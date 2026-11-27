// Beispiel für Gastseiten: Höhe des Quellenpanel-iframes anfordern und übernehmen.
(function () {
  var frame = document.getElementById('wq-frame');
  if (!frame) return;
  var herkunft = new URL(frame.src, location.href).origin;
  window.addEventListener('message', function (ev) {
    if (ev.source !== frame.contentWindow || ev.origin !== herkunft) return;
    if (ev.data && ev.data.type === 'quellenpanel:hoehe' && typeof ev.data.hoehe === 'number') {
      frame.style.height = Math.min(ev.data.hoehe, 5000) + 'px';
    }
  });
  frame.addEventListener('load', function () {
    frame.contentWindow.postMessage({ type: 'quellenpanel:hoehe?' }, herkunft);
  });
})();
