/*
 * IT Helpdesk Portal — Support homepage (Service Catalogue tab)
 * -------------------------------------------------------------
 * Adds the live parts of the homepage whose static markup is in index.html:
 * greeting, guide search with suggestions, known-issue banner, "your
 * activity" counts, popular guides and the contact panel.
 *
 * Sign-in: the portal signs people in with a pop-up, which browsers only allow
 * after a click or key press. So nothing here calls the API on page load
 * unless the person is already signed in; otherwise the activity strip offers
 * a "Sign in" button, and searching (a key press) signs in as it goes.
 *
 * Depends on index.html globals: apiCall(), getSession(), signedInAccount,
 * TERMINAL_STATES, and window.KnowledgeBase (web/knowledge/knowledge.js).
 */
(function () {
  "use strict";

  // Contact details shown in the "Need to talk to someone?" panel. Leave a
  // field empty to hide that line. [Set these once the helpdesk details are confirmed.]
  const SUPPORT_CONTACT = {
    email: "",      // e.g. "itsupport@cognitionlearninggroup.com"
    phone: "",      // e.g. "+44 161 000 0000"
    hours: "",      // e.g. "Monday to Friday, 8:30am to 5:30pm UK time"
    portalUrl: "",  // e.g. the Zoho Desk help centre link
  };

  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ICON = {
    request: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 13h6M9 17h4"/></svg>',
    approve: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
    device: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M2 20h20"/></svg>',
    guide: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5V5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2z"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
    mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
  };
  let loaded = false, loading = false;

  const signedIn = () => typeof signedInAccount !== "undefined" && !!signedInAccount;
  const firstName = () => {
    if (!signedIn()) return "";
    const n = (signedInAccount.name || "").trim();
    if (n && !n.includes("@")) return n.split(/\s+/)[0];
    const u = (signedInAccount.username || "").split("@")[0].split(/[._]/)[0];
    return u ? u.charAt(0).toUpperCase() + u.slice(1) : "";
  };
  const gotoTab = (view) => { const b = document.querySelector(`.tab-btn[data-view="${view}"]`); if (b) b.click(); };

  // ----------------------------------------------------------------- render
  function renderGreeting() {
    const n = firstName();
    $("#shTitle").textContent = n ? `Hi ${n}, how can we help today?` : "How can we help today?";
  }

  function renderContact() {
    const c = SUPPORT_CONTACT, rows = [];
    if (c.email) rows.push(`<div class="row">${ICON.mail}<a href="mailto:${esc(c.email)}" style="color:#fff;">${esc(c.email)}</a></div>`);
    if (c.phone) rows.push(`<div class="row">${ICON.phone}<a href="tel:${esc(c.phone.replace(/\s/g, ""))}" style="color:#fff;">${esc(c.phone)}</a></div>`);
    if (c.hours) rows.push(`<div class="row" style="color:#e3e3e3;">${ICON.clock}${esc(c.hours)}</div>`);
    if (c.portalUrl) rows.push(`<div class="row">${ICON.link}<a href="${esc(c.portalUrl)}" target="_blank" rel="noopener" style="color:#fff;">IT helpdesk portal</a></div>`);
    $("#shContact").innerHTML = `<h3>Need to talk to someone?</h3>
      <p>Most things can be fixed with a guide or a request above. If you're stuck, or something is urgent such as a lost device or a suspected security incident, contact the IT team straight away.</p>
      ${rows.join("")}`;
  }

  function renderActivity(state) {
    const el = $("#shActivity");
    if (state === "signin") {
      el.innerHTML = `<div class="sh-signin"><span>Sign in to see your requests, approvals and devices.</span>
        <button type="button" class="btn btn-primary" data-sh-signin>Sign in</button></div>`;
      return;
    }
    const card = (view, icon, n, label, alert) => `<button type="button" class="sh-act ${alert ? "is-alert" : ""}" data-sh-tab="${view}">
      <span class="ic">${ICON[icon]}</span><span><div class="n">${n}</div><div class="l">${label}</div></span></button>`;
    const v = state || {};
    const show = (x) => (x == null ? "–" : x);
    el.innerHTML = card("myRequests", "request", show(v.open), v.open === 1 ? "open request" : "open requests")
      + card("myApprovals", "approve", show(v.approvals), v.approvals === 1 ? "approval waiting for you" : "approvals waiting for you", v.approvals > 0)
      + card("myDevices", "device", show(v.devices), v.devices === 1 ? "device registered to you" : "devices registered to you");
  }

  function renderGuides(home) {
    const list = (home.popular && home.popular.length ? home.popular : home.recent || []).slice(0, 6);
    $("#shGuides").innerHTML = list.length ? list.map((a) => `<li><button type="button" data-sh-article="${esc(a.articleId)}">
        <span class="gi">${ICON.guide}</span><span><div class="gt">${esc(a.title)}</div><div class="gs">${esc(a.summary)}</div></span><span class="ga">&rsaquo;</span></button></li>`).join("")
      : `<li class="sh-empty">No guides are published yet.</li>`;
    const issue = (home.knownIssues || [])[0];
    $("#shIssue").innerHTML = issue ? `<div class="sh-issue" role="status">${ICON.alert}<span><b>Known issue:</b> ${esc(issue.title)}</span>
        <button type="button" data-sh-article="${esc(issue.articleId)}">Read more &rarr;</button></div>` : "";
  }

  // ----------------------------------------------------------------- data
  async function load() {
    if (loading) return;
    loading = true;
    renderActivity({});
    const session = getSession();
    const settle = (p) => p.then((v) => v, () => null);
    const [reqs, appr, devs, home] = await Promise.all([
      settle(apiCall(`/workflow/myRequests?requesterUpn=${encodeURIComponent(session.upn)}`)),
      settle(apiCall(`/workflow/myApprovals?role=${encodeURIComponent(session.role)}`)),
      settle(apiCall(`/cmdb/ci?class=Hardware&owner=${encodeURIComponent(session.upn)}`)),
      settle(apiCall("/knowledge/home")),
    ]);
    const terminal = typeof TERMINAL_STATES !== "undefined" ? TERMINAL_STATES : {};
    renderActivity({
      open: reqs ? reqs.instances.filter((i) => !terminal[i.currentState]).length : null,
      approvals: appr ? appr.instances.length : null,
      devices: devs ? devs.items.length : null,
    });
    if (home) renderGuides(home);
    renderGreeting();
    loaded = !!(reqs || home);
    loading = false;
  }

  // Suggestions while typing (not logged; only full searches count as demand).
  let timer = null, idx = -1;
  function suggest(q) {
    clearTimeout(timer);
    const box = $("#shSuggest");
    if (q.trim().length < 2) { box.hidden = true; return; }
    timer = setTimeout(async () => {
      try {
        const r = await apiCall(`/knowledge/search?q=${encodeURIComponent(q)}&log=false`);
        if ($("#shQ").value !== q) return;
        idx = -1;
        box.innerHTML = r.results.slice(0, 5).map((a) => `<button type="button" role="option" data-sh-article="${esc(a.articleId)}"><div class="t">${esc(a.title)}</div><div class="s">${esc(a.summary)}</div></button>`).join("")
          + `<button type="button" class="all" data-sh-search>${r.results.length ? "See all results" : "No guides match yet. Search anyway"} for “${esc(q)}”</button>`;
        box.hidden = false;
        if (!loaded) load();  // the search signed them in; fill in the rest of the page
      } catch (e) { /* best-effort */ }
    }, 220);
  }
  function search(q) {
    q = (q || "").trim(); if (q.length < 2) return;
    clearTimeout(timer); $("#shSuggest").hidden = true;
    gotoTab("knowledgeBase");
    if (window.KnowledgeBase && window.KnowledgeBase.search) window.KnowledgeBase.search(q);
  }
  function openArticle(id) {
    gotoTab("knowledgeBase");
    if (window.KnowledgeBase && window.KnowledgeBase.openArticle) window.KnowledgeBase.openArticle(id);
  }

  // ----------------------------------------------------------------- events
  function bind() {
    const view = document.getElementById("view-catalogue");
    view.addEventListener("click", (ev) => {
      const t = ev.target.closest("button"); if (!t) return;
      const d = t.dataset;
      if (d.shTab) return gotoTab(d.shTab);
      if (d.shArticle) return openArticle(d.shArticle);
      if (d.shQ) return search(d.shQ);
      if (d.shSearch !== undefined) return search($("#shQ").value);
      if (d.shSignin !== undefined) return load();
      // Service cards that open a form on this page: the original handlers toggle
      // the form; here we highlight the card and bring the form into view.
      const forms = { "tile-hardware": "hwRequestForm", "tile-sspr": "ssprPanel" };
      if (forms[t.id]) {
        const form = document.getElementById(forms[t.id]);
        setTimeout(() => {
          const open = form.style.display !== "none";
          document.querySelectorAll(".sh-svc").forEach((c) => c.classList.remove("is-open"));
          t.classList.toggle("is-open", open);
          t.setAttribute("aria-expanded", String(open));
          if (open) form.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 0);
      }
    });
    const q = $("#shQ");
    q.addEventListener("input", () => suggest(q.value));
    q.addEventListener("keydown", (ev) => {
      const box = $("#shSuggest"), opts = box.hidden ? [] : [...box.querySelectorAll("button")];
      if (ev.key === "ArrowDown" && opts.length) { ev.preventDefault(); idx = (idx + 1) % opts.length; }
      else if (ev.key === "ArrowUp" && opts.length) { ev.preventDefault(); idx = (idx - 1 + opts.length) % opts.length; }
      else if (ev.key === "Enter") { ev.preventDefault(); if (idx >= 0 && opts[idx]) opts[idx].click(); else search(q.value); return; }
      else if (ev.key === "Escape") { box.hidden = true; return; }
      else return;
      opts.forEach((o, i) => o.classList.toggle("is-active", i === idx));
    });
    document.addEventListener("click", (ev) => { if (!ev.target.closest(".sh-search")) $("#shSuggest").hidden = true; });
  }

  function init() {
    bind();
    renderGreeting();
    renderContact();
    renderActivity(signedIn() ? {} : "signin");
    if (signedIn()) { load(); return; }
    // The portal checks for an existing sign-in in the background on page load.
    // If that finds one, fill the page in without needing a click.
    let tries = 0;
    const watch = setInterval(() => {
      if (signedIn()) { clearInterval(watch); if (!loaded) load(); }
      else if (++tries > 30) clearInterval(watch);
    }, 500);
  }

  window.SupportHome = {
    open: function () { renderGreeting(); if (signedIn() && !loading) load(); else if (!loaded) renderActivity("signin"); },
  };
  if (document.getElementById("view-catalogue")) init();
})();
