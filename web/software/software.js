/*
 * IT Helpdesk Portal — Software Catalogue
 * ---------------------------------------
 * Overview      headline figures, one insight card per department, and
 *               findings that need attention, all calculated from the data
 * Catalogue     searchable, filterable list with a detail panel per service
 * Review queue  every service needing action, grouped by department, with CSV export
 *
 * Data: /software/catalogue.json, generated from the CLG Group Software
 * Catalog workbook by tools/build_software_catalogue.py. The file sits behind
 * the portal's sign-in like every other page. All text is escaped before it
 * is put into the page.
 */
(function () {
  "use strict";

  // AI tools approved in CLG_SEC_POL_006 (AI Governance Policy), section 17.
  // Update this list when the approved AI tools register changes.
  const AI_APPROVED = [
    { label: "Microsoft 365 Copilot", match: /copilot/i },
    { label: "WindSurf Coding", match: /windsurf/i },
    { label: "ElevenLabs Voiceover Generator", match: /elevenlabs/i },
    { label: "Claude Enterprise", match: /claude/i },
  ];
  const AI_PATTERN = /\bAI\b|copilot|chatgpt|openai|midjourney|synthesia|windsurf|claude|elevenlabs|gemini/i;
  const UNASSIGNED = /confirm|unknown|relevant department|not identified/i;
  const STATUSES = ["Active", "Review", "Verify", "Restricted"];
  const STATUS_HELP = { Active: "In use and evidenced", Review: "Owner, licence or need to confirm", Verify: "Use not yet proven", Restricted: "Use restricted by policy" };
  const CONFIDENCE_HELP = { Confirmed: "Directly evidenced in an internal source", Referenced: "Named in proposals or onboarding, licensing not proven", Ambiguous: "Name needs clarifying" };

  const state = { data: null, error: "", view: "overview", q: "", dept: "", status: "", confidence: "", attention: false };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const root = () => document.getElementById("softwareApp");
  const pct = (n, d) => (d ? Math.round((100 * n) / d) : 0);
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
  const needsAction = (i) => i.status !== "Active" || i.confidence !== "Confirmed";
  const unassigned = (i) => UNASSIGNED.test(i.owner);
  const isAI = (i) => AI_PATTERN.test(i.name) || AI_PATTERN.test(i.purpose);
  const normName = (n) => n.toLowerCase().replace(/[^a-z0-9]/g, "");

  // ------------------------------------------------------------ analysis
  function analyse(items) {
    const depts = [...new Set(items.map((i) => i.department))].sort((a, b) => items.filter((i) => i.department === b).length - items.filter((i) => i.department === a).length);
    const byDept = depts.map((d) => {
      const list = items.filter((i) => i.department === d);
      const vendors = countBy(list, "vendor");
      return {
        name: d, items: list, count: list.length,
        status: STATUSES.map((s) => ({ s, n: list.filter((i) => i.status === s).length })),
        confirmedPct: pct(list.filter((i) => i.confidence === "Confirmed").length, list.length),
        action: list.filter(needsAction).length, unassigned: list.filter(unassigned).length,
        vendors: vendors.slice(0, 3),
      };
    });
    const findings = [];
    const add = (level, title, text, list) => list.length && findings.push({ level, title, text, list });

    const aiOut = items.filter((i) => isAI(i) && !AI_APPROVED.some((a) => a.match.test(i.name)));
    add("high", `${plural(aiOut.length, "AI tool")} outside the approved AI register`,
      "The AI Governance Policy (CLG_SEC_POL_006, section 17) allows only tools on the approved register. Approve these through the AI Tool Request process or stop their use.", aiOut);
    const aiMissing = AI_APPROVED.filter((a) => !items.some((i) => a.match.test(i.name)));
    if (aiMissing.length) findings.push({ level: "info", title: `${plural(aiMissing.length, "approved AI tool")} missing from the catalogue`,
      text: `${aiMissing.map((a) => a.label).join(" and ")} ${aiMissing.length === 1 ? "is" : "are"} on the approved AI register but not catalogued. Add ${aiMissing.length === 1 ? "it" : "them"}, or remove ${aiMissing.length === 1 ? "it" : "them"} from the register.`, list: [] });

    const noOwner = items.filter(unassigned);
    add("high", `${plural(noOwner.length, "service")} without a confirmed business owner`,
      "Each service needs a named owner who is accountable for its licence, renewal and data. These show 'owner to confirm', 'unknown' or a vague department.", noOwner);

    const owners = countBy(items, "owner");
    const [topOwner, topN] = owners[0] || [];
    if (topN >= 8) add("medium", `${topN} services (${pct(topN, items.length)}%) rely on one owner: ${topOwner}`,
      "A single named owner for this many services is a key-person risk. Consider naming deputies or a team owner, especially for critical platforms.", items.filter((i) => i.owner === topOwner));

    const groups = {};
    items.forEach((i) => { (groups[normName(i.name)] = groups[normName(i.name)] || []).push(i); });
    const dupes = Object.values(groups).filter((g) => g.length > 1).flat();
    add("medium", "Same service listed in more than one department",
      "Merge these into one entry with the full business scope, so ownership, licences and renewals are tracked once.", dupes);

    const hygiene = items.filter((i) => /duplicate|two subscriptions|two accounts|user-held login|consolidat/i.test(i.notes));
    add("medium", `${plural(hygiene.length, "service")} with duplicate accounts or user-held logins`,
      "Duplicated subscriptions waste money, and logins held by individuals are lost when people leave. Consolidate to one centrally billed account each.", hygiene);

    const lms = items.filter((i) => /\blms\b|learning management|learning platform|learning delivery/i.test(i.name + " " + i.purpose)
      && !/runtime|stack|infrastructure|hosting/i.test(i.purpose) && i.confidence !== "Ambiguous" && i.vendor !== "Cognition Learning Group");
    add("info", `${plural(lms.length, "third-party learning platform")} alongside CLG's own LMS`,
      "CLG develops and licenses its own LMS (CogConnect). Check each third-party platform is still needed, and note that Moodle is restricted by policy.", lms);

    const unproven = items.filter((i) => i.confidence !== "Confirmed");
    add("info", `${plural(unproven.length, "service")} named in documents but not proven in use`,
      "These appear in proposals or onboarding material, but no subscription or licence record was found. Confirm each, or remove it from the catalogue.", unproven);

    const overlap = items.filter((i) => /google workspace/i.test(i.name));
    if (overlap.length) add("info", "Collaboration suite overlap", "Google Workspace is held alongside Microsoft 365, the Group standard. Review whether it's still needed.", overlap);

    return { depts: byDept, findings, vendors: countBy(items, "vendor"), owners };
  }
  function countBy(list, key) {
    const m = {};
    list.forEach((i) => { const k = i[key] || "Not recorded"; m[k] = (m[k] || 0) + 1; });
    return Object.entries(m).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }

  // ------------------------------------------------------------ rendering
  function render() {
    const r = root(); if (!r) return;
    const d = state.data;
    const seg = (id, label) => `<button type="button" data-sw-view="${id}" aria-pressed="${state.view === id}">${label}</button>`;
    r.innerHTML = `<div class="tp-head"><div><h1>Software Catalogue</h1>
        <p>Every system and service used across CLG: who owns it, how it's licensed, and what needs attention.${d ? ` Source: ${esc(d.source)}.` : ""}</p></div>
        <div class="tp-seg" role="group" aria-label="Software Catalogue sections">${seg("overview", "Overview")}${seg("catalogue", "Catalogue")}${seg("queue", "Review queue")}</div></div>
      ${state.error ? `<div class="error-box" role="alert">${esc(state.error)}</div>` : ""}
      ${!d ? (state.error ? "" : `<div class="card"><div class="tp-empty">Loading the catalogue…</div></div>`)
        : state.view === "overview" ? renderOverview() : state.view === "catalogue" ? renderCatalogue() : renderQueue()}`;
  }

  function renderOverview() {
    const items = state.data.items, a = state.analysis;
    const active = items.filter((i) => i.status === "Active").length;
    const confirmed = items.filter((i) => i.confidence === "Confirmed").length;
    const action = items.filter(needsAction).length;
    const noOwner = items.filter(unassigned).length;
    const ai = items.filter(isAI);
    const aiOut = ai.filter((i) => !AI_APPROVED.some((x) => x.match.test(i.name))).length;
    const kpi = (n, l, s, cls = "") => `<div class="sw-kpi ${cls}"><div class="n">${n}</div><div class="l">${l}</div><div class="s">${s}</div></div>`;
    const legend = STATUSES.map((s) => `<span><i class="${s}"></i>${s}</span>`).join("");
    return `<div class="sw-kpis">
        ${kpi(items.length, "Services catalogued", `${a.depts.length} departments, ${a.vendors.length} vendors`, "accent")}
        ${kpi(`${pct(active, items.length)}<small>%</small>`, "Active", `${active} of ${items.length} in use and evidenced`)}
        ${kpi(`${pct(confirmed, items.length)}<small>%</small>`, "Evidence confirmed", `${confirmed} directly evidenced in internal records`)}
        ${kpi(action, "Need action", `${noOwner} without a confirmed owner`, "warn")}
        ${kpi(ai.length, "AI tools", aiOut ? `${aiOut} outside the approved register` : "All on the approved register", aiOut ? "warn" : "")}
      </div>
      <div class="sw-section-h"><h2>By department</h2><p>Select a department to see its services.</p></div>
      <div class="sw-depts">${a.depts.map(deptCard).join("")}</div>
      <div class="sw-grid2">
        <div class="card"><div class="sw-section-h"><h2>Needs attention</h2><p>${plural(a.findings.length, "finding")}</p></div>
          <ul class="sw-findings">${a.findings.map(finding).join("")}</ul></div>
        <div>
          <div class="card" style="margin-top:0;"><div class="sw-section-h"><h2>Status by department</h2></div>
            <div class="sw-bars">${a.depts.map((d) => `<div class="sw-bar-row"><span class="t">${esc(d.name)}</span>
              <span class="sw-stack" style="height:10px;">${d.status.filter((x) => x.n).map((x) => `<span class="${x.s}" style="width:${pct(x.n, d.count)}%" title="${x.s}: ${x.n}"></span>`).join("")}</span>
              <span class="v">${d.count}</span></div>`).join("")}</div>
            <div class="sw-legend" style="margin-top:.7rem;">${legend}</div></div>
          <div class="card"><div class="sw-section-h"><h2>Top vendors</h2><p>By number of services</p></div>
            <div class="sw-bars">${a.vendors.slice(0, 7).map(([v, n]) => `<div class="sw-bar-row"><span class="t">${esc(v)}</span>
              <span class="b"><span style="width:${pct(n, a.vendors[0][1])}%"></span></span><span class="v">${n}</span></div>`).join("")}</div>
            <p class="sw-note">Microsoft and Zoho together supply ${a.vendors.filter(([v]) => /^(microsoft|zoho)$/i.test(v)).reduce((s, [, n]) => s + n, 0)} services, so their contracts and renewals carry the most weight.</p></div>
        </div>
      </div>`;
  }

  function deptCard(d) {
    return `<button type="button" class="sw-dept" data-sw-dept="${esc(d.name)}" aria-label="${esc(d.name)}: ${d.count} services">
      <div class="sw-dept-h"><span class="name">${esc(d.name)}</span><span class="count">${d.count}<small>services</small></span></div>
      <span class="sw-stack">${d.status.filter((x) => x.n).map((x) => `<span class="${x.s}" style="width:${pct(x.n, d.count)}%" title="${x.s}: ${x.n}"></span>`).join("")}</span>
      <div class="sw-legend">${d.status.filter((x) => x.n).map((x) => `<span><i class="${x.s}"></i>${x.n} ${x.s.toLowerCase()}</span>`).join("")}</div>
      <div class="sw-metrics"><div><b>${d.confirmedPct}%</b>evidence confirmed</div><div><b class="${d.action ? "bad" : ""}">${d.action}</b>need action</div>
        <div><b class="${d.unassigned ? "bad" : ""}">${d.unassigned}</b>no confirmed owner</div></div>
      <div class="vendors">Main vendors: ${d.vendors.map(([v, n]) => `<b>${esc(v)}</b> (${n})`).join(", ")}</div></button>`;
  }

  function finding(f) {
    return `<li class="sw-finding ${f.level}"><span class="bar"></span><div><h3>${esc(f.title)}</h3><p>${esc(f.text)}</p>
      ${f.list.length ? `<div class="sw-tags">${f.list.map((i) => `<button type="button" class="sw-tag" data-sw-open="${esc(i.id)}" title="${esc(i.department)}">${esc(i.name)}</button>`).join("")}</div>` : ""}</div></li>`;
  }

  function filtered() {
    const q = state.q.toLowerCase();
    return state.data.items.filter((i) => (!state.dept || i.department === state.dept) && (!state.status || i.status === state.status)
      && (!state.confidence || i.confidence === state.confidence) && (!state.attention || needsAction(i))
      && (!q || [i.name, i.vendor, i.purpose, i.owner, i.scope, i.notes].join(" ").toLowerCase().includes(q)));
  }

  function renderCatalogue() {
    const items = state.data.items, rows = filtered();
    const opt = (values, cur, all) => `<option value="">${all}</option>${values.map((v) => `<option ${v === cur ? "selected" : ""}>${esc(v)}</option>`).join("")}`;
    const depts = state.analysis.depts.map((d) => d.name);
    return `<div class="card">
      <div class="tp-toolbar"><input type="search" data-sw-f="q" value="${esc(state.q)}" placeholder="Search services, vendors, owners and notes" aria-label="Search the catalogue">
        <select data-sw-f="dept" aria-label="Department">${opt(depts, state.dept, "All departments")}</select>
        <select data-sw-f="status" aria-label="Status">${opt(STATUSES, state.status, "All statuses")}</select>
        <select data-sw-f="confidence" aria-label="Evidence">${opt(["Confirmed", "Referenced", "Ambiguous"], state.confidence, "All evidence")}</select>
        <label style="display:inline-flex;gap:.35rem;align-items:center;font-size:.85rem;margin-left:auto;"><input type="checkbox" data-sw-f="attention" ${state.attention ? "checked" : ""} style="accent-color:var(--brand-orange-text);"> Needs action only</label></div>
      <p class="sw-count">Showing ${rows.length} of ${items.length} services${state.dept ? ` in ${esc(state.dept)}` : ""}.
        ${state.dept || state.status || state.confidence || state.q || state.attention ? `<button type="button" class="tp-link" data-sw-clear>Clear filters</button>` : ""}</p>
      <div class="tp-table-wrap"><table class="tp-table"><thead><tr><th>Service</th><th>Department</th><th>Vendor</th><th>Business owner</th><th>Licence</th><th>Status</th><th>Evidence</th></tr></thead><tbody>
      ${rows.length ? rows.map((i) => `<tr class="sw-row" tabindex="0" data-sw-open="${esc(i.id)}">
        <td><span class="sw-name">${esc(i.name)}</span>${isAI(i) ? '<span class="sw-flag">AI</span>' : ""}<span class="sw-sub">${esc(i.purpose)}</span></td>
        <td>${esc(i.department)}</td><td>${esc(i.vendor)}</td>
        <td>${unassigned(i) ? `<span style="color:var(--sw-review);font-weight:600;">${esc(i.owner)}</span>` : esc(i.owner)}</td>
        <td style="font-size:.8rem;">${esc(i.licence)}</td>
        <td><span class="sw-pill ${esc(i.status)}" title="${esc(STATUS_HELP[i.status] || "")}">${esc(i.status)}</span></td>
        <td><span class="sw-pill ${esc(i.confidence)}" title="${esc(CONFIDENCE_HELP[i.confidence] || "")}">${esc(i.confidence)}</span></td></tr>`).join("")
        : `<tr><td colspan="7"><div class="tp-empty">No services match these filters.</div></td></tr>`}</tbody></table></div></div>`;
  }

  function renderQueue() {
    const items = state.data.items.filter(needsAction);
    const groups = state.analysis.depts.map((d) => ({ name: d.name, list: items.filter((i) => i.department === d.name) })).filter((g) => g.list.length);
    return `<div class="card"><div class="sw-section-h"><h2>${plural(items.length, "service")} need action</h2>
        <button type="button" class="btn tp-btn-ghost" data-sw-csv style="margin:0;">Download CSV</button></div>
      <p class="sw-count">Services that aren't both Active and directly evidenced. Confirm each one's use, owner, licence and renewal, and whether it should stay in the approved catalogue.</p>
      ${groups.map((g) => `<div class="sw-queue-group"><h3>${esc(g.name)} <span class="tp-hint" style="margin:0;">(${g.list.length})</span></h3>
        <div class="tp-table-wrap"><table class="tp-table"><thead><tr><th>Service</th><th>Owner</th><th>Status</th><th>Evidence</th><th>Notes</th></tr></thead><tbody>
        ${g.list.map((i) => `<tr class="sw-row" tabindex="0" data-sw-open="${esc(i.id)}"><td><span class="sw-name">${esc(i.name)}</span><span class="sw-sub">${esc(i.vendor)}</span></td>
          <td>${esc(i.owner)}</td><td><span class="sw-pill ${esc(i.status)}">${esc(i.status)}</span></td>
          <td><span class="sw-pill ${esc(i.confidence)}">${esc(i.confidence)}</span></td><td style="font-size:.8rem;max-width:36ch;">${esc(i.notes)}</td></tr>`).join("")}
        </tbody></table></div></div>`).join("")}</div>`;
  }

  function openDrawer(id) {
    const i = state.data.items.find((x) => x.id === id); if (!i) return;
    closeDrawer();
    const others = state.data.items.filter((x) => x.id !== i.id && normName(x.name) === normName(i.name));
    const aiOut = isAI(i) && !AI_APPROVED.some((a) => a.match.test(i.name));
    const row = (k, v) => v ? `<dt>${k}</dt><dd>${esc(v)}</dd>` : "";
    const m = document.createElement("div");
    m.className = "sw-drawer"; m.id = "swDrawer";
    m.innerHTML = `<aside class="sw-drawer-box" role="dialog" aria-modal="true" aria-labelledby="swDT">
      <div class="sw-drawer-h"><div style="display:flex;justify-content:space-between;align-items:center;">
        <span><span class="sw-pill ${esc(i.status)}">${esc(i.status)}</span> <span class="sw-pill ${esc(i.confidence)}">${esc(i.confidence)}</span></span>
        <button type="button" class="tp-close" data-sw-close aria-label="Close">×</button></div>
        <h2 id="swDT">${esc(i.name)}</h2><p>${esc(i.vendor)} · ${esc(i.department)}</p></div>
      <div class="sw-drawer-b">
        ${aiOut ? `<div class="sw-callout" style="background:var(--sw-restricted-bg);border-color:var(--sw-restricted);"><b>Not on the approved AI register</b>The AI Governance Policy (CLG_SEC_POL_006) requires this tool to be approved before use.</div>` : ""}
        ${i.notes ? `<div class="sw-callout"><b>Review notes</b>${esc(i.notes)}</div>` : ""}
        <dl class="sw-dl">${row("Business purpose", i.purpose)}${row("Business scope", i.scope)}${row("Business owner", i.owner)}
          ${row("Licence / cost model", i.licence)}${row("Lifecycle status", `${i.status} — ${STATUS_HELP[i.status] || ""}`)}
          ${row("Evidence", `${i.confidence} — ${CONFIDENCE_HELP[i.confidence] || ""}`)}${row("Evidence source", i.evidence)}
          ${row("Required action", i.requiredAction)}</dl>
        ${others.length ? `<p class="tp-hint">Also listed under ${others.map((o) => `<button type="button" class="tp-link" data-sw-open="${esc(o.id)}">${esc(o.department)}</button>`).join(", ")}.</p>` : ""}
      </div></aside>`;
    m.addEventListener("click", (ev) => {
      if (ev.target === m || ev.target.closest("[data-sw-close]")) return closeDrawer();
      const o = ev.target.closest("[data-sw-open]"); if (o) openDrawer(o.dataset.swOpen);
    });
    document.body.appendChild(m);
    m.querySelector("[data-sw-close]").focus();
  }
  function closeDrawer() { const m = document.getElementById("swDrawer"); if (m) m.remove(); }

  function downloadCsv() {
    const cols = [["Department", "department"], ["Software / Service", "name"], ["Vendor", "vendor"], ["Business Owner", "owner"],
      ["Lifecycle Status", "status"], ["Evidence Confidence", "confidence"], ["Review Notes", "notes"], ["Required Action", "requiredAction"]];
    const cell = (v) => `"${String(v || "").replace(/"/g, '""')}"`;
    const lines = [cols.map(([h]) => cell(h)).join(",")].concat(state.data.items.filter(needsAction).map((i) => cols.map(([, k]) => cell(i[k])).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv" }));
    a.download = "CLG software review queue.csv"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  // ------------------------------------------------------------ events
  function bind() {
    const r = root(); if (!r || r.dataset.bound) return;
    r.dataset.bound = "1";
    r.addEventListener("click", (ev) => {
      const t = ev.target.closest("button, tr[data-sw-open]"); if (!t) return;
      const d = t.dataset;
      if (d.swView) { state.view = d.swView; render(); return; }
      if (d.swDept) { Object.assign(state, { view: "catalogue", dept: d.swDept, status: "", confidence: "", q: "", attention: false }); render(); window.scrollTo({ top: 0 }); return; }
      if (d.swOpen) return openDrawer(d.swOpen);
      if (d.swClear !== undefined) { Object.assign(state, { dept: "", status: "", confidence: "", q: "", attention: false }); render(); return; }
      if (d.swCsv !== undefined) downloadCsv();
    });
    r.addEventListener("keydown", (ev) => { const tr = ev.target.closest("tr[data-sw-open]"); if (tr && ev.key === "Enter") openDrawer(tr.dataset.swOpen); });
    r.addEventListener("input", (ev) => {
      const el = ev.target, k = el.dataset.swF; if (!k) return;
      state[k] = el.type === "checkbox" ? el.checked : el.value;
      render();
      if (k === "q") { const back = $('[data-sw-f="q"]'); back.focus(); back.setSelectionRange(back.value.length, back.value.length); }
    });
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") closeDrawer(); });
  }

  async function load() {
    try {
      const res = await fetch("/software/catalogue.json", { credentials: "same-origin", cache: "no-cache" });
      if (!res.ok) throw new Error(`The catalogue could not be loaded (HTTP ${res.status}).`);
      state.data = await res.json();
      state.analysis = analyse(state.data.items);
    } catch (e) { state.error = e.message || "The catalogue could not be loaded."; }
    render();
  }

  window.SoftwareCatalogue = {
    open: function () { bind(); if (!state.data && !state.error) { render(); load(); } else render(); },
    _analyse: analyse,
  };
})();
