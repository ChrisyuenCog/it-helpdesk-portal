/*
 * IT Helpdesk Portal — My Requests, My Approvals, My Devices, hardware request form
 * -------------------------------------------------------------------------------
 * Phase 1 identity: nothing here says who the user is. The API works out the
 * caller from the Microsoft sign-in token (api/workflow_access.py) and returns,
 * for each request, the progress stages, timeline and the exact actions THIS
 * caller may take. The page only renders what the server allows.
 *
 * Defines the globals the tab switcher calls: loadMyRequests(), loadMyApprovals(),
 * loadMyDevices(). Depends on index.html globals apiCall(), getApiAccessToken().
 * All values from the API are escaped before being put into the page.
 */
(function () {
  "use strict";

  const ASSET_API = "https://it-asset-register-api-asded3axebb7h2g3.uksouth-01.azurewebsites.net/api";
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtDate(iso, withTime) {
    if (!iso) return "";
    const d = new Date(String(iso).length <= 10 ? iso + "T00:00:00" : iso);
    if (isNaN(d)) return String(iso);
    const s = `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
    return withTime ? `${s}, ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}` : s;
  }
  function ago(iso) {
    const d = new Date(iso); if (isNaN(d)) return "";
    const days = Math.floor((Date.now() - d.getTime()) / 86400000);
    return days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`;
  }
  function toast(msg) { const el = document.createElement("div"); el.className = "tp-toast"; el.setAttribute("role", "status"); el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 2800); }
  const STATUS_LABEL = { open: "In progress", completed: "Completed", rejected: "Rejected" };
  const ICON = {
    laptop: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M2 20h20"/></svg>',
    monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
    phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="2" width="12" height="20" rx="2"/><path d="M11 18h2"/></svg>',
    box: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/></svg>',
  };
  const state = { me: null, requests: null, filter: "all", approvals: null, devices: null };

  // ------------------------------------------------------------ identity in the header
  async function loadMe() {
    if (state.me) return state.me;
    try {
      state.me = await apiCall("/me");
      const el = document.getElementById("signedInRoles");
      if (el) el.innerHTML = (state.me.roleLabels || []).map((r) => `<span>${esc(r)}</span>`).join("");
    } catch (e) { /* the tab that needs it will show the error */ }
    return state.me;
  }
  window.PortalIdentity = { load: loadMe };

  // ------------------------------------------------------------ shared pieces
  function steps(stages) {
    if (!stages || !stages.length) return "";
    return `<ol class="rq-steps" aria-label="Progress">${stages.map((s) =>
      `<li class="${esc(s.status)}" ${s.status === "current" ? 'aria-current="step"' : ""}><span>${esc(s.label)}</span></li>`).join("")}</ol>`;
  }
  function meta(r, who) {
    const bits = [];
    if (who === "approver") bits.push(`Requested by <b>${esc(r.requesterUpn)}</b>`);
    if (r.quantity && r.quantity > 1) bits.push(`Quantity <b>${esc(r.quantity)}</b>`);
    if (r.neededBy) bits.push(`Needed by <b>${esc(fmtDate(r.neededBy))}</b>`);
    if (who !== "approver" && r.approverUpn) bits.push(`Manager <b>${esc(r.approverUpn)}</b>`);
    bits.push(`Submitted <b>${esc(fmtDate(r.createdAt))}</b>`);
    if (r.serialNumber) bits.push(`Serial <b>${esc(r.serialNumber)}</b>`);
    return `<div class="rq-meta">${bits.map((b) => `<span>${b}</span>`).join("")}</div>`;
  }
  function timeline(r) {
    const items = (r.timeline || []).slice().reverse();
    if (!items.length) return "";
    return `<ul class="rq-timeline">${items.map((t) => `<li><div class="t">${esc(t.text)}</div>
      <div class="m">${esc(fmtDate(t.at, true))}${t.by ? ` · ${esc(t.by)}` : ""}</div>${t.comment ? `<div class="c">“${esc(t.comment)}”</div>` : ""}</li>`).join("")}</ul>`;
  }
  function card(r, who) {
    return `<article class="rq-card is-${esc(r.status)}" data-rq="${esc(r.instanceId)}">
      <div class="rq-top"><div><div class="rq-title">${esc(r.title)}</div>
        <div class="rq-ref"><b>${esc(r.reference)}</b> · ${esc(r.workflowLabel)}${r.status === "open" ? ` · now at ${esc(r.stateLabel.toLowerCase())}` : ""}</div></div>
        <span class="rq-pill ${esc(r.status)}">${esc(r.status === "open" ? r.stateLabel : STATUS_LABEL[r.status] || r.stateLabel)}</span></div>
      ${steps(r.stages)}${meta(r, who)}
      ${r.justification ? `<p class="rq-just">${esc(r.justification)}</p>` : ""}
      ${rejection(r)}
      ${who === "approver" ? actions(r) : ""}
      <div class="rq-toggle"><button type="button" class="tp-link" data-rq-history="${esc(r.instanceId)}" aria-expanded="false">Show history</button>
        <div class="rq-history" hidden>${timeline(r)}</div></div></article>`;
  }
  // Why a request was rejected, shown on the card rather than hidden in the history.
  function rejection(r) {
    if (r.status !== "rejected") return "";
    const e = (r.timeline || []).slice().reverse().find((t) => /^Rejected/.test(t.text || ""));
    if (!e) return "";
    return `<div class="rq-rejected"><b>${esc(e.text)}${e.by ? ` by ${esc(e.by)}` : ""}</b>${e.comment ? `<span>“${esc(e.comment)}”</span>` : ""}</div>`;
  }
  function actions(r) {
    const acts = r.availableActions || [];
    if (!acts.length) return "";
    const fields = [];
    acts.forEach((a) => (a.requiredFields || []).forEach((f) => { if (!fields.some((x) => x.name === f.name)) fields.push(f); }));
    const positive = acts.filter((a) => !a.requiresComment), negative = acts.filter((a) => a.requiresComment);
    return `<div class="rq-act" data-act="${esc(r.instanceId)}">
      ${fields.map((f) => `<div class="tp-field"><label for="f-${esc(r.instanceId)}-${esc(f.name)}">${esc(f.label)} <span class="tp-req">*</span></label>
        <input id="f-${esc(r.instanceId)}-${esc(f.name)}" data-field="${esc(f.name)}" autocomplete="off"></div>`).join("")}
      ${positive.length ? `<div class="tp-field"><label for="c-${esc(r.instanceId)}">Comment <span class="tp-hint" style="margin:0;font-weight:400;">(optional)</span></label>
        <textarea id="c-${esc(r.instanceId)}" data-comment placeholder="Add a note for the requester and the next approver"></textarea></div>` : ""}
      <div class="tp-actions">${positive.map((a) => `<button type="button" class="btn btn-primary" data-do="${esc(a.action)}">${esc(a.label)}</button>`).join("")}
        ${negative.map((a) => `<button type="button" class="btn tp-btn-ghost" data-ask="${esc(a.action)}">${esc(a.label)}…</button>`).join("")}</div>
      ${negative.map((a) => `<div class="rq-reason" data-reason="${esc(a.action)}" hidden><div class="tp-field" style="margin-bottom:.5rem;">
        <label for="r-${esc(r.instanceId)}">Reason <span class="tp-req">*</span></label>
        <textarea id="r-${esc(r.instanceId)}" data-reason-text placeholder="Tell the requester why, and what to do instead"></textarea></div>
        <div class="tp-actions"><button type="button" class="btn btn-danger" data-do="${esc(a.action)}" data-needs-reason>${esc(a.label)} request</button>
        <button type="button" class="tp-link" data-cancel-ask>Cancel</button></div></div>`).join("")}
      <div data-act-result></div></div>`;
  }
  function errorBox(msg) { return `<div class="error-box" role="alert">${esc(msg)}</div>`; }

  // ------------------------------------------------------------ My Requests
  async function loadMyRequests() {
    const el = document.getElementById("myRequestsApp");
    if (!state.requests) el.innerHTML = `<div class="card"><div class="tp-empty">Loading your requests…</div></div>`;
    try {
      const data = await apiCall("/workflow/myRequests");
      state.requests = (data.requests || []).slice().sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
      renderRequests();
      loadMe();
    } catch (e) { el.innerHTML = errorBox(e.message); }
  }
  function renderRequests() {
    const el = document.getElementById("myRequestsApp"), all = state.requests;
    const counts = { all: all.length, open: 0, completed: 0, rejected: 0 };
    all.forEach((r) => { counts[r.status] = (counts[r.status] || 0) + 1; });
    const shown = all.filter((r) => state.filter === "all" || r.status === state.filter);
    const f = (k, l) => `<button type="button" data-rq-filter="${k}" aria-pressed="${state.filter === k}">${l}<span class="n">${counts[k] || 0}</span></button>`;
    el.innerHTML = `<div class="rq-head"><div><h1>My Requests</h1><p>Everything you've asked IT for, where it's up to, and who has acted on it.</p></div>
        <div class="tp-actions"><button type="button" class="btn tp-btn-ghost" data-rq-refresh>Refresh</button><button type="button" class="btn btn-primary" data-rq-new>New request</button></div></div>
      ${all.length ? `<div class="rq-filters" role="group" aria-label="Filter requests">${f("all", "All")}${f("open", "In progress")}${f("completed", "Completed")}${f("rejected", "Rejected")}</div>
        ${shown.length ? shown.map((r) => card(r, "requester")).join("") : `<div class="tp-empty">No requests in this group.</div>`}`
      : `<div class="rq-empty"><h2>You haven't made any requests yet</h2><p>Need a laptop, monitor or accessory? Request it in a minute, and follow it here from approval to delivery.</p>
          <button type="button" class="btn btn-primary" data-rq-new>Request hardware</button></div>`}`;
  }

  // ------------------------------------------------------------ My Approvals
  async function loadMyApprovals() {
    const el = document.getElementById("myApprovalsApp");
    if (!state.approvals) el.innerHTML = `<div class="card"><div class="tp-empty">Loading…</div></div>`;
    try {
      const data = await apiCall("/workflow/myApprovals");
      state.approvals = data.requests || [];
      if (data.caller) state.me = data.caller;
      renderApprovals();
    } catch (e) { el.innerHTML = errorBox(e.message); }
  }
  function renderApprovals() {
    const el = document.getElementById("myApprovalsApp"), list = state.approvals, me = state.me;
    const roles = me && me.roleLabels && me.roleLabels.length ? me.roleLabels.join(", ") : "";
    el.innerHTML = `<div class="rq-head"><div><h1>My Approvals</h1>
        <p>Requests waiting for a decision or action from you${roles ? `, as the requester's manager or in your role as ${esc(roles)}` : ""}. The longest-waiting are at the top.</p></div>
        <div class="tp-actions"><button type="button" class="btn tp-btn-ghost" data-ap-refresh>Refresh</button></div></div>
      ${list.length ? list.map((r) => card(r, "approver").replace('<div class="rq-ref">', `<div class="rq-ref">Waiting ${esc(ago(r.updatedAt || r.createdAt))} · `)).join("")
        : `<div class="rq-empty"><h2>You're all caught up</h2><p>Nothing is waiting for you. Requests appear here when someone names you as their manager, or when a step needs your IT role.</p></div>`}`;
  }
  async function act(instanceId, action, box) {
    const result = box.querySelector("[data-act-result]");
    const fields = {};
    let missing = null;
    box.querySelectorAll("[data-field]").forEach((i) => { fields[i.dataset.field] = i.value.trim(); if (!i.value.trim() && !missing) missing = i; });
    const needsReason = !!box.querySelector(`[data-reason="${action}"]`);
    const comment = needsReason ? (box.querySelector(`[data-reason="${action}"] [data-reason-text]`) || {}).value : (box.querySelector("[data-comment]") || {}).value;
    if (needsReason && !(comment || "").trim()) { result.innerHTML = errorBox("Give a reason, so the requester knows what to do next."); return; }
    if (!needsReason && missing) { result.innerHTML = errorBox(`Enter the ${missing.previousElementSibling.textContent.replace("*", "").trim().toLowerCase()} first.`); missing.focus(); return; }
    box.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try {
      const res = await apiCall("/workflow/action", { method: "POST", body: { instanceId, action, fields: needsReason ? {} : fields, comment: (comment || "").trim() || undefined } });
      const req = res.request || {};
      toast(`${req.reference || "Request"}: ${req.stateLabel || "updated"}.`);
      state.approvals = state.approvals.filter((r) => r.instanceId !== instanceId || (req.availableActions || []).length);
      if ((req.availableActions || []).length) state.approvals = state.approvals.map((r) => (r.instanceId === instanceId ? req : r));
      renderApprovals();
      state.devices = null;  // a delivery may have registered a device
      setTimeout(loadMyApprovals, 1500);  // pick up any automatic next step
    } catch (e) {
      result.innerHTML = errorBox(e.message);
      box.querySelectorAll("button").forEach((b) => { b.disabled = false; });
    }
  }

  // ------------------------------------------------------------ My Devices
  function matchesMe(asset, me) {
    const owner = String(asset.assignedUser || "").trim().toLowerCase();
    if (!owner || !me) return false;
    const upn = String(me.upn || "").toLowerCase();
    const local = upn.split("@")[0];
    const names = [upn, local, local.replace(/[._-]+/g, " "), String(me.displayName || "").toLowerCase()].filter(Boolean);
    return names.includes(owner) || names.includes(owner.replace(/[._-]+/g, " "));
  }
  // Devices from both sources: hardware CIs registered by delivered requests
  // (/api/me/devices) and the IT Asset Register's assets assigned to this person.
  async function fetchDevices() {
    const me = await loadMe();
    const [cmdb, register, reqs] = await Promise.all([
      apiCall("/me/devices").catch((e) => ({ error: e.message })),
      (async () => {
        try {
          const token = await getApiAccessToken();
          const res = await fetch(`${ASSET_API}/getAssetRegister`, { headers: { Authorization: `Bearer ${token}` } });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return await res.json();
        } catch (e) { return { error: e.message }; }
      })(),
      apiCall("/workflow/myRequests").catch(() => ({ requests: [] })),
    ]);
    // A delivered request knows the device's serial number and reference; attach them.
    const delivered = (reqs.requests || []).filter((r) => r.status === "completed" && r.serialNumber);
    const devices = [];
    (cmdb.items || []).forEach((ci) => {
      const r = delivered.find((x) => x.title === ci.name);
      devices.push({ source: "request", name: ci.name, status: ci.status, entity: ci.entity, createdAt: ci.createdAt,
        serialNumber: r && r.serialNumber, reference: r && r.reference });
    });
    (register.assets || []).filter((a) => matchesMe(a, me)).forEach((a) => devices.push({ source: "register", name: a.model || a.assetCategory || a.assetId, ...a }));
    return { list: devices, registerError: register.error, cmdbError: cmdb.error };
  }
  async function loadMyDevices() {
    const el = document.getElementById("myDevicesApp");
    if (!state.devices) el.innerHTML = `<div class="card"><div class="tp-empty">Loading your devices…</div></div>`;
    try { state.devices = await fetchDevices(); renderDevices(); }
    catch (e) { el.innerHTML = errorBox(e.message); }
  }
  function deviceIcon(d) {
    const c = String(d.assetCategory || d.name || "").toLowerCase();
    return /monitor|screen|display/.test(c) ? ICON.monitor : /phone|mobile|tablet|ipad/.test(c) ? ICON.phone : /laptop|notebook|macbook|latitude|dell|surface|thinkpad/.test(c) ? ICON.laptop : ICON.box;
  }
  function renderDevices() {
    const el = document.getElementById("myDevicesApp"), d = state.devices;
    const row = (k, v, cls) => (v ? `<dt>${k}</dt><dd class="${cls || ""}">${esc(v)}</dd>` : "");
    const human = (v) => (!v || /\s/.test(v) ? v : String(v).replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (c) => c.toUpperCase()).replace(/ ([A-Z])(?=[a-z])/g, (m, c) => " " + c.toLowerCase()));
    const intune = (s) => (/matched/i.test(s || "") ? "rq-ok" : /not found|no serial/i.test(s || "") ? "rq-warn" : "");
    const comp = (s) => (/^compliant$/i.test(s || "") ? "rq-ok" : /non|not/i.test(s || "") ? "rq-bad" : "");
    el.innerHTML = `<div class="rq-head"><div><h1>My Devices</h1><p>The CLG equipment registered to you, from your requests and the IT Asset Register.</p></div>
        <div class="tp-actions"><button type="button" class="btn tp-btn-ghost" data-dv-refresh>Refresh</button><button type="button" class="btn btn-primary" data-rq-new>Request hardware</button></div></div>
      ${d.list.length ? `<div class="rq-devices">${d.list.map((x) => `<div class="rq-dev">
          <div class="rq-dev-h"><span class="ic">${deviceIcon(x)}</span><div><div class="n">${esc(x.name)}</div>
            <div class="s">${esc([x.manufacturer, x.assetCategory].filter(Boolean).join(" · ") || (x.source === "request" ? "Delivered through a hardware request" : ""))}</div></div></div>
          <dl>${row("Asset ID", x.assetId)}${row("Serial number", x.serialNumber)}${row("Status", human(x.lifecycleStage || x.status))}
            ${row("Intune", x.intuneMatchStatus, intune(x.intuneMatchStatus))}${row("Compliance", human(x.complianceStatus), comp(x.complianceStatus))}
            ${row("Last check-in", x.lastCheckin ? fmtDate(x.lastCheckin, true) : "")}${row("Registered", x.source === "request" ? fmtDate(x.createdAt) : "")}${row("Request", x.reference)}</dl>
          <span class="rq-src">${x.source === "request" ? "From your hardware request" : "IT Asset Register"}</span></div>`).join("")}</div>`
        : `<div class="rq-empty"><h2>No devices registered to you yet</h2><p>Devices appear here once IT records them against your name, for example when a hardware request is delivered.</p>
            <button type="button" class="btn btn-primary" data-rq-new>Request hardware</button></div>`}
      <p class="rq-note">Something missing or wrong? Tell the IT team, so the asset register stays accurate.${d.registerError ? ` (The IT Asset Register couldn't be reached: ${esc(d.registerError)}.)` : ""}</p>`;
  }

  // ------------------------------------------------------------ hardware request form
  function renderForm() {
    const form = document.getElementById("hwRequestForm"); if (!form || form.dataset.v2) return;
    form.dataset.v2 = "1";
    const today = new Date().toISOString().slice(0, 10);
    form.innerHTML = `<h2>Request hardware</h2>
      <p class="subtitle">Your request goes to your manager for approval, then to IT, who order it and register it to you on delivery.</p>
      <div class="tp-form">
        <div class="tp-field tp-full"><label for="hwItem">What do you need? <span class="tp-req">*</span></label>
          <input id="hwItem" maxlength="300" placeholder="For example: Dell Latitude 5450 laptop, 24-inch monitor, USB-C dock"></div>
        <div class="tp-field"><label for="hwQty">Quantity</label><input id="hwQty" type="number" min="1" max="50" value="1"></div>
        <div class="tp-field"><label for="hwNeeded">Needed by</label><input id="hwNeeded" type="date" min="${today}"><div class="tp-hint">Optional. Leave blank if there's no deadline.</div></div>
        <div class="tp-field tp-full"><label for="hwManager">Your manager's email <span class="tp-req">*</span></label>
          <input id="hwManager" type="email" autocomplete="off" placeholder="manager@cognitionlearninggroup.com">
          <div class="tp-hint">They'll approve the request. Once IT connects the portal to Entra, your manager will be filled in automatically.</div></div>
        <div class="tp-field tp-full"><label for="hwWhy">Why do you need it?</label>
          <textarea id="hwWhy" maxlength="2000" placeholder="For example: my current laptop is failing, or I'm starting a new role"></textarea></div>
      </div>
      <div class="tp-actions" style="margin-top:1rem;"><button type="button" class="btn btn-primary" id="hwSubmitBtn">Submit request</button></div>
      <div id="hwFormResult"></div>`;
    $("#hwSubmitBtn").addEventListener("click", submitForm);
  }
  async function submitForm() {
    const out = $("#hwFormResult"), btn = $("#hwSubmitBtn");
    const fields = { itemDescription: $("#hwItem").value.trim(), quantity: $("#hwQty").value, neededBy: $("#hwNeeded").value,
      approverUpn: $("#hwManager").value.trim(), justification: $("#hwWhy").value.trim() };
    if (!fields.itemDescription) { out.innerHTML = errorBox("Describe what you need."); $("#hwItem").focus(); return; }
    if (!fields.approverUpn) { out.innerHTML = errorBox("Enter your manager's email address."); $("#hwManager").focus(); return; }
    btn.disabled = true; btn.textContent = "Submitting…"; out.innerHTML = "";
    try {
      const res = await apiCall("/workflow/start", { method: "POST", body: { workflowDefId: "HARDWARE_REQUEST", fields } });
      out.innerHTML = `<div class="rq-success" role="status"><span class="ic">✓</span><div><h3>Request ${esc(res.reference || "")} submitted</h3>
        <p>It's on its way to ${esc(fields.approverUpn)} for approval. You can follow every step in My Requests.</p>
        <button type="button" class="btn tp-btn-ghost" style="margin:0;" data-goto="myRequests">View my requests</button></div></div>`;
      ["hwItem", "hwNeeded", "hwWhy"].forEach((id) => { $("#" + id).value = ""; });
      $("#hwQty").value = "1";
      state.requests = null;
    } catch (e) { out.innerHTML = errorBox(e.message); }
    btn.disabled = false; btn.textContent = "Submit request";
  }

  // ------------------------------------------------------------ events
  function openHardwareForm() {
    document.querySelector('.tab-btn[data-view="catalogue"]').click();
    const form = document.getElementById("hwRequestForm");
    if (form.style.display === "none") document.getElementById("tile-hardware").click();
    setTimeout(() => { form.scrollIntoView({ behavior: "smooth", block: "start" }); const i = $("#hwItem"); if (i) i.focus({ preventScroll: true }); }, 50);
  }
  document.addEventListener("click", (ev) => {
    const t = ev.target.closest("button"); if (!t) return;
    const d = t.dataset;
    if (d.rqNew !== undefined) return openHardwareForm();
    if (d.goto) return document.querySelector(`.tab-btn[data-view="${d.goto}"]`).click();
    if (d.rqRefresh !== undefined) return loadMyRequests();
    if (d.apRefresh !== undefined) return loadMyApprovals();
    if (d.dvRefresh !== undefined) { state.devices = null; return loadMyDevices(); }
    if (d.rqFilter) { state.filter = d.rqFilter; return renderRequests(); }
    if (d.rqHistory) {
      const box = t.nextElementSibling, open = box.hidden;
      box.hidden = !open; t.setAttribute("aria-expanded", String(open)); t.textContent = open ? "Hide history" : "Show history";
      return;
    }
    const actBox = t.closest("[data-act]");
    if (actBox) {
      if (d.ask) { actBox.querySelectorAll("[data-reason]").forEach((r) => { r.hidden = r.dataset.reason !== d.ask; }); const ta = actBox.querySelector(`[data-reason="${d.ask}"] textarea`); if (ta) ta.focus(); return; }
      if (d.cancelAsk !== undefined) { actBox.querySelectorAll("[data-reason]").forEach((r) => { r.hidden = true; }); return; }
      if (d.do) return act(actBox.dataset.act, d.do, actBox);
    }
  });

  renderForm();
  // Show the caller's roles in the header once the background sign-in check finds them.
  let tries = 0;
  const watch = setInterval(() => {
    if (typeof signedInAccount !== "undefined" && signedInAccount) { clearInterval(watch); loadMe(); }
    else if (++tries > 30) clearInterval(watch);
  }, 500);
  window.PortalDevices = { fetch: fetchDevices };
  window.loadMyRequests = loadMyRequests;
  window.loadMyApprovals = loadMyApprovals;
  window.loadMyDevices = loadMyDevices;
})();
