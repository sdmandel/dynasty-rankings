/*
 * FOUC PREVENTION — copy this snippet into each HTML page's <head>, before any stylesheets.
 *
 * <!-- FOUC prevention: paste this into <head> before any stylesheets -->
 * <script>
 * (function(){var t=localStorage.getItem('pr-theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t;})();
 * </script>
 */
(() => {
  const analyticsSrc = "assets/analytics.js";
  if (!document.querySelector(`script[src="${analyticsSrc}"]`)) {
    const analytics = document.createElement("script");
    analytics.src = analyticsSrc;
    analytics.async = true;
    (document.head || document.body || document.documentElement).appendChild(analytics);
  }

  const body = document.body;
  if (!body || body.dataset.globalNav === "off") {
    return;
  }

  const navItems = [
    ["The Hub", "index.html"],
    ["Power Rankings", "power_rankings.html"],
    ["Standings", "standings.html"],
    ["Team Intel", "team_intel.html"],
    ["Roster Depth", "roster_depth.html"],
    ["Dynasty Rankings", "dynasty_rankings.html"],
    ["Prospects", "prospects.html"],
    ["Closers", "closers.html"],
    ["Transactions", "transactions.html"],
  ];
  const page = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
  const isPowerRankingsArticle = /^week\d+_power_rankings\.html$/.test(page);

  const nav = document.createElement("nav");
  nav.className = "global-nav";
  nav.setAttribute("aria-label", "Global navigation");

  const inner = document.createElement("div");
  inner.className = "global-nav-inner";

  const brand = document.createElement("a");
  brand.className = "global-nav-brand";
  brand.href = "index.html";
  brand.textContent = "Backyard";
  inner.appendChild(brand);

  const toggle = document.createElement("button");
  toggle.className = "global-nav-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Open navigation menu");
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "globalNavLinks");
  toggle.innerHTML = '<span class="global-nav-toggle-bars" aria-hidden="true"></span>';
  inner.appendChild(toggle);

  const links = document.createElement("div");
  links.className = "global-nav-links";
  links.id = "globalNavLinks";

  navItems.forEach(([label, href]) => {
    const link = document.createElement("a");
    link.className = "global-nav-link";
    link.href = href;
    link.textContent = label;
    const target = href.toLowerCase();
    if (page === target || (isPowerRankingsArticle && target === "power_rankings.html")) {
      link.classList.add("active");
      link.setAttribute("aria-current", "page");
    }
    links.appendChild(link);
  });

  inner.appendChild(links);

  (function() {
    const STORAGE_KEY = "pr-theme";
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    let mqListener = null;

    function applyTheme(mode) {
      if (mode === "auto") {
        delete document.documentElement.dataset.theme;
        localStorage.removeItem(STORAGE_KEY);
        if (!mqListener) {
          mqListener = () => syncButtons();
          mq.addEventListener("change", mqListener);
        }
      } else {
        document.documentElement.dataset.theme = mode;
        localStorage.setItem(STORAGE_KEY, mode);
        if (mqListener) {
          mq.removeEventListener("change", mqListener);
          mqListener = null;
        }
      }
      syncButtons();
    }

    function getInitialMode() {
      const saved = localStorage.getItem(STORAGE_KEY);
      return (saved === "dark" || saved === "light") ? saved : "auto";
    }

    const initialMode = getInitialMode();
    if (initialMode !== "auto") {
      document.documentElement.dataset.theme = initialMode;
    } else {
      mqListener = () => syncButtons();
      mq.addEventListener("change", mqListener);
    }

    const seg = document.createElement("div");
    seg.className = "segmented global-nav-segmented";
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Theme");

    const modes = [["Auto", "auto"], ["Light", "light"], ["Dark", "dark"]];
    const btns = modes.map(([label, mode]) => {
      const b = document.createElement("button");
      b.className = "segmented-btn";
      b.type = "button";
      b.textContent = label;
      b.dataset.mode = mode;
      b.addEventListener("click", () => applyTheme(mode));
      seg.appendChild(b);
      return b;
    });

    function syncButtons() {
      const saved = localStorage.getItem(STORAGE_KEY);
      const current = (saved === "dark" || saved === "light") ? saved : "auto";
      btns.forEach(b => {
        const active = b.dataset.mode === current;
        b.classList.toggle("active", active);
        b.setAttribute("aria-pressed", String(active));
      });
    }
    syncButtons();

    inner.appendChild(seg);
  })();

  if (!document.querySelector('link[href*="fonts.googleapis.com/css2"][href*="Source+Serif+4"]')) {
    const pc1 = document.createElement("link");
    pc1.rel = "preconnect";
    pc1.href = "https://fonts.googleapis.com";
    document.head.appendChild(pc1);
    const pc2 = document.createElement("link");
    pc2.rel = "preconnect";
    pc2.href = "https://fonts.gstatic.com";
    pc2.crossOrigin = "anonymous";
    document.head.appendChild(pc2);
    const font = document.createElement("link");
    font.rel = "stylesheet";
    font.href = "https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,300..900;1,8..60,300..900&display=swap";
    document.head.appendChild(font);
  }

  nav.appendChild(inner);
  body.insertBefore(nav, body.firstChild);

  const closeNav = () => {
    nav.classList.remove("is-open");
    body.classList.remove("global-nav-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation menu");
  };

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    if (expanded) {
      closeNav();
      return;
    }
    nav.classList.add("is-open");
    body.classList.add("global-nav-open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close navigation menu");
  });

  links.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("a")) closeNav();
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNav();
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth >= 768) closeNav();
  });
})();
