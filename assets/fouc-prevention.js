(function() {
  var t = localStorage.getItem('pr-theme');
  document.documentElement.dataset.theme =
    (t === 'dark' || t === 'light')
      ? t
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
})();
