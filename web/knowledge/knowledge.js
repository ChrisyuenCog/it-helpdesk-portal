/*
 * IT Helpdesk Portal — Knowledge Base v2
 * --------------------------------------
 * Browse    search with suggestions, categories, popular, recent, known issues
 * Article   rendered guide, evidence, related articles, structured feedback,
 *           shareable link (#kb/<articleId>)
 * Manage    every article with status; edit with live preview; approve
 * Insights  zero-result searches, lowest rated, reasons, overdue reviews
 *
 * Depends on index.html globals apiCall() and switching tabs via .tab-btn.
 * Article bodies are rendered by renderBody(): text is escaped FIRST and only a
 * small, fixed set of formatting is then applied, so stored content can never
 * inject HTML or script. Links are limited to https: and mailto:.
 */
(function () {
  "use strict";

  const TYPE_CLASS = { "Known issue": "known", "Policy summary": "policy", "Troubleshooting": "trouble" };
  const REASONS = { outdated: "It's out of date", unclear: "It's unclear", did_not_solve: "It didn't solve my problem", other: "Something else" };
  const state = { view: "browse", page: "home", home: null, category: null, results: null, query: "", article: null,
                  manage: null, mFilter: { q: "", status: "", category: "" }, insights: null, evidence: null, error: "" };

  const $ = (s, r = document) => r.querySelector(s);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtDate = (iso) => { if (!iso) return ""; const s = String(iso); const m = Number(s.slice(5, 7)); return m ? `${Number(s.slice(8, 10))} ${MONTHS[m - 1]} ${s.slice(0, 4)}` : s; };
  const hasConfirm = (t) => /\[confirm/i.test(t || "");
  const api = (p, o) => apiCall(p, o);
  function toast(msg) { const el = document.createElement("div"); el.className = "tp-toast"; el.setAttribute("role", "status"); el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 2600); }
  const typeBadge = (t) => `<span class="kb-type ${TYPE_CLASS[t] || ""}">${esc(t)}</span>`;
  const root = () => document.getElementById("knowledgeApp");
  let suggestTimer = null, suggestIdx = -1;

  // --------------------------------------------------------- safe body renderer
  function inline(s) {
    return s
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+|mailto:[^\s)]+)\)/g, (m, t, u) => `<a href="${u}" target="_blank" rel="noopener">${t}</a>`)
      .replace(/\[confirm:([^\]]*)\]/gi, '<span class="kb-confirm">[confirm:$1]</span>');
  }
  function renderBody(text) {
    const lines = esc(text || "").split(/\r?\n/);
    let html = "", list = null, para = [];
    const flushPara = () => { if (para.length) { html += `<p>${inline(para.join(" "))}</p>`; para = []; } };
    const flushList = () => { if (list) { html += `</${list}>`; list = null; } };
    for (const raw of lines) {
      const line = raw.trim();
      let m;
      if (!line) { flushPara(); flushList(); continue; }
      if ((m = line.match(/^##\s+(.*)/))) { flushPara(); flushList(); html += `<h2>${inline(m[1])}</h2>`; continue; }
      if ((m = line.match(/^&gt;\s?(.*)/))) { flushPara(); flushList(); html += `<blockquote>${inline(m[1])}</blockquote>`; continue; }
      if ((m = line.match(/^\d+\.\s+(.*)/))) { flushPara(); if (list !== "ol") { flushList(); html += "<ol>"; list = "ol"; } html += `<li>${inline(m[1])}</li>`; continue; }
      if ((m = line.match(/^[-*]\s+(.*)/))) { flushPara(); if (list !== "ul") { flushList(); html += "<ul>"; list = "ul"; } html += `<li>${inline(m[1])}</li>`; continue; }
      flushList(); para.push(line);
    }
    flushPara(); flushList();
    return html;
  }

  // --------------------------------------------------------------- rendering
  function render() {
    const r = root(); if (!r) return;
    const seg = (id, label) => `<button type="button" data-kb-view="${id}" aria-pressed="${state.view === id}">${label}</button>`;
    r.innerHTML = `
      <div class="tp-head"><div><h1>Knowledge Base</h1><p>Step-by-step guides to fix common IT problems yourself, written and checked by CLG IT.</p></div>
        <div class="tp-seg" role="group" aria-label="Knowledge Base sections">${seg("browse", "Browse")}${seg("manage", "Manage articles")}${seg("insights", "Insights")}</div></div>
      ${state.error ? `<div class="error-box" role="alert">${esc(state.error)}</div>` : ""}
      <div id="kbBody">${state.view === "browse" ? renderBrowse() : state.view === "manage" ? renderManage() : renderInsights()}</div>`;
  }

  function itemList(items, empty) {
    if (!items || !items.length) return `<p class="tp-hint">${empty}</p>`;
    return `<ul class="kb-list">${items.map((a) => `<li><button type="button" class="kb-item" data-kb-open="${esc(a.articleId)}">
      <div class="kb-item-t">${esc(a.title)}</div><div class="kb-item-s">${esc(a.summary)}</div>
      <div class="kb-item-m">${typeBadge(a.articleType)}<span>${esc(a.category)}</span>${a.status && a.status !== "Approved" ? `<span class="tp-status needs_review">${esc(a.status)}</span>` : ""}</div>
    </button></li>`).join("")}</ul>`;
  }

  function searchBox() {
    return `<div class="kb-search"><input id="kbQ" type="search" autocomplete="off" value="${esc(state.query)}" placeholder="Describe your problem, for example: forgot password, laptop stolen, 2FA"
      aria-label="Search the knowledge base" aria-autocomplete="list" aria-controls="kbSuggest"><div id="kbSuggest" class="kb-suggest" hidden></div></div>`;
  }

  function renderBrowse() {
    if (state.page === "article") return renderArticle();
    if (state.page === "category") return `<div class="kb-crumbs"><button type="button" data-kb-home>Knowledge Base</button> › ${esc(state.category.category)}</div>
      <div class="card"><h2 style="margin-top:0;">${esc(state.category.category)}</h2>${itemList(state.category.articles, "No published articles in this category yet.")}</div>`;
    if (state.page === "results") return `<div class="kb-hero"><h2>How can we help?</h2><p>Search ${state.home ? state.home.total : ""} guides written by CLG IT.</p>${searchBox()}</div>
      <div class="card"><h2 style="margin-top:0;">${state.results.count} result${state.results.count === 1 ? "" : "s"} for “${esc(state.results.query)}”</h2>
      ${state.results.count ? itemList(state.results.results) : `<p>No guides match that yet. Try different words, or contact the IT helpdesk.</p>
        <p class="tp-hint">Searches with no results are reported to IT anonymously, so the most-needed guides get written next.</p>`}</div>`;
    const h = state.home;
    if (!h) return `<div class="card"><div class="tp-empty">Loading the knowledge base…</div></div>`;
    return `<div class="kb-hero"><h2>How can we help?</h2><p>Search ${h.total} guide${h.total === 1 ? "" : "s"} written by CLG IT, or browse by topic.</p>${searchBox()}</div>
      ${(h.knownIssues || []).map((a) => `<div class="kb-issue" role="status"><strong>Known issue:</strong><span>${esc(a.title)}. <button type="button" class="tp-link" data-kb-open="${esc(a.articleId)}">Read more</button></span></div>`).join("")}
      ${h.total ? `<div class="kb-cats">${h.categories.map((c) => `<button type="button" class="kb-cat" data-kb-cat="${esc(c.name)}"><div class="n">${esc(c.name)}</div><div class="c">${c.count} guide${c.count === 1 ? "" : "s"}</div></button>`).join("")}</div>
      <div class="kb-cols"><div class="card"><h2 style="margin-top:0;font-size:1rem;">Most viewed</h2>${itemList(h.popular, "Popular guides appear here once people start reading.")}</div>
        <div class="card"><h2 style="margin-top:0;font-size:1rem;">Recently updated</h2>${itemList(h.recent, "Nothing yet.")}</div></div>`
      : `<div class="card"><div class="tp-empty">No guides are published yet. IT can review and publish the starter articles under <b>Manage articles</b>.</div></div>`}`;
  }

  function renderArticle() {
    const { article: a, rating, related, preview } = state.article;
    const evidence = (a.evidence || []).map((k) => `<span class="tp-chip ok">${esc(k)}</span>`).join(" ");
    return `<div class="kb-crumbs"><button type="button" data-kb-home>Knowledge Base</button> › <button type="button" data-kb-cat="${esc(a.category)}">${esc(a.category)}</button></div>
      <div class="kb-article-wrap"><article class="card kb-article">
        ${a.status !== "Approved" ? `<div class="kb-banner draft">${esc(a.status)} — not visible to staff until it is approved.${hasConfirm(a.body) ? " Replace the highlighted [confirm] text before approving." : ""}</div>` : ""}
        ${a.reviewOverdue ? `<div class="kb-banner overdue">This article was due for review on ${esc(fmtDate(a.reviewDate))}. Some details may be out of date.</div>` : ""}
        ${typeBadge(a.articleType)}<h1>${esc(a.title)}</h1><p class="kb-lede">${esc(a.summary)}</p>
        <div class="kb-meta"><span>Updated ${esc(fmtDate(a.updatedAt))}</span><span>Version ${a.version}</span><span>Owner: ${esc(a.owner)}</span>
          ${a.reviewDate ? `<span>Next review ${esc(fmtDate(a.reviewDate))}</span>` : ""}${a.audience === "IT only" ? "<span><b>IT only</b></span>" : ""}</div>
        <div class="kb-body">${renderBody(a.body)}</div>
        ${preview ? "" : `<div class="kb-feedback" id="kbFeedback">${feedbackForm()}</div>`}
      </article>
      <aside class="kb-side">
        <div class="card"><h3>Share this guide</h3><button type="button" class="btn tp-btn-ghost" style="margin:0;width:100%;" data-kb-copy="${esc(a.articleId)}">Copy link</button></div>
        ${evidence ? `<div class="card"><h3>Based on</h3><div class="tp-chips">${evidence}</div></div>` : ""}
        ${rating && rating.votes ? `<div class="card"><h3>Ratings</h3><p class="tp-hint" style="margin:0;">${rating.helpfulPercent}% found this helpful (${rating.votes} vote${rating.votes === 1 ? "" : "s"})</p></div>` : ""}
        ${related && related.length ? `<div class="card"><h3>Related guides</h3>${itemList(related)}</div>` : ""}
      </aside></div>`;
  }

  function feedbackForm(stage) {
    if (stage === "thanks") return `<h3>Thanks for your feedback</h3><p class="tp-hint" style="margin:0;">It goes straight to the article's owner in IT.</p>`;
    if (stage === "no") return `<h3>Sorry about that. What went wrong?</h3>
      <div class="kb-reasons" role="radiogroup">${Object.entries(REASONS).map(([k, v]) => `<label><input type="radio" name="kbReason" value="${k}"> ${v}</label>`).join("")}</div>
      <textarea id="kbComment" placeholder="Optional: tell IT what was missing or wrong" aria-label="Comment"></textarea>
      <div class="tp-actions" style="margin-top:.6rem;"><button type="button" class="btn btn-primary" data-kb-fb-send>Send feedback</button></div>`;
    return `<h3>Did this guide solve your problem?</h3><div class="tp-actions">
      <button type="button" class="btn btn-primary" data-kb-fb="yes">Yes</button><button type="button" class="btn tp-btn-ghost" data-kb-fb="no">No</button></div>`;
  }

  // ------------------------------------------------------------------ manage
  function renderManage() {
    if (!state.manage) return `<div class="card"><div class="tp-empty">Loading articles…</div></div>`;
    const f = state.mFilter, q = f.q.toLowerCase();
    const cats = [...new Set(state.manage.map((a) => a.category))].sort();
    const rows = state.manage.filter((a) => (!f.status || a.status === f.status) && (!f.category || a.category === f.category)
      && (!q || (a.title + " " + a.summary + " " + a.keywords.join(" ")).toLowerCase().includes(q)));
    const counts = ["Approved", "Draft", "Retired"].map((s) => `${state.manage.filter((a) => a.status === s).length} ${s.toLowerCase()}`).join(" · ");
    return `<div class="card"><p class="tp-hint" style="margin:0 0 .75rem;">${state.manage.length} articles: ${counts}. Staff see only approved articles. Articles with [confirm] text can't be approved until it's replaced.</p>
      <div class="tp-toolbar"><input type="search" data-kb-mf="q" value="${esc(f.q)}" placeholder="Search titles, summaries and keywords" aria-label="Filter articles">
        <select data-kb-mf="category" aria-label="Category"><option value="">All categories</option>${cats.map((c) => `<option ${c === f.category ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <select data-kb-mf="status" aria-label="Status"><option value="">All statuses</option>${["Approved", "Draft", "Retired"].map((s) => `<option ${s === f.status ? "selected" : ""}>${s}</option>`).join("")}</select>
        <button type="button" class="btn btn-primary" data-kb-new>New article</button></div>
      <div class="tp-table-wrap"><table class="tp-table"><thead><tr><th>Article</th><th>Type</th><th>Status</th><th>Views</th><th>Helpful</th><th>Updated</th><th></th></tr></thead><tbody>
      ${rows.length ? rows.map((a) => `<tr><td><span class="tp-cat">${esc(a.category)}${a.audience === "IT only" ? " · IT only" : ""}</span><span class="tp-q-cell">${esc(a.title)}</span></td>
        <td>${typeBadge(a.articleType)}</td>
        <td><span class="tp-status ${a.status === "Approved" ? "ready" : a.status === "Retired" ? "unmatched" : "needs_review"}">${esc(a.status)}</span><span class="tp-hint" style="display:block;">v${a.version}</span></td>
        <td>${a.views}</td><td>${a.votes ? `${a.helpfulPercent}% <span class="tp-hint" style="margin:0;">(${a.votes})</span>` : "–"}</td>
        <td style="white-space:nowrap;font-size:.8rem;color:var(--muted);">${esc(fmtDate(a.updatedAt))}<br>${esc(a.updatedBy || "Starter set")}</td>
        <td class="tp-row-actions"><button type="button" class="tp-link" data-kb-preview="${esc(a.articleId)}">View</button><button type="button" class="tp-link" data-kb-edit="${esc(a.articleId)}">Edit</button>
          ${a.status === "Draft" ? `<button type="button" class="tp-link" data-kb-approve="${esc(a.articleId)}">Approve</button>` : ""}</td></tr>`).join("")
        : `<tr><td colspan="7"><div class="tp-empty">No articles match these filters.</div></td></tr>`}</tbody></table></div></div>`;
  }

  async function openEditor(articleId) {
    let a = { articleId: "", title: "", summary: "", category: "", articleType: "How-to", audience: "All staff", body: "", keywords: [], evidence: [], reviewDate: "", status: "Draft" };
    try {
      if (articleId) a = (await api(`/knowledge/articles/${encodeURIComponent(articleId)}?drafts=true`)).article;
      if (!state.evidence) state.evidence = (await api("/tender/evidence")).evidence || [];
    } catch (e) { toast(e.message); return; }
    const cats = [...new Set((state.manage || []).map((x) => x.category))].sort();
    const sel = (id, opts, v) => `<select id="${id}">${opts.map((o) => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select>`;
    // Same rule as the API: exact title first, else the shortest title starting
    // with the key, so "Cyber Essentials" never ticks "Cyber Essentials Plus".
    const resolve = (k) => { const key = String(k).toLowerCase();
      return state.evidence.find((d) => d.title.toLowerCase() === key)
        || state.evidence.filter((d) => d.title.toLowerCase().startsWith(key)).sort((x, y) => x.title.length - y.title.length)[0]; };
    const evSel = new Set(a.evidence.map(resolve).filter(Boolean).map((d) => d.title));
    const ev = state.evidence.map((d) => `<label><input type="checkbox" name="kbEv" value="${esc(d.title)}" ${evSel.has(d.title) ? "checked" : ""}> <span>${esc(d.title)}</span></label>`).join("");
    const m = document.createElement("div");
    m.className = "tp-modal"; m.id = "kbModal";
    m.innerHTML = `<div class="tp-modal-box wide" role="dialog" aria-modal="true" aria-labelledby="kbEdT" style="background:#fff;">
      <div class="tp-modal-head"><h2 id="kbEdT">${articleId ? "Edit article" : "New article"}</h2><button type="button" class="tp-close" data-kb-close aria-label="Close">×</button></div>
      <div class="tp-modal-body"><div class="tp-form">
        <div class="tp-field tp-full"><label for="edTitle">Title</label><input id="edTitle" value="${esc(a.title)}" placeholder="Start with what the reader wants to do, e.g. Reset your password"></div>
        <div class="tp-field tp-full"><label for="edSum">Summary</label><input id="edSum" value="${esc(a.summary)}" placeholder="One sentence shown in search results"></div>
        <div class="tp-field"><label for="edCat">Category</label><input id="edCat" list="edCats" value="${esc(a.category)}"><datalist id="edCats">${cats.map((c) => `<option value="${esc(c)}">`).join("")}</datalist></div>
        <div class="tp-field"><label for="edType">Type</label>${sel("edType", ["How-to", "Troubleshooting", "Known issue", "Policy summary"], a.articleType)}</div>
        <div class="tp-field"><label for="edAud">Audience</label>${sel("edAud", ["All staff", "IT only"], a.audience)}</div>
        <div class="tp-field"><label for="edRev">Review by</label><input id="edRev" type="date" value="${esc(a.reviewDate || "")}"><div class="tp-hint">Defaults to a year from approval.</div></div>
        <div class="tp-field tp-full"><label for="edBody">Article</label>
          <div class="tp-hint" style="margin:0 0 .3rem;">Format: <code>## Heading</code> · <code>1. Step</code> · <code>- Bullet</code> · <code>**bold**</code> · <code>[text](https://…)</code> · <code>&gt; Note</code>. Write [confirm: …] for anything not yet verified.</div>
          <div class="kb-cols"><textarea id="edBody" style="min-height:360px;font-family:ui-monospace,Consolas,monospace;font-size:.82rem;">${esc(a.body)}</textarea>
          <div class="kb-editor-preview kb-body" id="edPrev" aria-label="Preview">${renderBody(a.body)}</div></div></div>
        <div class="tp-field tp-full"><label for="edKw">Keywords</label><input id="edKw" value="${esc(a.keywords.join(", "))}"><div class="tp-hint">Words and phrases staff might type, comma-separated, e.g. forgot password, locked out.</div></div>
        <div class="tp-field tp-full"><label>Based on</label><div class="tp-checks">${ev || '<span class="tp-hint">No Policy &amp; Compliance records found.</span>'}</div></div>
        ${articleId ? `<div class="tp-field"><label for="edStatus">Status</label>${sel("edStatus", a.status === "Approved" ? ["Approved", "Draft", "Retired"] : ["Draft", "Retired"], a.status)}
          ${a.status === "Approved" ? '<div class="tp-hint">Changing the wording sends it back to Draft for re-approval.</div>' : ""}</div>` : ""}
      </div><div id="edErr"></div></div>
      <div class="tp-modal-foot"><button type="button" class="btn tp-btn-ghost" data-kb-close>Cancel</button><button type="button" class="btn btn-primary" id="edSave">Save</button></div></div>`;
    m.addEventListener("click", (ev) => { if (ev.target === m || ev.target.closest("[data-kb-close]")) m.remove(); });
    document.body.appendChild(m);
    $("#edTitle").focus();
    $("#edBody").addEventListener("input", (ev) => { $("#edPrev").innerHTML = renderBody(ev.target.value); });
    $("#edSave").onclick = async () => {
      const body = { articleId: a.articleId || undefined, title: $("#edTitle").value, summary: $("#edSum").value, category: $("#edCat").value,
        articleType: $("#edType").value, audience: $("#edAud").value, reviewDate: $("#edRev").value || null, body: $("#edBody").value,
        keywords: $("#edKw").value, owner: a.owner, evidence: [...document.querySelectorAll('input[name="kbEv"]:checked')].map((x) => x.value),
        status: $("#edStatus") ? $("#edStatus").value : "Draft" };
      $("#edSave").disabled = true;
      try { await api("/knowledge/articles", { method: "POST", body }); m.remove(); toast("Article saved."); await loadManage(); }
      catch (e) { $("#edErr").innerHTML = `<div class="error-box" role="alert">${esc(e.message)}</div>`; $("#edSave").disabled = false; }
    };
  }

  // ---------------------------------------------------------------- insights
  function renderInsights() {
    const i = state.insights;
    if (!i) return `<div class="card"><div class="tp-empty">Loading insights…</div></div>`;
    const reasonTotal = Object.values(i.notHelpfulReasons).reduce((s, n) => s + n, 0);
    const list = (items, fmt, empty) => items.length ? `<ul class="kb-list">${items.map(fmt).join("")}</ul>` : `<p class="tp-hint">${empty}</p>`;
    const art = (a, extra) => `<li><button type="button" class="kb-item" data-kb-preview="${esc(a.articleId)}"><div class="kb-item-t">${esc(a.title)}</div>${extra ? `<div class="kb-item-s">${extra}</div>` : ""}</button></li>`;
    return `<div class="kb-stats">
        <div class="kb-stat"><div class="n">${i.counts.Approved}</div><div class="l">Published guides</div></div>
        <div class="kb-stat"><div class="n">${i.counts.Draft}</div><div class="l">Drafts</div></div>
        <div class="kb-stat"><div class="n">${i.searches}</div><div class="l">Searches, last 90 days</div></div>
        <div class="kb-stat"><div class="n">${i.zeroResultRate == null ? "–" : i.zeroResultRate + "%"}</div><div class="l">Searches with no results</div></div></div>
      <div class="kb-panels">
        <div class="card"><h3>Write these next</h3><p class="hint">What staff searched for and found nothing. Recorded anonymously.</p>
          ${list(i.zeroResultSearches, (z) => `<li class="kb-bar-row"><span>${esc(z.query)}</span><span class="kb-bar"><span style="width:${Math.round(100 * z.count / i.zeroResultSearches[0].count)}%"></span></span><b>${z.count}</b></li>`, "No empty searches yet.")}</div>
        <div class="card"><h3>Needs improving</h3><p class="hint">Guides fewer than 70% of readers found helpful (3+ votes).</p>
          ${list(i.lowestRated, (a) => art(a, `${a.helpfulPercent}% helpful from ${a.votes} votes`), "No poorly rated guides.")}
          ${reasonTotal ? `<h3 style="margin-top:1rem;">Why guides didn't help</h3>${Object.entries(i.notHelpfulReasons).map(([k, n]) => `<div class="kb-bar-row"><span>${esc(REASONS[k] || k)}</span><span class="kb-bar"><span style="width:${Math.round(100 * n / reasonTotal)}%"></span></span><b>${n}</b></div>`).join("")}` : ""}</div>
        <div class="card"><h3>Reader comments</h3><p class="hint">Recent "not helpful" comments.</p>
          ${list(i.recentComments, (c) => `<li style="padding:.6rem 0;"><div class="kb-item-t" style="font-size:.85rem;">${esc(c.title)}</div><div class="kb-item-s">“${esc(c.comment)}” · ${esc(REASONS[c.reason] || "")}</div></li>`, "No comments yet.")}</div>
        <div class="card"><h3>Due for review</h3><p class="hint">Published guides past their review date.</p>
          ${list(i.reviewOverdue, (a) => art(a, `Review was due ${esc(fmtDate(a.reviewDate))}`), "Every published guide is within its review date.")}
          <h3 style="margin-top:1rem;">Drafts waiting for facts</h3><p class="hint">Drafts that still contain [confirm] text.</p>
          ${list(i.draftsWithPlaceholders, (a) => art(a), "None.")}</div>
        <div class="card"><h3>Most searched</h3>${list(i.topSearches, (z) => `<li class="kb-bar-row"><span>${esc(z.query)}</span><span class="kb-bar"><span style="width:${Math.round(100 * z.count / i.topSearches[0].count)}%"></span></span><b>${z.count}</b></li>`, "No searches yet.")}</div>
        <div class="card"><h3>Most viewed</h3>${list(i.mostViewed, (a) => art(a, `${a.views} view${a.views === 1 ? "" : "s"}${a.votes ? ` · ${a.helpfulPercent}% helpful` : ""}`), "No views yet.")}</div>
      </div>`;
  }

  // ----------------------------------------------------------------- loaders
  async function loadHome() { try { state.home = await api("/knowledge/home"); } catch (e) { state.error = e.message; } render(); }
  async function loadManage() { try { state.manage = (await api("/knowledge/articles")).articles; } catch (e) { state.error = e.message; state.manage = []; } render(); }
  async function loadInsights() { try { state.insights = await api("/knowledge/insights"); } catch (e) { state.error = e.message; } render(); }
  async function openArticle(id, preview) {
    try {
      const res = await api(`/knowledge/articles/${encodeURIComponent(id)}${preview ? "?drafts=true" : ""}`);
      state.article = { ...res, preview: !!preview }; state.view = "browse"; state.page = "article"; state.error = "";
      if (!preview && location.hash !== `#kb/${id}`) history.replaceState(null, "", `#kb/${id}`);
      render(); window.scrollTo({ top: 0 });
    } catch (e) { toast(e.message); }
  }
  async function openCategory(name) {
    try { state.category = await api(`/knowledge/category?name=${encodeURIComponent(name)}${state.article && state.article.preview ? "&drafts=true" : ""}`); state.page = "category"; state.view = "browse"; render(); }
    catch (e) { toast(e.message); }
  }
  async function runSearch(q) {
    q = (q || "").trim(); if (q.length < 2) return;
    clearTimeout(suggestTimer); const box = $("#kbSuggest"); if (box) box.hidden = true;  // no late suggestions over results
    state.query = q;
    try { state.results = await api(`/knowledge/search?q=${encodeURIComponent(q)}`); state.page = "results"; render(); const i = $("#kbQ"); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }
    catch (e) { toast(e.message); }
  }

  // Suggestions while typing: not logged, so only submitted searches count as demand.
  function suggest(q) {
    clearTimeout(suggestTimer);
    const box = $("#kbSuggest"); if (!box) return;
    if (q.trim().length < 2) { box.hidden = true; return; }
    suggestTimer = setTimeout(async () => {
      try {
        const r = await api(`/knowledge/search?q=${encodeURIComponent(q)}&log=false`);
        const b = $("#kbSuggest"); if (!b || $("#kbQ").value !== q) return;
        suggestIdx = -1;
        b.innerHTML = r.results.slice(0, 5).map((a) => `<button type="button" role="option" data-kb-open="${esc(a.articleId)}"><div class="t">${esc(a.title)}</div><div class="s">${esc(a.summary)}</div></button>`).join("")
          + `<button type="button" class="all" data-kb-search-all>See all results for “${esc(q)}”</button>`;
        b.hidden = false;
      } catch (e) { /* suggestions are best-effort */ }
    }, 220);
  }

  async function sendFeedback(helpful) {
    const a = state.article.article, box = $("#kbFeedback");
    const body = { articleId: a.articleId, helpful };
    if (!helpful) {
      const r = document.querySelector('input[name="kbReason"]:checked');
      if (!r) { toast("Choose what went wrong."); return; }
      body.reason = r.value; body.comment = ($("#kbComment") || {}).value || "";
    }
    try { await api("/knowledge/feedback", { method: "POST", body }); box.innerHTML = feedbackForm("thanks"); }
    catch (e) { toast(e.message); }
  }

  // ----------------------------------------------------------------- events
  function bind() {
    const r = root(); if (!r || r.dataset.bound) return;
    r.dataset.bound = "1";
    r.addEventListener("click", async (ev) => {
      const t = ev.target.closest("button"); if (!t) return;
      const d = t.dataset;
      if (d.kbView) { state.view = d.kbView; state.error = ""; if (d.kbView === "browse") { state.page = "home"; loadHome(); } render();
        if (d.kbView === "manage") loadManage(); if (d.kbView === "insights") loadInsights(); return; }
      if (d.kbOpen) return openArticle(d.kbOpen, false);
      if (d.kbPreview) return openArticle(d.kbPreview, true);
      if (d.kbCat) return openCategory(d.kbCat);
      if (d.kbHome !== undefined) { state.page = "home"; state.query = ""; history.replaceState(null, "", location.pathname); loadHome(); return; }
      if (d.kbSearchAll !== undefined) return runSearch($("#kbQ").value);
      if (d.kbEdit) return openEditor(d.kbEdit);
      if (d.kbNew !== undefined) return openEditor(null);
      if (d.kbApprove) { try { await api(`/knowledge/articles/${encodeURIComponent(d.kbApprove)}/approve`, { method: "POST", body: {} }); toast("Article published."); loadManage(); } catch (e) { toast(e.message); } return; }
      if (d.kbCopy) { const url = `${location.origin}${location.pathname}#kb/${d.kbCopy}`; try { await navigator.clipboard.writeText(url); toast("Link copied."); } catch (e) { toast(url); } return; }
      if (d.kbFb === "yes") return sendFeedback(true);
      if (d.kbFb === "no") { $("#kbFeedback").innerHTML = feedbackForm("no"); return; }
      if (d.kbFbSend !== undefined) return sendFeedback(false);
    });
    r.addEventListener("input", (ev) => {
      const el = ev.target;
      if (el.id === "kbQ") { state.query = el.value; suggest(el.value); }
      if (el.dataset.kbMf) { state.mFilter[el.dataset.kbMf] = el.value; const id = el.dataset.kbMf; render(); const back = document.querySelector(`[data-kb-mf="${id}"]`); if (back && back.type === "search") { back.focus(); back.setSelectionRange(back.value.length, back.value.length); } }
    });
    r.addEventListener("keydown", (ev) => {
      if (ev.target.id !== "kbQ") return;
      const box = $("#kbSuggest"), opts = box && !box.hidden ? [...box.querySelectorAll("button")] : [];
      if (ev.key === "ArrowDown" && opts.length) { ev.preventDefault(); suggestIdx = (suggestIdx + 1) % opts.length; }
      else if (ev.key === "ArrowUp" && opts.length) { ev.preventDefault(); suggestIdx = (suggestIdx - 1 + opts.length) % opts.length; }
      else if (ev.key === "Enter") { ev.preventDefault(); if (suggestIdx >= 0 && opts[suggestIdx]) opts[suggestIdx].click(); else runSearch(ev.target.value); return; }
      else if (ev.key === "Escape") { if (box) box.hidden = true; return; }
      else return;
      opts.forEach((o, i) => o.classList.toggle("is-active", i === suggestIdx));
    });
    document.addEventListener("click", (ev) => { const box = $("#kbSuggest"); if (box && !ev.target.closest(".kb-search")) box.hidden = true; });
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") { const m = $("#kbModal"); if (m) m.remove(); } });
  }

  window.KnowledgeBase = {
    open: function () {
      bind();
      const m = location.hash.match(/^#kb\/([A-Za-z0-9-]+)$/);
      if (m) { openArticle(m[1], false); return; }
      if (!state.home) loadHome(); else render();
    },
    _renderBody: renderBody,
  };
})();
