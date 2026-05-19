(() => {
  const ANDROID_PACKAGE = "com.fangraphs.fangraphsmobile";

  function isAndroid() {
    return /Android/i.test(navigator.userAgent || "");
  }

  function isIOS() {
    return /iPhone|iPad|iPod/i.test(navigator.userAgent || "");
  }

  function webUrl({ slug, id, statType = "batting" }) {
    return `https://www.fangraphs.com/players/${encodeURIComponent(slug)}/${encodeURIComponent(id)}/stats/${encodeURIComponent(statType)}`;
  }

  function appAwareUrl(player) {
    const fallback = webUrl(player);
    if (isAndroid()) {
      const path = `players/${encodeURIComponent(player.slug)}/${encodeURIComponent(player.id)}/stats/${encodeURIComponent(player.statType || "batting")}`;
      return `intent://${path}#Intent;scheme=https;package=${ANDROID_PACKAGE};S.browser_fallback_url=${encodeURIComponent(fallback)};end`;
    }
    return fallback;
  }

  function targetForDevice() {
    return isIOS() || isAndroid() ? "_self" : "_blank";
  }

  window.fangraphsLinks = {
    appAwareUrl,
    targetForDevice,
    webUrl,
  };
})();
