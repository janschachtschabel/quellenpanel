"""Branding aus dem Profil: /api/capabilities liefert nur gültige Hex-Farben."""
import repo_profile


def test_capabilities_has_profile_branding(client):
    b = client.get("/api/capabilities").json()["branding"]
    assert b == {"primary": "#003b7c", "accent": "#e4f700"}


def test_invalid_branding_is_dropped(client, monkeypatch):
    import dataclasses
    prof = dataclasses.replace(repo_profile.get(),
                               branding={"primary": "red; background:url(x)", "accent": "#00ff00", "logo": "x.svg"})
    monkeypatch.setattr(repo_profile, "get", lambda: prof)
    b = client.get("/api/capabilities").json()["branding"]
    assert b == {"accent": "#00ff00"}
