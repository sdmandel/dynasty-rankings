/*
 * Shared progressive-enhancement shell. Pages retain their authored content if
 * JavaScript is unavailable; this adds common navigation and accessibility aids.
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
  if (!body || body.dataset.globalNav === "off") return;

  const page = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
  const isRankingsArticle = /^week\d+_power_rankings\.html$/.test(page);
  const sections = [
    { label: "Overview", items: [
      ["Hub", "index.html"],
      ["Standings", "standings.html"],
      ["Transactions", "transactions.html"],
      ["League Feed", "feed.html"],
    ] },
    { label: "League", items: [
      ["Team Intel", "team_intel.html"],
      ["League Analytics", "league_analytics.html"],
      ["Win Window", "win_window.html"],
      ["Rivalries", "rivalries.html"],
      ["Franchise History", "franchise_history.html"],
      ["Rules", "rules.html"],
      ["Polls", "polls.html"],
    ] },
    { label: "Players", items: [
      ["Roster Depth", "roster_depth.html"],
      ["Dynasty Rankings", "dynasty_rankings.html"],
      ["Prospect Desk", "prospects.html"],
      ["Closer Carousel", "closers.html"],
    ] },
    { label: "Editorial", items: [
      ["Current Power Rankings", "week16_power_rankings.html", "rankings-current"],
      ["Rankings Archive", "power_rankings.html", "rankings-archive"],
    ] },
  ];

  function isCurrent(href, kind) {
    if (kind === "rankings-current") return isRankingsArticle;
    if (kind === "rankings-archive") return page === "power_rankings.html";
    return page === href.toLowerCase();
  }

  let main = document.querySelector("main, [role='main']");
  let skipLink = null;
  if (!main) main = document.querySelector(".content, .page, .charts-section, .nav-section, .site-header");
  if (main) {
    if (!main.id) main.id = "main-content";
    main.tabIndex = -1;
    skipLink = document.createElement("a");
    skipLink.className = "skip-link";
    skipLink.href = `#${main.id}`;
    skipLink.textContent = "Skip to main content";
    body.insertBefore(skipLink, body.firstChild);
  }

  const nav = document.createElement("nav");
  nav.className = "global-nav";
  nav.setAttribute("aria-label", "Site navigation");
  const inner = document.createElement("div");
  inner.className = "global-nav-inner";

  const brand = document.createElement("a");
  brand.className = "global-nav-brand";
  brand.href = "index.html";
  brand.textContent = "Backyard";
  brand.setAttribute("aria-label", "Backyard league hub");
  inner.appendChild(brand);

  const toggle = document.createElement("button");
  toggle.className = "global-nav-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Open navigation menu");
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "globalNavMenu");
  toggle.innerHTML = '<span class="global-nav-toggle-bars" aria-hidden="true"></span>';
  inner.appendChild(toggle);

  const menu = document.createElement("div");
  menu.className = "global-nav-menu";
  menu.id = "globalNavMenu";
  sections.forEach((section) => {
    const group = document.createElement("details");
    group.className = "global-nav-group";
    const summary = document.createElement("summary");
    summary.className = "global-nav-section";
    summary.textContent = section.label;
    const list = document.createElement("div");
    list.className = "global-nav-links";
    list.setAttribute("aria-label", section.label);
    let sectionCurrent = false;
    section.items.forEach(([label, href, kind]) => {
      const link = document.createElement("a");
      link.className = "global-nav-link";
      link.href = href;
      link.textContent = label;
      if (isCurrent(href, kind)) {
        sectionCurrent = true;
        link.classList.add("active");
        link.setAttribute("aria-current", "page");
      }
      list.appendChild(link);
    });
    if (sectionCurrent) {
      group.classList.add("has-current");
    }
    summary.addEventListener('click', () => {
      if (group.open) return;
      menu.querySelectorAll('.global-nav-group[open]').forEach((other) => {
        if (other !== group) other.open = false;
      });
    });
    group.append(summary, list);
    menu.appendChild(group);
  });
  inner.appendChild(menu);

  const STORAGE_KEY = "pr-theme";
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  let mqListener = null;
  const theme = document.createElement("div");
  theme.className = "segmented global-nav-segmented";
  theme.setAttribute("role", "group");
  theme.setAttribute("aria-label", "Color theme");
  const themeButtons = [["Auto", "auto"], ["Light", "light"], ["Dark", "dark"]].map(([label, mode]) => {
    const button = document.createElement("button");
    button.className = "segmented-btn";
    button.type = "button";
    button.textContent = label;
    button.dataset.mode = mode;
    theme.appendChild(button);
    return button;
  });
  function syncThemeButtons() {
    const saved = localStorage.getItem(STORAGE_KEY);
    const current = saved === "dark" || saved === "light" ? saved : "auto";
    themeButtons.forEach((button) => {
      const active = button.dataset.mode === current;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }
  function useSystemTheme() {
    document.documentElement.dataset.theme = mq.matches ? "dark" : "light";
  }
  function applyTheme(mode) {
    if (mqListener) mq.removeEventListener("change", mqListener);
    mqListener = null;
    if (mode === "auto") {
      localStorage.removeItem(STORAGE_KEY);
      useSystemTheme();
      mqListener = () => { useSystemTheme(); syncThemeButtons(); };
      mq.addEventListener("change", mqListener);
    } else {
      document.documentElement.dataset.theme = mode;
      localStorage.setItem(STORAGE_KEY, mode);
    }
    syncThemeButtons();
  }
  themeButtons.forEach((button) => button.addEventListener("click", () => applyTheme(button.dataset.mode)));
  const savedTheme = localStorage.getItem(STORAGE_KEY);
  applyTheme(savedTheme === "dark" || savedTheme === "light" ? savedTheme : "auto");
  inner.appendChild(theme);

  nav.appendChild(inner);
  body.insertBefore(nav, skipLink ? skipLink.nextSibling : body.firstChild);

  function closeNav({ restoreFocus = false } = {}) {
    nav.classList.remove("is-open");
    body.classList.remove("global-nav-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation menu");
    if (restoreFocus) toggle.focus();
  }
  toggle.addEventListener("click", () => {
    const opening = toggle.getAttribute("aria-expanded") !== "true";
    if (!opening) return closeNav();
    nav.classList.add("is-open");
    body.classList.add("global-nav-open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close navigation menu");
  });
  menu.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("a")) closeNav();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.classList.contains("is-open")) closeNav({ restoreFocus: true });
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth >= 768) closeNav();
  });

  if (!document.querySelector('link[href*="fonts.googleapis.com/css2"][href*="Source+Serif+4"]')) {
    const font = document.createElement("link");
    font.rel = "stylesheet";
    font.href = "https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,300..900;1,8..60,300..900&display=swap";
    document.head.appendChild(font);
  }

  if (!document.querySelector("footer, .site-footer, .footer")) {
    const footer = document.createElement("footer");
    footer.className = "site-shell-footer";
    footer.innerHTML = '<a href="index.html">Backyard league hub</a><span aria-hidden="true"> · </span><a href="rules.html">League rules</a>';
    body.appendChild(footer);
  }
})();
