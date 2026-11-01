/* Radar PND : interactions légères (amélioration progressive, tout fonctionne sans JavaScript). */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ($("[name=csrfmiddlewaretoken]") || {}).value || "";
  const nf = (v, d) => Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d == null ? 1 : d }).replace(/ /g, " ");
  const mobile = () => window.matchMedia("(max-width: 899.98px)").matches;

  function toast(msg) {
    let t = $("#toast");
    if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = msg; t.hidden = false;
    t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
    clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 2400);
  }

  /* ------------------------------------------------ tiroir de navigation */
  const drawer = $("#drawer"), mb = $(".menu-btn");
  let lastFocus = null;
  function openDrawer() {
    lastFocus = document.activeElement;
    drawer.hidden = false; mb.setAttribute("aria-expanded", "true");
    document.body.classList.add("sheet-lock");
    const f = $("[data-close]", drawer); if (f) f.focus();
  }
  function closeDrawer() {
    drawer.hidden = true; mb.setAttribute("aria-expanded", "false");
    document.body.classList.remove("sheet-lock");
    if (lastFocus) lastFocus.focus();
  }
  if (drawer && mb) {
    mb.addEventListener("click", openDrawer);
    drawer.addEventListener("click", (e) => { if (e.target === drawer || e.target.closest("[data-close]")) closeDrawer(); });
  }

  /* ------------------------------------------------ feuilles du bas (filtres, profil) */
  let backdrop = null, openSheet = null;
  function showSheet(sheet) {
    if (!sheet) return;
    lastFocus = document.activeElement;
    backdrop = document.createElement("div"); backdrop.className = "sheet-backdrop";
    backdrop.addEventListener("click", hideSheet);
    document.body.appendChild(backdrop);
    sheet.classList.add("open"); openSheet = sheet;
    sheet.setAttribute("role", "dialog"); sheet.setAttribute("aria-modal", "true");
    document.body.classList.add("sheet-lock");
    $$("[data-sheet-open]").forEach((b) => b.getAttribute("aria-controls") === sheet.id && b.setAttribute("aria-expanded", "true"));
    setTimeout(() => { const f = $("input:not([type=hidden]), select, button", sheet); if (f) f.focus({ preventScroll: true }); }, 60);
  }
  function hideSheet() {
    if (!openSheet) return;
    openSheet.classList.remove("open");
    openSheet.removeAttribute("role"); openSheet.removeAttribute("aria-modal");
    $$("[data-sheet-open]").forEach((b) => b.setAttribute("aria-expanded", "false"));
    openSheet = null;
    if (backdrop) { backdrop.remove(); backdrop = null; }
    document.body.classList.remove("sheet-lock");
    if (lastFocus) lastFocus.focus({ preventScroll: true });
  }
  $$("[data-sheet-open]").forEach((b) => b.addEventListener("click", () => showSheet(document.getElementById(b.dataset.sheetOpen))));
  document.addEventListener("click", (e) => { if (e.target.closest("[data-sheet-close]")) hideSheet(); });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (openSheet) hideSheet();
    else if (drawer && !drawer.hidden) closeDrawer();
  });
  window.matchMedia("(min-width: 900px)").addEventListener("change", (m) => { if (m.matches) hideSheet(); });

  /* ------------------------------------------------ formulaires de filtres */
  $$("form[data-filters]").forEach((f) => {
    const sheet = $(".sheet", f);
    const count = () => {
      const n = $$(".sheet select", f).filter((s) => s.value).length;
      $$(".js-fcount", f).forEach((c) => { c.textContent = n; c.hidden = !n; });
    };
    f.addEventListener("change", (e) => {
      if (e.target.name === "pilier" && f.secteur) f.secteur.value = "";
      count();
      if (e.target.tagName === "SELECT" && !(sheet && sheet.classList.contains("open"))) f.submit();
    });
    const reset = $("[data-reset]", f);
    if (reset) reset.addEventListener("click", () => { $$(".sheet select", f).forEach((s) => (s.value = "")); count(); });
    count();
  });

  /* ------------------------------------------------ recherche de l'accueil : actions ou projets */
  const qf = $("#qbox-form");
  if (qf) {
    const qi = $("input[data-ph-court]", qf);
    if (qi && window.matchMedia("(max-width: 479.98px)").matches) qi.placeholder = qi.dataset.phCourt;
    const sync = () => { const r = $("input[name=cible]:checked", qf); if (r) qf.action = r.dataset.action; };
    qf.addEventListener("change", sync); sync();
    qf.addEventListener("submit", () => $$("input[name=cible]", qf).forEach((r) => (r.disabled = true)));
  }

  /* ------------------------------------------------ profil du radar */
  const pf = $("#profil-form");
  if (pf) {
    const panel = $("#profil");
    const presets = (() => { const el = $("#presets"); return el ? JSON.parse(el.textContent) : {}; })();
    const steps = $$(".pstep", pf);
    let cur = 0;
    const applyPreset = (type) => {
      const p = presets[type]; if (!p) return;
      $$("input[name=familles]", pf).forEach((i) => (i.checked = p.familles.includes(i.value)));
      $$("input[name=secteurs]", pf).forEach((i) => (i.checked = p.secteurs.includes(i.value)));
      $$("input[name=horizon]", pf).forEach((i) => (i.checked = i.value === p.horizon));
      $$("input[name=taille]", pf).forEach((i) => (i.checked = i.value === p.taille));
      groupCounts();
    };
    const groupCounts = () => $$(".pgroup", pf).forEach((g) => {
      const n = $$("input:checked", g).length, el = $(".n", g);
      if (el) { el.textContent = n ? `${n} suivi${n > 1 ? "s" : ""}` : "aucun"; el.classList.toggle("on", !!n); }
    });
    const show = (i) => {
      cur = Math.max(0, Math.min(steps.length - 1, i));
      steps.forEach((s, k) => s.classList.toggle("cur", k === cur));
      $$(".stepper-dots i", pf).forEach((d, k) => d.classList.toggle("on", k <= cur));
      $$(".stepper-labels span", pf).forEach((d, k) => d.classList.toggle("on", k === cur));
      const lab = $(".stepper-top b", pf); if (lab) lab.textContent = `Étape ${cur + 1} sur ${steps.length}`;
      const prev = $("[data-prev]", pf), next = $("[data-next]", pf), go = $("[data-go]", pf);
      if (prev) prev.textContent = cur ? "Retour" : "Annuler";
      if (next) next.hidden = cur === steps.length - 1;
      if (go) go.hidden = cur !== steps.length - 1;
      const sc = $(".steps-scroll", pf); if (sc) sc.scrollTop = 0;
    };
    show(0); groupCounts();
    $$("[data-profile-open]").forEach((b) => b.addEventListener("click", () => { show(+(b.dataset.step || 0)); showSheet(panel); }));
    const prev = $("[data-prev]", pf), next = $("[data-next]", pf);
    if (prev) prev.addEventListener("click", () => (cur ? show(cur - 1) : hideSheet()));
    if (next) next.addEventListener("click", () => show(cur + 1));
    let h;
    pf.addEventListener("change", (e) => {
      groupCounts();
      if (panel.classList.contains("open")) {
        if (e.target.name === "type") applyPreset(e.target.value);
        return; // sur mobile, on valide à la dernière étape
      }
      if (e.target.name === "type") { $("#appliquer_preset").value = "1"; pf.submit(); return; }
      clearTimeout(h); h = setTimeout(() => pf.submit(), 300);
    });
  }

  /* ------------------------------------------------ ajout / retrait de la sélection sans rechargement */
  document.addEventListener("submit", async (e) => {
    const f = e.target.closest("form.js-toggle");
    if (!f) return;
    e.preventDefault();
    try {
      const r = await fetch(f.action, { method: "POST", headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" }, credentials: "same-origin" });
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      $$(`form.js-toggle[action="${f.getAttribute("action")}"] button`).forEach((b) => {
        b.setAttribute("aria-pressed", d.selected);
        const lbl = b.querySelector(".lbl");
        if (lbl) lbl.textContent = d.selected ? (b.dataset.on || "Retenue") : (b.dataset.off || "Retenir");
        if (b.dataset.ariaOn) b.setAttribute("aria-label", d.selected ? b.dataset.ariaOn : b.dataset.ariaOff);
      });
      $$(".js-sel-count").forEach((c) => { c.textContent = d.count; c.hidden = !d.count; });
      toast(d.selected ? "Ajoutée à votre sélection" : "Retirée de votre sélection");
    } catch (err) { f.submit(); }
  });

  /* ------------------------------------------------ copier un paragraphe */
  function copyText(txt, el) {
    const done = () => toast("Paragraphe copié dans le presse-papiers");
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(txt).then(done, () => selectEl(el));
    else selectEl(el);
  }
  function selectEl(el) {
    if (!el) return;
    if (el.hidden) { el.hidden = false; }
    const r = document.createRange(); r.selectNodeContents(el);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    toast("Texte sélectionné : copiez-le avec la commande Copier");
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-copy]"); if (!b) return;
    const el = document.getElementById(b.dataset.copy);
    if (el) copyText(el.dataset.text || el.innerText, el);
  });

  /* ------------------------------------------------ notes de sélection : enregistrement automatique */
  $$("form.js-note").forEach((f) => {
    const ta = f.querySelector("textarea"), ok = f.querySelector(".saved");
    let h;
    const save = async () => {
      try {
        const r = await fetch(f.action, { method: "POST", body: new FormData(f), headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" }, credentials: "same-origin" });
        if (r.ok && ok) { ok.classList.add("on"); setTimeout(() => ok.classList.remove("on"), 1600); }
      } catch (e) { /* le bouton reste disponible */ }
    };
    ta.addEventListener("input", () => { clearTimeout(h); h = setTimeout(save, 900); });
    f.addEventListener("submit", (e) => { e.preventDefault(); save(); });
  });

  /* ------------------------------------------------ lignes de tableau cliquables */
  document.addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-href]");
    if (!tr || e.target.closest("a,button,form")) return;
    window.location = tr.dataset.href;
  });

  /* ------------------------------------------------ « Charger plus » */
  document.addEventListener("click", async (e) => {
    const a = e.target.closest("a[data-more]");
    if (!a) return;
    e.preventDefault();
    a.setAttribute("aria-busy", "true"); const lbl = a.querySelector(".lbl"); const old = lbl ? lbl.textContent : "";
    if (lbl) lbl.textContent = "Chargement…";
    try {
      const r = await fetch(a.href, { credentials: "same-origin" });
      const doc = new DOMParser().parseFromString(await r.text(), "text/html");
      [["#liste-cartes", "li"], ["#liste-table tbody", "tr"]].forEach(([sel, tag]) => {
        const dst = $(sel), src = $(sel, doc);
        if (dst && src) Array.from(src.children).filter((c) => c.tagName === tag.toUpperCase()).forEach((c) => dst.appendChild(document.adoptNode(c)));
      });
      const pager = $("#pager"), np = $("#pager", doc);
      if (pager && np) { const n = document.adoptNode(np); $$("[data-prev-page]", n).forEach((x) => x.remove()); pager.replaceWith(n); }
      history.replaceState(null, "", a.href);
    } catch (err) { window.location = a.href; }
    finally { a.removeAttribute("aria-busy"); if (lbl) lbl.textContent = old; }
  });

  /* ------------------------------------------------ panneaux repliables : repliés sur mobile */
  if (mobile()) $$("details[data-mobile-closed]").forEach((d) => d.removeAttribute("open"));

  /* ------------------------------------------------ bascule de listes (Tendances) */
  $$("[data-seg]").forEach((g) => {
    const btns = $$("button", g);
    btns.forEach((b) => b.addEventListener("click", () => {
      btns.forEach((x) => { x.setAttribute("aria-pressed", x === b); const p = document.getElementById(x.dataset.target); if (p) p.hidden = x !== b; });
    }));
  });

  /* ------------------------------------------------ apparition au défilement */
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const io = new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } }), { rootMargin: "0px 0px -8% 0px" });
    $$(".reveal").forEach((el) => io.observe(el));
  } else $$(".reveal").forEach((el) => el.classList.add("in"));

  /* ------------------------------------------------ graphiques */
  if (!window.Chart) return;
  const css = getComputedStyle(document.documentElement);
  const INK = css.getPropertyValue("--ink").trim() || "#0e1a2b";
  const MUTED = css.getPropertyValue("--muted").trim() || "#5b6779";
  const LINE = css.getPropertyValue("--line-2").trim() || "#edf0f4";
  Chart.defaults.font.family = css.getPropertyValue("--f-ui");
  Chart.defaults.font.size = 12;
  Chart.defaults.font.weight = 600;
  Chart.defaults.color = MUTED;
  Chart.defaults.plugins.tooltip.backgroundColor = INK;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 10;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "700" };
  Chart.defaults.animation.duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 500;
  const data = (id) => { const el = document.getElementById(id); return el ? JSON.parse(el.textContent) : null; };
  const mdTick = (v) => nf(v, 0);
  const hexA = (hex, a) => { const n = parseInt(hex.replace("#", ""), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; };

  /* Programmation annuelle d'un pilier, d'un secteur ou d'une action (Md FCFA) */
  $$("canvas[data-chart=annuel]").forEach((cv) => {
    const d = data(cv.dataset.src); if (!d) return;
    const max = Math.max(...d.valeurs);
    new Chart(cv, {
      type: "bar",
      data: { labels: d.annees, datasets: [{ data: d.valeurs, backgroundColor: d.valeurs.map((v) => (v === max && v > 0 ? d.couleur : hexA(d.couleur, 0.32))), borderRadius: 8, maxBarThickness: 56 }] },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${nf(c.raw, c.raw < 1 ? 3 : 1)} Md FCFA` } } },
        scales: { x: { grid: { display: false }, border: { display: false }, ticks: { color: INK } }, y: { beginAtZero: true, grid: { color: LINE }, border: { display: false }, ticks: { maxTicksLimit: 5, callback: (v) => nf(v, v < 10 ? 1 : 0) } } },
      },
    });
  });

  /* Tendances : programmation annuelle par pilier, dynamique des actions */
  const T = data("graph-tendances");
  if (T) {
    const yCv = $("#chart-annees");
    if (yCv) new Chart(yCv, {
      type: "bar",
      data: { labels: T.annees, datasets: T.piliers.map((p) => ({ label: `Pilier ${p.numero}`, data: p.annuel, backgroundColor: p.couleur, borderColor: "#fff", borderWidth: { top: 1.5 }, maxBarThickness: 64, borderRadius: 2 })) },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { mode: "index", callbacks: { title: (c) => `Programmation ${c[0].label}`, label: (c) => ` ${c.dataset.label} : ${nf(c.raw, 0)} Md FCFA`, footer: (c) => `Total : ${nf(c.reduce((s, x) => s + x.raw, 0), 0)} Md FCFA` } } },
        scales: { x: { stacked: true, grid: { display: false }, border: { display: false }, ticks: { color: INK } }, y: { stacked: true, grid: { color: LINE }, border: { display: false }, ticks: { maxTicksLimit: 5, callback: mdTick } } },
      },
    });
    const tCv = $("#chart-dynamique");
    if (tCv) {
      const col = { "Nouvelle": "#f77f00", "Hausse forte": "#006e47", "Hausse": "#2fc08a", "Stable": "#a9b2be", "Baisse": "#d08a80" };
      new Chart(tCv, {
        type: "doughnut",
        data: { labels: T.tendances.map((t) => t.nom), datasets: [{ data: T.tendances.map((t) => t.n), backgroundColor: T.tendances.map((t) => col[t.nom]), borderColor: "#fff", borderWidth: 3 }] },
        options: { maintainAspectRatio: false, cutout: "64%", plugins: { legend: { position: mobile() ? "bottom" : "right", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, color: INK, padding: 12 } }, tooltip: { callbacks: { label: (c) => ` ${c.label} : ${nf(c.raw, 0)} actions, ${nf(T.tendances[c.dataIndex].v, 0)} Md FCFA` } } } },
      });
    }
  }
})();
