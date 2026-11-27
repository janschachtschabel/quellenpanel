"""Import der Korrekturen: Datei lesen, Spalten zuordnen, Vorschau, Ergebnis."""
import io
import json

import openpyxl
import pytest

import korrektur_import as ki
from korrekturen import Korrektur

A = "27c77a87-8250-4a26-9d95-3b24cd162539"
B = "bf727265-d124-4c33-a924-d632d46ee855"
C = "16489b8d-1111-4222-8333-944455556666"


def _csv(text, sep=";"):
    return ("﻿" + text.replace(";", sep)).encode("utf-8")


def test_reads_csv_semicolon_and_comma():
    for sep in (";", ","):
        spalten, zeilen = ki.lesen_datei(_csv("Typ;Schlüssel;Aktion\nnode;%s;blacklist\n" % A, sep), "csv")
        assert spalten == ["Typ", "Schlüssel", "Aktion"]
        assert zeilen == [{"Typ": "node", "Schlüssel": A, "Aktion": "blacklist"}]


def test_reads_json_list():
    data = json.dumps([{"typ": "node", "schluessel": A, "aktion": "whitelist", "n": 3}]).encode()
    spalten, zeilen = ki.lesen_datei(data, "json")
    assert spalten == ["typ", "schluessel", "aktion", "n"]
    assert zeilen[0]["n"] == "3"


def test_reads_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Typ", "Schlüssel", "Aktion", "Wert"])
    ws.append(["node", A, "blacklist", None])
    buf = io.BytesIO()
    wb.save(buf)
    spalten, zeilen = ki.lesen_datei(buf.getvalue(), "xlsx")
    assert spalten == ["Typ", "Schlüssel", "Aktion", "Wert"]
    assert zeilen == [{"Typ": "node", "Schlüssel": A, "Aktion": "blacklist", "Wert": ""}]


@pytest.mark.parametrize("data,fmt", [(b"{kaputt", "json"), (b'{"a": 1}', "json"),
                                      (b"keine xlsx", "xlsx"), (b"a;b\n1;2", "pdf"), (b"", "csv")])
def test_bad_input_raises(data, fmt):
    with pytest.raises(ki.ImportFehler):
        ki.lesen_datei(data, fmt)


def test_too_many_rows_raises():
    text = "Typ;Schlüssel;Aktion\n" + ("node;%s;blacklist\n" % A) * (ki.MAX_ZEILEN + 1)
    with pytest.raises(ki.ImportFehler):
        ki.lesen_datei(_csv(text), "csv")


def test_auto_mapping_own_header_and_aliases():
    own = ki.auto_zuordnung(["Typ", "Schlüssel", "Aktion", "Wert", "Kommentar", "Geändert von"])
    assert own == {"typ": "Typ", "schluessel": "Schlüssel", "aktion": "Aktion", "wert": "Wert",
                   "kommentar": "Kommentar"}
    alt = ki.auto_zuordnung(["Node-Id", "Liste", "TITEL"])
    assert alt["schluessel"] == "Node-Id" and alt["aktion"] == "Liste" and alt["kommentar"] == "TITEL"
    assert alt["typ"] is None


def _rows(*triples):
    return [{"Typ": t, "Schlüssel": s, "Aktion": a, "Wert": w} for t, s, a, w in triples]


MAP = {"typ": "Typ", "schluessel": "Schlüssel", "aktion": "Aktion", "wert": "Wert", "kommentar": None}


def test_preview_ergaenzen_counts():
    bestand = [Korrektur("node", A, "blacklist"), Korrektur("bezugsquelle", "youtube", "beschreibung", "alt")]
    zeilen = _rows(("node", A, "blacklist", ""),                    # unverändert
                   ("bezugsquelle", "youtube", "beschreibung", "neu"),  # geändert
                   ("node", C, "whitelist", ""),                    # neu
                   ("node", "kaputt", "blacklist", ""))             # fehlerhaft
    v = ki.vorschau(zeilen, MAP, bestand, "ergaenzen", wer="JS")
    assert v["unveraendert"] == 1
    assert [k.schluessel for k in v["neu"]] == [C]
    assert v["geaendert"][0]["alt"].wert == "alt" and v["geaendert"][0]["neu"].wert == "neu"
    assert v["fehlerhaft"][0]["zeile"] == 5 and "Node-ID" in v["fehlerhaft"][0]["text"]
    assert v["entfallen"] == []
    erg = v["ergebnis"]
    assert len(erg) == 3
    assert next(k for k in erg if k.typ == "bezugsquelle").wert == "neu"
    assert next(k for k in erg if k.schluessel == C).geaendert_von == "JS"
    assert next(k for k in erg if k.schluessel == A).geaendert_von == ""   # unverändert bleibt


def test_preview_list_switch_is_change():
    v = ki.vorschau(_rows(("node", A, "whitelist", "")), MAP, [Korrektur("node", A, "blacklist")],
                    "ergaenzen", wer="JS")
    assert len(v["geaendert"]) == 1 and v["neu"] == []
    assert [k.aktion for k in v["ergebnis"]] == ["whitelist"]


def test_preview_ersetzen_reports_dropped():
    bestand = [Korrektur("node", A, "blacklist"), Korrektur("node", B, "whitelist")]
    v = ki.vorschau(_rows(("node", A, "blacklist", "")), MAP, bestand, "ersetzen", wer="JS")
    assert [k.schluessel for k in v["entfallen"]] == [B]
    assert [k.schluessel for k in v["ergebnis"]] == [A]


def test_missing_required_mapping_raises():
    with pytest.raises(ki.ImportFehler):
        ki.vorschau(_rows(("node", A, "blacklist", "")), {**MAP, "aktion": None}, [], "ergaenzen", wer="JS")


def test_unknown_mode_raises():
    with pytest.raises(ki.ImportFehler):
        ki.vorschau([], MAP, [], "mischen", wer="JS")


def test_vermerk_never_replaces_a_blacklist_entry():
    # Abschluss-Audit: blacklist and vermerk on one node shared a key, so re-importing the current
    # file turned the blacklist into a second vermerk and made the source public.
    bestand = [Korrektur("node", A, "blacklist"), Korrektur("node", A, "vermerk", "", "geprüft")]
    zeilen = [{"Typ": "node", "Schlüssel": A, "Aktion": "blacklist", "Wert": "", "Kommentar": ""},
              {"Typ": "node", "Schlüssel": A, "Aktion": "vermerk", "Wert": "", "Kommentar": "geprüft"}]
    v = ki.vorschau(zeilen, {**MAP, "kommentar": "Kommentar"}, bestand, "ergaenzen", wer="JS")
    assert sorted(k.aktion for k in v["ergebnis"]) == ["blacklist", "vermerk"]
    assert v["unveraendert"] == 2 and v["geaendert"] == []
    # A new vermerk is added beside the blacklist, it does not replace it.
    v = ki.vorschau(_rows(("node", A, "vermerk", "")), MAP, [Korrektur("node", A, "blacklist")],
                    "ergaenzen", wer="JS")
    assert sorted(k.aktion for k in v["ergebnis"]) == ["blacklist", "vermerk"]
