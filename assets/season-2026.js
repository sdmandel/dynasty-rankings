(function () {
  const player = document.getElementById("seasonFilm");
  const poster = document.getElementById("seasonFilmPoster");
  const play = document.getElementById("seasonFilmPlay");
  const video = document.getElementById("seasonFilmVideo");
  const download = document.getElementById("seasonFilmDownload");
  if (!player || !poster || !play || !video || !download) return;

  function theme() {
    return document.documentElement.dataset.theme === "light" ? "light" : "dark";
  }

  function asset(kind, selectedTheme) {
    return `media/season-2026/${kind}-${selectedTheme}.${kind === "film-poster" ? "png" : "mp4"}?v=3`;
  }

  function syncPreview() {
    if (player.classList.contains("is-playing")) return;
    const selectedTheme = theme();
    poster.src = asset("film-poster", selectedTheme);
    download.href = asset("season-2026", selectedTheme);
  }

  play.addEventListener("click", () => {
    const selectedTheme = theme();
    video.src = asset("season-2026", selectedTheme);
    download.href = video.src;
    player.classList.add("is-playing");
    video.play().catch(() => {});
  });

  new MutationObserver(syncPreview).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  syncPreview();
})();
