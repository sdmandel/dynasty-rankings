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
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");

    function applyTheme(theme) {
      document.documentElement.dataset.theme = theme;
    }

    function getInitialTheme() {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "dark" || saved === "light") return saved;
      return prefersDark.matches ? "dark" : "light";
    }

    applyTheme(getInitialTheme());

    const btn = document.createElement("button");
    btn.className = "global-nav-theme";
    btn.type = "button";
    btn.setAttribute("aria-label", "Toggle dark/light theme");
    btn.innerHTML = '<span aria-hidden="true" class="theme-icon"></span>';

    btn.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      localStorage.setItem(STORAGE_KEY, next);
    });

    function syncIcon() {
      btn.dataset.current = document.documentElement.dataset.theme;
    }
    new MutationObserver(syncIcon).observe(document.documentElement, { attributeFilter: ["data-theme"] });
    syncIcon();

    inner.appendChild(btn);
  })();

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
