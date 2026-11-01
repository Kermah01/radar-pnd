/* Radar PND : interactions légères (amélioration progressive, tout fonctionne sans JavaScript). */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ($("[name=csrfmiddlewaretoken]") || {}).value || "";
  const nf = (v, d) => Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d == null ? 1 : d }).replace(/\u202f/g, "\u00a0");

  function toast(msg) {
    let t = $("#toast");
    if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = msg; t.hidden = false;
    clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 2200);
  }

  /* Menu mobile */
  const mb = $(".menu-btn"), nav = $("#nav");
  if (mb && nav) mb.addEventListener("click", () => { const o = nav.classList.toggle("open"); mb.setAttribute("aria-expanded", o); });

  /* Sur petit écran, la liste des secteurs suivis est repliée pour laisser voir les résultats */
  if (window.matchMedia("(max-width: 900px)").matches) $$("details.secs").forEach((d) => d.removeAttribute("open"));

  /* Profil du radar : mise à jour automatique */
  const pf = $("#profil-form");
  if (pf) {
    let h;
    const submit = () => { clearTimeout(h); h = setTimeout(() => pf.submit(), 250); };
    pf.addEventListener("change", (e) => {
      if (e.target.name === "type") { $("#appliquer_preset").value = "1"; pf.submit(); return; }
      submit();
    });
  }

  /* Ajout / retrait de la sélection sans rechargement */
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
      });
      const c = $("#sel-count");
      if (c) { c.textContent = d.count; c.hidden = !d.count; }
      toast(d.selected ? "Ajoutée à votre sélection" : "Retirée de votre sélection");
    } catch (err) { f.submit(); }
  });

  /* Copier un paragraphe */
  function copyText(txt, el) {
    const done = () => toast("Texte copié dans le presse-papiers");
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(txt).then(done, () => selectEl(el));
    } else selectEl(el);
  }
  function selectEl(el) {
    if (!el) return;
    const r = document.createRange(); r.selectNodeContents(el);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    toast("Texte sélectionné : copiez-le avec Ctrl+C");
  }
  $$("[data-copy]").forEach((b) => b.addEventListener("click", () => {
    const el = document.getElementById(b.dataset.copy);
    if (el) copyText(el.dataset.text || el.innerText, el);
  }));

  /* Notes de sélection : enregistrement automatique */
  $$("form.js-note").forEach((f) => {
    const ta = f.querySelector("textarea"), ok = f.querySelector(".saved");
    let h;
    const save = async () => {
      const body = new FormData(f);
      try {
        const r = await fetch(f.action, { method: "POST", body, headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" }, credentials: "same-origin" });
        if (r.ok && ok) { ok.classList.add("on"); setTimeout(() => ok.classList.remove("on"), 1600); }
      } catch (e) { /* le bouton reste disponible */ }
    };
    ta.addEventListener("input", () => { clearTimeout(h); h = setTimeout(save, 900); });
    f.addEventListener("submit", (e) => { e.preventDefault(); save(); });
  });

  /* Lignes de tableau cliquables */
  document.addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-href]");
    if (!tr || e.target.closest("a,button,form")) return;
    window.location = tr.dataset.href;
  });

  /* ---------------------------------------------------------------- graphiques */
  if (!window.Chart) return;
  const css = getComputedStyle(document.documentElement);
  const INK = css.getPropertyValue("--ink").trim() || "#152233";
  const MUTED = css.getPropertyValue("--muted").trim() || "#5d6878";
  const LINE = css.getPropertyValue("--line-2").trim() || "#eeece6";
  Chart.defaults.font.family = css.getPropertyValue("--f-ui");
  Chart.defaults.font.size = 12;
  Chart.defaults.color = MUTED;
  Chart.defaults.plugins.tooltip.backgroundColor = INK;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "600" };
  Chart.defaults.animation.duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 500;
  const data = (id) => { const el = document.getElementById(id); return el ? JSON.parse(el.textContent) : null; };
  const mdTick = (v) => nf(v, 0);
  const hexA = (hex, a) => { const h = hex.replace("#", ""); const n = parseInt(h, 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; };
  const isSmall = () => window.matchMedia("(max-width: 560px)").matches;

  /* Programmation annuelle d'un pilier, d'un secteur ou d'une action (Md FCFA) */
  $$("canvas[data-chart=annuel]").forEach((cv) => {
    const d = data(cv.dataset.src); if (!d) return;
    const max = Math.max(...d.valeurs);
    new Chart(cv, {
      type: "bar",
      data: { labels: d.annees, datasets: [{ data: d.valeurs, backgroundColor: d.valeurs.map((v) => (v === max && v > 0 ? d.couleur : hexA(d.couleur, 0.35))), borderRadius: 4, maxBarThickness: 64 }] },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${nf(c.raw, c.raw < 1 ? 3 : 1)} Md FCFA` } } },
        scales: { x: { grid: { display: false }, ticks: { color: INK } }, y: { beginAtZero: true, grid: { color: LINE }, border: { display: false }, ticks: { callback: (v) => nf(v, v < 10 ? 1 : 0) }, title: { display: true, text: "Md FCFA" } } },
      },
    });
  });

  /* Tendances */
  const T = data("graph-tendances");
  if (T) {
    const secCv = $("#chart-secteurs");
    let secChart;
    const drawSec = (mode) => {
      const rows = mode === "growth" ? T.secteurs_croissance : T.secteurs_total;
      const cfg = {
        type: "bar",
        data: { labels: rows.map((r) => r.nom), datasets: [{ data: rows.map((r) => r.v), backgroundColor: rows.map((r) => r.c), borderRadius: 3, barThickness: isSmall() ? 14 : 16 }] },
        options: {
          indexAxis: "y", maintainAspectRatio: false,
          onClick: (e, els) => { if (els.length) window.location = rows[els[0].index].url; },
          onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => `${rows[c[0].dataIndex].code} ${rows[c[0].dataIndex].nom}`, label: (c) => (mode === "growth" ? ` x ${nf(c.raw, 1)} entre 2026 et 2030` : ` ${nf(c.raw, 0)} Md FCFA`) } } },
          scales: {
            x: mode === "growth" ? { type: "logarithmic", grid: { color: LINE }, border: { display: false }, ticks: { callback: (v) => ([1, 2, 5, 10, 20, 50, 100].includes(v) ? "x " + v : "") } } : { grid: { color: LINE }, border: { display: false }, ticks: { callback: mdTick } },
            y: { grid: { display: false }, ticks: { color: INK, autoSkip: false, callback: function (v) { const l = this.getLabelForValue(v); const m = isSmall() ? 18 : 30; return l.length > m ? l.slice(0, m - 1) + "…" : l; } } },
          },
        },
      };
      if (secChart) secChart.destroy();
      secChart = new Chart(secCv, cfg);
      $("#note-secteurs").textContent = mode === "growth" ? "Rapport entre la programmation 2030 et 2026, secteurs de plus de 50 Md FCFA. Échelle logarithmique." : "Les 20 secteurs les plus dotés sur 2026-2030, en milliards de FCFA.";
    };
    if (secCv) {
      drawSec("total");
      $$("#seg-secteurs button").forEach((b) => b.addEventListener("click", () => { $$("#seg-secteurs button").forEach((x) => x.setAttribute("aria-pressed", x === b)); drawSec(b.dataset.m); }));
    }
    const yCv = $("#chart-annees");
    if (yCv) new Chart(yCv, {
      type: "bar",
      data: { labels: T.annees, datasets: T.piliers.map((p) => ({ label: `Pilier ${p.numero}`, data: p.annuel, backgroundColor: p.couleur, borderColor: "#fff", borderWidth: { top: 1 }, maxBarThickness: 70 })) },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { mode: "index", callbacks: { title: (c) => `Programmation ${c[0].label}`, label: (c) => ` ${c.dataset.label} : ${nf(c.raw, 0)} Md FCFA`, footer: (c) => `Total : ${nf(c.reduce((s, x) => s + x.raw, 0), 0)} Md FCFA` } } },
        scales: { x: { stacked: true, grid: { display: false }, ticks: { color: INK } }, y: { stacked: true, grid: { color: LINE }, border: { display: false }, ticks: { callback: mdTick }, title: { display: true, text: "Md FCFA" } } },
      },
    });
    const fCv = $("#chart-familles");
    if (fCv) new Chart(fCv, {
      type: "bar",
      data: { labels: T.familles.map((f) => f.nom), datasets: [{ data: T.familles.map((f) => f.v), backgroundColor: T.familles.map((f, i) => (i === 0 ? "#f77f00" : i < 3 ? hexA("#f77f00", 0.7) : hexA("#152233", 0.75))), borderRadius: 3, barThickness: 14 }] },
      options: {
        indexAxis: "y", maintainAspectRatio: false,
        onClick: (e, els) => { if (els.length) window.location = `/explorer/?famille=${T.familles[els[0].index].slug}`; },
        onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${nf(c.raw, 0)} Md FCFA` } } },
        scales: { x: { grid: { color: LINE }, border: { display: false }, ticks: { callback: mdTick } }, y: { grid: { display: false }, ticks: { color: INK, autoSkip: false, callback: function (v) { const l = this.getLabelForValue(v); const m = isSmall() ? 22 : 40; return l.length > m ? l.slice(0, m - 1) + "…" : l; } } } },
      },
    });
    const tCv = $("#chart-dynamique");
    if (tCv) {
      const col = { "Nouvelle": "#f77f00", "Hausse forte": "#00704a", "Hausse": "#3fb183", "Stable": "#a7aeb8", "Baisse": "#c98a83" };
      new Chart(tCv, {
        type: "doughnut",
        data: { labels: T.tendances.map((t) => t.nom), datasets: [{ data: T.tendances.map((t) => t.n), backgroundColor: T.tendances.map((t) => col[t.nom]), borderColor: "#fff", borderWidth: 2 }] },
        options: { maintainAspectRatio: false, cutout: "62%", plugins: { legend: { position: isSmall() ? "bottom" : "right", labels: { boxWidth: 10, boxHeight: 10, color: INK } }, tooltip: { callbacks: { label: (c) => ` ${c.label} : ${nf(c.raw, 0)} actions, ${nf(T.tendances[c.dataIndex].v, 0)} Md FCFA` } } } },
      });
    }
  }
})();
