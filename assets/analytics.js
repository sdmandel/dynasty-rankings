(() => {
  const BEACON_SRC = "https://static.cloudflareinsights.com/beacon.min.js";
  const DEFAULT_CF_TOKEN = "e14a66458e824e24805b097c66200b3d";
  const GLOBAL_KEY = "__siteAnalytics";

  if (window[GLOBAL_KEY] && window[GLOBAL_KEY].initialized) {
    return;
  }

  const queue = [];
  const listeners = [];
  const currentScript = document.currentScript;
  const config = {
    endpoint: (currentScript && currentScript.dataset.endpoint) || window.siteAnalyticsEndpoint || "",
    cfToken: (currentScript && currentScript.dataset.cfToken) || window.siteAnalyticsCfToken || DEFAULT_CF_TOKEN,
  };

  function normalizeProps(props) {
    if (!props || typeof props !== "object" || Array.isArray(props)) {
      return {};
    }
    const cleaned = {};
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || typeof value === "function") {
        continue;
      }
      cleaned[key] = value;
    }
    return cleaned;
  }

  function dispatchToEndpoint(event) {
    if (!config.endpoint) {
      return false;
    }

    const payload = JSON.stringify(event);
    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([payload], { type: "application/json" });
        if (navigator.sendBeacon(config.endpoint, blob)) {
          return true;
        }
      }
    } catch (_) {
      // Fall through to fetch.
    }

    fetch(config.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
      credentials: "same-origin",
    }).catch(() => {});
    return true;
  }

  function dispatchEvent(event) {
    const zaraz = window.zaraz;
    if (zaraz && typeof zaraz.track === "function") {
      try {
        zaraz.track(event.name, event.props);
        return true;
      } catch (_) {
        // Fall through to the configured endpoint.
      }
    }

    return dispatchToEndpoint(event);
  }

  function flushQueue() {
    if (!queue.length) {
      return;
    }

    const pending = queue.splice(0);
    pending.forEach(event => {
      if (!dispatchEvent(event)) {
        queue.push(event);
      }
    });
  }

  function ensureCloudflareBeacon() {
    if (document.querySelector('script[src*="cloudflareinsights.com/beacon.min.js"]')) {
      return;
    }
    if (document.querySelector("script[data-cf-beacon]")) {
      return;
    }

    const script = document.createElement("script");
    script.async = true;
    script.src = BEACON_SRC;
    script.dataset.cfBeacon = JSON.stringify({ token: config.cfToken });
    (document.head || document.body || document.documentElement).appendChild(script);
  }

  function track(name, props = {}) {
    const eventName = String(name || "").trim();
    if (!eventName) {
      return false;
    }

    const event = {
      name: eventName,
      props: normalizeProps(props),
      path: location.pathname,
      url: location.href,
      timestamp: new Date().toISOString(),
    };

    if (dispatchEvent(event)) {
      return true;
    }

    queue.push(event);
    return false;
  }

  function configure(nextConfig = {}) {
    if (typeof nextConfig !== "object" || nextConfig === null) {
      return;
    }

    if (typeof nextConfig.endpoint === "string") {
      config.endpoint = nextConfig.endpoint;
    }
    if (typeof nextConfig.cfToken === "string") {
      config.cfToken = nextConfig.cfToken;
    }

    flushQueue();
  }

  function onLinkClick(event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    const anchor = event.target && event.target.closest ? event.target.closest("a[href]") : null;
    if (!anchor) {
      return;
    }

    const rawHref = anchor.getAttribute("href") || "";
    if (!rawHref || rawHref.startsWith("#") || rawHref.startsWith("mailto:") || rawHref.startsWith("tel:") || rawHref.startsWith("javascript:")) {
      return;
    }

    let url;
    try {
      url = new URL(anchor.href, location.href);
    } catch (_) {
      return;
    }

    if (url.origin === location.origin && url.pathname === location.pathname && url.hash === location.hash) {
      return;
    }

    const kind = url.origin === location.origin ? "internal" : "outbound";
    track("nav_click", {
      kind,
      href: url.href,
      text: (anchor.textContent || "").trim().slice(0, 80),
    });
  }

  ensureCloudflareBeacon();

  const api = window.siteAnalytics || {};
  api.track = track;
  api.configure = configure;
  api.flush = flushQueue;
  api.initialized = true;
  api.version = "1.0.0";
  window.siteAnalytics = api;
  window[GLOBAL_KEY] = api;

  if (!listeners.length) {
    document.addEventListener("click", onLinkClick, true);
    listeners.push("click");
  }

  window.setTimeout(flushQueue, 2000);
})();
