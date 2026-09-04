(function () {
  var button = document.getElementById('night');
  var night = false;
  function paint(frame) {
    var doc = frame.contentDocument;
    if (!doc || !doc.body) return;
    doc.body.classList.toggle('nightMode', night);
    doc.body.classList.toggle('night_mode', night);
  }
  var frames = Array.prototype.slice.call(document.querySelectorAll('iframe.cardframe'));
  frames.forEach(function (frame) {
    frame.addEventListener('load', function () { paint(frame); });
  });
  button.addEventListener('click', function () {
    night = !night;
    button.setAttribute('aria-pressed', String(night));
    frames.forEach(paint);
  });
})();
