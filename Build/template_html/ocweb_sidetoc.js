// OpenChapters sidetoc enhancement:
//   1. Mark the sidetoc entry that matches the current page so CSS
//      can highlight it.
//   2. Scroll the sidetoc container so the current entry is visible
//      rather than resetting to the top on every navigation.
//
// Loaded via <script src="ocweb_sidetoc.js"></script> so it works
// under a strict Content-Security-Policy that forbids inline scripts.
(function () {
  function enhance() {
    var toc = document.querySelector('nav.sidetoc');
    if (!toc) return;
    var here = location.pathname.split('/').pop() || 'index.html';
    var links = toc.querySelectorAll('a');
    var current = null;
    for (var i = 0; i < links.length; i++) {
      var href = links[i].getAttribute('href') || '';
      var file = href.split('#')[0].split('/').pop();
      if (file && file === here) { current = links[i]; break; }
    }
    if (!current) return;
    current.classList.add('ochtml-current');
    var scroller = toc.querySelector('div.sidetoccontents') || toc;
    if (typeof current.scrollIntoView === 'function') {
      try { current.scrollIntoView({ block: 'center' }); return; } catch (e) { /* fall through */ }
    }
    var top = current.offsetTop - (scroller.clientHeight / 2);
    scroller.scrollTop = Math.max(0, top);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhance);
  } else {
    enhance();
  }
})();
