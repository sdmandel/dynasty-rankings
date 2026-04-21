(() => {
  const body = document.body;
  if (!body || body.dataset.hubLink === "off") {
    return;
  }

  const header = document.querySelector(".site-header, .header");
  if (!header) {
    return;
  }

  const existing = header.querySelector(".back-link, .site-shell-back-link");
  if (existing) {
    existing.setAttribute("href", "index.html");
    existing.textContent = "\u2190 The Hub";
    existing.classList.add("site-shell-back-link");
    return;
  }

  const link = document.createElement("a");
  link.href = "index.html";
  link.className = "site-shell-back-link";
  link.textContent = "\u2190 The Hub";
  header.insertBefore(link, header.firstChild);
})();
