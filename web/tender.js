/*
 * IT Helpdesk Portal — Tender Pack (Batch I, HD-054–058 widened)
 * -------------------------------------------------------------
 * Three views inside the "Tender Pack" tab:
 *   New pack       bid details → review matched answers → issue pack
 *   Answer library approved wording, evidence links, approval
 *   Issued packs   every pack as issued (audit record), re-openable
 *
 * Depends on index.html globals: apiCall(path, options) (adds the Entra
 * token) and window.getSignedInUserName(). All server rules are enforced in
 * api/tender_api.py; checks here only make the UI explain them early.
 * Every value from the API is escaped before it is put into the page.
 */
(function () {
  "use strict";

  const EXAMPLE_QUESTIONS = [
    "1. Does your organisation hold a current Cyber Essentials Plus certificate?",
    "2. Do you hold Cyber Essentials certification?",
    "3. Are you registered with the ICO? Please provide your registration number.",
    "4. Do you have a documented information security policy?",
    "5. Is multi-factor authentication enforced for all staff?",
    "6. How do you ensure laptops are encrypted and managed?",
    "7. What is your process for reporting a data breach to the client?",
    "8. What is your annual turnover?",
  ].join("\n");

  const STATUS_LABEL = { ready: "Ready", needs_review: "Check answer", blocked: "Blocked", unmatched: "No answer yet" };
  const STAT_LABEL = { ready: "Ready to use", needs_review: "Need your check", blocked: "Blocked by evidence", unmatched: "No library answer" };

  const state = {
    view: "new", step: 1, loadedEvidence: false, evidence: [],
    bid: { clientName: "", bidReference: "", deadline: "", questions: "" },
    items: [], filter: "all", pack: null, busy: false, error: "",
    library: null, libQuery: "", libCategory: "", libStatus: "", packs: null,
  };

  // ---------------------------------------------------------------- helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtDate(iso) {
    if (!iso) return "";
    const s = String(iso);
    const y = s.slice(0, 4), m = Number(s.slice(5, 7)), d = Number(s.slice(8, 10));
    return m ? `${d} ${MONTHS[m - 1]} ${y}` : s;
  }
  function fmtDateTime(iso) {
    if (!iso) return "";
    const t = new Date(iso);
    return isNaN(t) ? fmtDate(iso) : `${fmtDate(iso)}, ${t.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
  }
  function todayIso() { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
  function addDays(iso, n) { const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
  const hasPlaceholder = (t) => /\[confirm/i.test(t || "");
  const userName = () => (typeof window.getSignedInUserName === "function" && window.getSignedInUserName()) || "You (signed-in user)";
  function toast(msg) {
    const el = document.createElement("div");
    el.className = "tp-toast"; el.setAttribute("role", "status"); el.textContent = msg;
    document.body.appendChild(el); setTimeout(() => el.remove(), 2600);
  }
  async function api(path, options) { return apiCall(path, options); }

  // Mirrors tender_api.resolve_evidence: exact title first, else the shortest
  // title starting with the key, so "Cyber Essentials" never resolves to
  // "Cyber Essentials Plus".
  function resolveDoc(key) {
    const k = String(key || "").trim().toLowerCase();
    if (!k) return null;
    const exact = state.evidence.find((d) => d.title.trim().toLowerCase() === k);
    if (exact) return exact;
    return state.evidence.filter((d) => d.title.trim().toLowerCase().startsWith(k)).sort((x, y) => x.title.length - y.title.length)[0] || null;
  }

  function chipClass(status) {
    if (status === "valid" || status === "current") return "ok";
    if (status === "expired" || status === "expires_before_deadline") return "bad";
    if (status === "missing") return "none";
    return "warn";
  }
  function chipText(e) {
    const t = e.title || e.key;
    switch (e.status) {
      case "valid": return `${t} – valid to ${fmtDate(e.expiryDate)}`;
      case "expired": return `${t} – expired ${fmtDate(e.expiryDate)}`;
      case "expires_before_deadline": return `${t} – expires ${fmtDate(e.expiryDate)}`;
      case "current": return `${t}${e.currentVersion ? " – " + e.currentVersion : ""}`;
      case "review_overdue": return `${t} – review overdue`;
      case "missing": return `${t} – not found`;
      default: return `${t} – check record`;
    }
  }
  function chip(e) {
    const cls = chipClass(e.status);
    const title = esc(e.message || "");
    return e.documentUrl
      ? `<a class="tp-chip ${cls}" href="${esc(e.documentUrl)}" target="_blank" rel="noopener" title="${title}">${esc(chipText(e))}</a>`
      : `<span class="tp-chip ${cls}" title="${title}">${esc(chipText(e))}</span>`;
  }
  // Mirrors tender_api.evidence_status for the Step 1 overview only.
  function certStatusOnDeadline(doc, deadline) {
    const today = todayIso();
    if (!doc.expiryDate) return { ...doc, status: "unknown" };
    if (doc.expiryDate < today) return { ...doc, status: "expired" };
    if (deadline && doc.expiryDate < deadline) return { ...doc, status: "expires_before_deadline" };
    return { ...doc, status: "valid" };
  }

  // Effective status after the preparer's edits (server re-checks on issue).
  function effective(item) {
    if (item.status === "unmatched") return (item.answerText || "").trim() ? "needs_review" : "unmatched";
    return item.status;
  }
  function itemProblem(item) {
    if (!item.include) return null;
    const st = effective(item);
    if (!(item.answerText || "").trim()) return "empty";
    if (st === "blocked") return "blocked";
    if (hasPlaceholder(item.answerText)) return "placeholder";
    if (st === "needs_review" && !item.reviewed) return "unchecked";
    return null;
  }

  // ------------------------------------------------------------ rendering
  function root() { return document.getElementById("tenderApp"); }

  function render() {
    const r = root(); if (!r) return;
    const seg = (id, label) => `<button type="button" data-tp-view="${id}" aria-pressed="${state.view === id}">${label}</button>`;
    r.innerHTML = `
      <div class="tp-head">
        <div>
          <h1>Tender Pack</h1>
          <p>Answer a bid's IT and security questions with approved wording, checked against certificates and policies that are valid on the submission deadline.</p>
        </div>
        <div class="tp-seg" role="group" aria-label="Tender Pack sections">${seg("new", "New pack")}${seg("library", "Answer library")}${seg("packs", "Issued packs")}</div>
      </div>
      ${state.error ? `<div class="error-box" role="alert">${esc(state.error)}</div>` : ""}
      <div id="tpBody">${state.view === "new" ? renderNew() : state.view === "library" ? renderLibrary() : renderPacks()}</div>`;
  }

  function stepper() {
    const cls = (n) => (state.step === n ? "is-current" : state.step > n ? "is-done" : "");
    return `<ol class="tp-steps" aria-label="Progress">
      <li class="${cls(1)}" ${state.step === 1 ? 'aria-current="step"' : ""}>Bid details</li>
      <li class="${cls(2)}" ${state.step === 2 ? 'aria-current="step"' : ""}>Review answers</li>
      <li class="${cls(3)}" ${state.step === 3 ? 'aria-current="step"' : ""}>Issue pack</li></ol>`;
  }

  function renderNew() {
    return stepper() + (state.step === 1 ? renderStep1() : state.step === 2 ? renderStep2() : renderStep3());
  }

  function renderStep1() {
    const b = state.bid;
    const certs = state.evidence.filter((e) => e.kind === "Certificate").map((c) => certStatusOnDeadline(c, b.deadline));
    const health = !state.loadedEvidence ? `<p class="tp-hint">Loading certificate status…</p>`
      : certs.length ? `<div class="tp-chips">${certs.map(chip).join("")}</div>
          <p class="tp-hint">Checked against the submission deadline${b.deadline ? ` of ${esc(fmtDate(b.deadline))}` : ""}. Answers that rely on a certificate in red cannot go into the pack.</p>`
      : `<p class="tp-hint">No certificates are recorded in Policy &amp; Compliance yet.</p>`;
    return `<div class="card">
      <div class="tp-form">
        <div class="tp-field"><label for="tpClient">Client or buyer <span class="tp-req" aria-hidden="true">*</span></label>
          <input id="tpClient" data-bid="clientName" value="${esc(b.clientName)}" autocomplete="off" placeholder="For example, Example County Council"></div>
        <div class="tp-field"><label for="tpRef">Bid reference</label>
          <input id="tpRef" data-bid="bidReference" value="${esc(b.bidReference)}" autocomplete="off" placeholder="The buyer's tender or lot number"></div>
        <div class="tp-field"><label for="tpDeadline">Submission deadline <span class="tp-req" aria-hidden="true">*</span></label>
          <input id="tpDeadline" type="date" data-bid="deadline" value="${esc(b.deadline)}" min="${todayIso()}"></div>
        <div class="tp-field"><label for="tpBy">Prepared by</label>
          <input id="tpBy" value="${esc(userName())}" readonly><div class="tp-hint">Taken from your Microsoft sign-in.</div></div>
        <div class="tp-field tp-full"><label for="tpQuestions">IT and security questions <span class="tp-req" aria-hidden="true">*</span></label>
          <textarea id="tpQuestions" data-bid="questions" placeholder="Paste the questions from the tender, one per line.">${esc(b.questions)}</textarea>
          <div class="tp-hint">Numbering and bullets are removed automatically. Up to 200 questions. <button type="button" class="tp-link" data-tp-action="example">Use example questions</button></div></div>
      </div>
      <div class="tp-health"><h3>Certificates on the deadline</h3>${health}</div>
      <div class="tp-actions" style="margin-top:1.25rem;">
        <button type="button" class="btn btn-primary" data-tp-action="match" ${state.busy ? "disabled" : ""}>${state.busy ? "Finding answers…" : "Find answers"}</button>
      </div></div>`;
  }

  function renderStep2() {
    const counts = { ready: 0, needs_review: 0, blocked: 0, unmatched: 0 };
    state.items.forEach((i) => { counts[effective(i)] = (counts[effective(i)] || 0) + 1; });
    const stat = (k) => `<button type="button" class="tp-stat ${k}" data-tp-filter="${k}" aria-pressed="${state.filter === k}">
        <div class="n">${counts[k]}</div><div class="l">${STAT_LABEL[k]}</div></button>`;
    const shown = state.items.filter((i) => state.filter === "all" || effective(i) === state.filter);
    const b = state.bid;
    return `
      <div class="tp-meta"><span><strong>${esc(b.clientName)}</strong></span>${b.bidReference ? `<span>Ref ${esc(b.bidReference)}</span>` : ""}
        <span>Deadline <strong>${esc(fmtDate(b.deadline))}</strong></span><span>${state.items.length} questions</span>
        ${state.filter !== "all" ? `<button type="button" class="tp-link" data-tp-filter="all">Show all questions</button>` : ""}</div>
      <div class="tp-stats">${stat("ready")}${stat("needs_review")}${stat("blocked")}${stat("unmatched")}</div>
      ${shown.length ? shown.map(renderItem).join("") : `<div class="tp-empty">No questions in this group.</div>`}
      ${renderBar()}`;
  }

  function renderItem(item) {
    const st = effective(item);
    const i = item.index;
    const a = item.answer;
    const alts = (item.alternatives || []);
    const src = a ? `<span>From library: “${esc(a.question)}”</span>
        <span>${esc(item.confidence)} match</span><span>${a.status === "Approved" ? "Approved answer" : "Draft answer"}</span>` : "";
    const altSelect = alts.length ? `<label><span class="tp-hint" style="margin:0 .3rem 0 0;">Use instead:</span>
        <select data-tp-alt="${i}" aria-label="Use a different library answer for question ${i}"><option value="">Choose another answer…</option>
        ${alts.map((x) => `<option value="${esc(x.answerId)}">${esc(x.question)} (${esc(x.confidence)})</option>`).join("")}</select></label>` : "";
    let reasons = [...(item.reasons || [])];
    if (item.status === "unmatched" && (item.answerText || "").trim()) reasons = ["Written for this bid, not from the approved library."];
    if (hasPlaceholder(item.answerText) && !reasons.some((r) => r.includes("[confirm"))) reasons.unshift("Replace the [confirm: …] text with verified facts.");
    const ev = (item.evidence || []);
    const needsCheck = st === "needs_review";
    return `<article class="tp-q ${st} ${item.include ? "" : "is-excluded"}" data-item="${i}" aria-label="Question ${i}">
      <div class="tp-q-head"><span class="tp-q-num">Q${i}</span><div class="tp-q-text">${esc(item.question)}</div>
        <span class="tp-status ${st}">${STATUS_LABEL[st]}</span></div>
      <div class="tp-q-body">
        <textarea data-tp-text="${i}" aria-label="Answer to question ${i}" class="${hasPlaceholder(item.answerText) ? "has-placeholder" : ""}"
          placeholder="No approved answer matches. Write one for this bid, or leave this question out.">${esc(item.answerText)}</textarea>
        ${src || altSelect ? `<div class="tp-src">${src}${altSelect}</div>` : ""}
        ${reasons.length ? `<ul class="tp-reasons">${reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
        ${ev.length ? `<div class="tp-ev"><span class="tp-ev-label">Evidence</span><span class="tp-chips" style="display:inline-flex;">${ev.map(chip).join("")}</span></div>` : ""}
      </div>
      <div class="tp-q-foot">
        <label><input type="checkbox" data-tp-include="${i}" ${item.include ? "checked" : ""} ${st === "blocked" ? "disabled" : ""}> Include in pack</label>
        ${needsCheck ? `<label><input type="checkbox" data-tp-reviewed="${i}" ${item.reviewed ? "checked" : ""} ${item.include ? "" : "disabled"}> I have checked this answer</label>` : ""}
        ${st === "blocked" ? `<span class="tp-hint" style="margin:0;">Cannot be included until the evidence is renewed.</span>` : ""}
      </div></article>`;
  }

  function renderBar() {
    const included = state.items.filter((i) => i.include);
    const problems = state.items.map(itemProblem).filter(Boolean);
    const unchecked = problems.filter((p) => p === "unchecked").length;
    const placeholders = problems.filter((p) => p === "placeholder").length;
    const empty = problems.filter((p) => p === "empty").length;
    const parts = [];
    if (unchecked) parts.push(`${unchecked} to check`);
    if (placeholders) parts.push(`${placeholders} with [confirm] text`);
    if (empty) parts.push(`${empty} without an answer`);
    const ok = included.length > 0 && problems.length === 0;
    return `<div class="tp-bar">
      <div class="tp-bar-msg"><strong>${included.length} of ${state.items.length}</strong> questions in the pack${parts.length ? ` · <span class="warn">${parts.join(", ")}</span>` : ""}</div>
      <div class="tp-actions">
        <button type="button" class="btn tp-btn-ghost" data-tp-action="back">Back to bid details</button>
        <button type="button" class="btn btn-primary" data-tp-action="issue" ${ok && !state.busy ? "" : "disabled"}>${state.busy ? "Issuing…" : "Issue pack"}</button>
      </div></div>`;
  }

  function renderStep3() {
    const p = state.pack; const s = p.snapshot;
    const files = (s.evidenceAppendix || []).filter((e) => e.kind === "Certificate");
    return `<div class="tp-banner" role="status">
        <div><h2>Pack ${esc(p.packRef)} issued</h2><p>${s.summary.questions} answers for ${esc(s.clientName)}, saved to Issued packs as the record of what was sent.</p></div>
        <div class="tp-actions">
          <button type="button" class="btn btn-primary" data-tp-action="word">Download Word</button>
          <button type="button" class="btn tp-btn-ghost" data-tp-action="print">Print or save as PDF</button>
          <button type="button" class="btn tp-btn-ghost" data-tp-action="copy">Copy answers</button>
          <button type="button" class="btn tp-btn-ghost" data-tp-action="restart">Start a new pack</button>
        </div></div>
      ${files.length ? `<div class="tp-attach"><h3>Attach these certificates to the submission</h3>
        <p>The pack lists them as evidence. The links open CLG's SharePoint copies, which the buyer cannot open, so attach the files themselves.</p>
        <div class="tp-chips">${files.map(chip).join("")}</div></div>` : ""}
      <div class="tp-paper">${renderPackDocument(s)}</div>`;
  }

  // ------------------------------------------------------ the pack document
  // Inline styles only, so the same HTML renders in the preview, in Word and in print.
  function renderPackDocument(s) {
    const orange = "#F47B20", grey = "#5F6062", ink = "#333333", muted = "#6b6b6b", rule = "#e3e3e3";
    const font = "font-family:'Segoe UI',Arial,sans-serif;";
    const th = `style="text-align:left;padding:6pt 8pt;border-bottom:1pt solid ${grey};font-size:9pt;color:${grey};${font}"`;
    const td = `style="padding:6pt 8pt;border-bottom:0.5pt solid ${rule};font-size:9.5pt;vertical-align:top;color:${ink};${font}"`;
    const evidenceRows = (s.evidenceAppendix || []).map((e) => `<tr>
        <td ${td}><b>${esc(e.title)}</b><br><span style="color:${muted};font-size:8.5pt;">${esc(e.kind)}</span></td>
        <td ${td}>${esc(e.currentVersion || "")}</td>
        <td ${td}>${e.kind === "Certificate" ? `Valid until ${esc(fmtDate(e.expiryDate))}` : esc(e.approvalStatus || "Approved")}${e.kind === "Policy" && e.nextReviewDate ? `<br><span style="color:${muted};font-size:8.5pt;">Next review ${esc(fmtDate(e.nextReviewDate))}</span>` : ""}</td></tr>`).join("");
    const answers = s.items.map((it) => {
      const ev = (it.evidence || []).filter((e) => e.kind).map((e) => e.kind === "Certificate"
        ? `${esc(e.title)} (valid until ${esc(fmtDate(e.expiryDate))})` : `${esc(e.title)}${e.currentVersion ? ` (${esc(e.currentVersion)})` : ""}`);
      return `<div style="margin:0 0 14pt;page-break-inside:avoid;">
        <p style="margin:0 0 3pt;font-size:8.5pt;color:${orange};font-weight:700;letter-spacing:0.02em;${font}">${esc(it.category)}</p>
        <p style="margin:0 0 5pt;font-size:10.5pt;font-weight:700;color:${grey};${font}">Q${it.number}. ${esc(it.question)}</p>
        <p style="margin:0 0 5pt;font-size:10pt;line-height:1.5;color:${ink};${font}">${esc(it.answerText).replace(/\n/g, "<br>")}</p>
        ${ev.length ? `<p style="margin:0;font-size:8.5pt;color:${muted};${font}">Supporting evidence: ${ev.join("; ")}</p>` : ""}</div>`;
    }).join("");
    const meta = (k, v) => v ? `<tr><td style="padding:3pt 14pt 3pt 0;font-size:9pt;color:${muted};${font}">${k}</td><td style="padding:3pt 0;font-size:9.5pt;color:${ink};font-weight:600;${font}">${esc(v)}</td></tr>` : "";
    return `<div style="${font}color:${ink};">
      <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;">
        <tr><td bgcolor="${orange}" style="background:${orange};height:8pt;line-height:8pt;font-size:4pt;">&nbsp;</td></tr>
        <tr><td bgcolor="${grey}" style="background:${grey};padding:26pt 34pt 22pt;color:#ffffff;">
          <p style="margin:0;font-size:20pt;font-weight:700;line-height:1.1;color:#ffffff;${font}">Cognition</p>
          <p style="margin:2pt 0 0;font-size:11pt;font-weight:300;color:#ffffff;${font}">Learning Group<span style="color:${orange};font-weight:700;"> ›</span></p>
          <p style="margin:26pt 0 4pt;font-size:18pt;font-weight:600;color:#ffffff;${font}">IT and Information Security Response</p>
          <p style="margin:0;font-size:11pt;color:#f0f0f0;${font}">Prepared for ${esc(s.clientName)}</p>
        </td></tr></table>
      <div style="padding:20pt 34pt 30pt;">
        <table style="border-collapse:collapse;margin:0 0 18pt;">${meta("Bid reference", s.bidReference)}${meta("Submission deadline", fmtDate(s.deadline))}
          ${meta("Pack reference", s.packRef)}${meta("Prepared by", s.preparedBy)}${meta("Issued", fmtDate(s.createdAt))}</table>
        ${evidenceRows ? `<p style="margin:0 0 6pt;font-size:12pt;font-weight:700;color:${grey};${font}">Assurance summary</p>
        <p style="margin:0 0 8pt;font-size:9.5pt;color:${muted};${font}">Certificates and policies referred to in this response, each confirmed as valid on the submission deadline.</p>
        <table style="border-collapse:collapse;width:100%;margin:0 0 20pt;"><tr><th ${th}>Evidence</th><th ${th}>Reference</th><th ${th}>Status</th></tr>${evidenceRows}</table>` : ""}
        <p style="margin:0 0 10pt;font-size:12pt;font-weight:700;color:${grey};border-bottom:1.5pt solid ${orange};padding-bottom:4pt;${font}">Responses</p>
        ${answers}
        <p style="margin:22pt 0 0;padding-top:8pt;border-top:0.5pt solid ${rule};font-size:8pt;color:${muted};${font}">Commercial in confidence. Prepared by Cognition Learning Group from its approved answer library and live certificate and policy records. Pack ${esc(s.packRef)}.</p>
      </div></div>`;
  }

  function packFileName(s) { return `${s.packRef} ${s.clientName}`.replace(/[\\/:*?"<>|]+/g, "-").slice(0, 120); }
  function downloadWord(s) {
    const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
      <head><meta charset="utf-8"><title>${esc(s.packRef)}</title><!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->
      <style>@page { size: 21cm 29.7cm; margin: 1.6cm; } body { margin: 0; }</style></head><body>${renderPackDocument(s)}</body></html>`;
    const blob = new Blob(["\ufeff", html], { type: "application/msword" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = packFileName(s) + ".doc";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  function printPack(s) {
    const w = window.open("", "_blank");
    if (!w) { toast("Allow pop-ups for the portal to print the pack."); return; }
    w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(packFileName(s))}</title>
      <style>@page { size: A4; margin: 14mm; } body { margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }</style></head>
      <body>${renderPackDocument(s)}<script>window.onload = function () { window.print(); };<\/script></body></html>`);
    w.document.close();
  }
  async function copyAnswers(s) {
    const text = s.items.map((it) => `Q${it.number}. ${it.question}\n${it.answerText}`).join("\n\n");
    try { await navigator.clipboard.writeText(text); toast("Answers copied to the clipboard."); }
    catch (e) { toast("Copy failed. Use Download Word instead."); }
  }

  // ---------------------------------------------------------- answer library
  function renderLibrary() {
    if (!state.library) return `<div class="card"><div class="tp-empty">Loading the answer library…</div></div>`;
    const cats = [...new Set(state.library.map((a) => a.category))].sort();
    const q = state.libQuery.toLowerCase();
    const rows = state.library.filter((a) => (!state.libCategory || a.category === state.libCategory)
      && (!state.libStatus || a.status === state.libStatus)
      && (!q || (a.question + " " + a.answerText + " " + a.keywords.join(" ")).toLowerCase().includes(q)));
    const draftCount = state.library.filter((a) => a.status === "Draft").length;
    const evChips = (a) => a.evidence.length ? a.evidence.map((k) => {
      const doc = resolveDoc(k);
      return `<span class="tp-chip ${doc ? "ok" : "none"}">${esc(doc ? doc.title : k + " (not found)")}</span>`;
    }).join(" ") : `<span class="tp-hint" style="margin:0;">None</span>`;
    return `<div class="card">
      ${draftCount ? `<div class="tp-reasons" style="background:var(--tp-review-bg);color:#6b3d00;list-style:none;padding-left:.75rem;margin:0 0 1rem;">
        ${draftCount} of ${state.library.length} answers are drafts. Packs can use them only after the preparer checks each one; approve answers here to make them ready to use.</div>` : ""}
      <div class="tp-toolbar">
        <input type="search" data-lib="libQuery" value="${esc(state.libQuery)}" placeholder="Search questions, answers and keywords" aria-label="Search the answer library">
        <select data-lib="libCategory" aria-label="Filter by category"><option value="">All categories</option>${cats.map((c) => `<option ${c === state.libCategory ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <select data-lib="libStatus" aria-label="Filter by status"><option value="">All statuses</option>${["Approved", "Draft"].map((s) => `<option ${s === state.libStatus ? "selected" : ""}>${s}</option>`).join("")}</select>
        <button type="button" class="btn btn-primary" data-tp-action="new-answer">Add answer</button>
      </div>
      <div class="tp-table-wrap"><table class="tp-table"><thead><tr><th>Question and answer</th><th>Evidence</th><th>Status</th><th>Last change</th><th></th></tr></thead><tbody>
      ${rows.length ? rows.map((a) => `<tr>
        <td><span class="tp-cat">${esc(a.category)}</span><span class="tp-q-cell">${esc(a.question)}</span>
          <span class="tp-ans-preview">${esc(a.answerText.length > 160 ? a.answerText.slice(0, 157) + "…" : a.answerText)}</span></td>
        <td style="min-width:150px;">${evChips(a)}</td>
        <td><span class="tp-status ${a.status === "Approved" ? "ready" : "needs_review"}">${esc(a.status)}</span>
          ${hasPlaceholder(a.answerText) ? `<span class="tp-hint" style="display:block;">Has [confirm] text</span>` : ""}</td>
        <td style="white-space:nowrap;font-size:.8rem;color:var(--muted);">${esc(fmtDate(a.approvedAt || a.updatedAt))}<br>${esc(a.approvedBy || a.updatedBy || "Seed library")}</td>
        <td class="tp-row-actions"><button type="button" class="tp-link" data-tp-edit="${esc(a.answerId)}">Edit</button>
          ${a.status !== "Approved" ? `<button type="button" class="tp-link" data-tp-approve="${esc(a.answerId)}" ${hasPlaceholder(a.answerText) ? 'disabled title="Replace the [confirm] text first"' : ""}>Approve</button>` : ""}</td></tr>`).join("")
        : `<tr><td colspan="5"><div class="tp-empty">No answers match these filters.</div></td></tr>`}
      </tbody></table></div></div>`;
  }

  function openAnswerEditor(answer) {
    const a = answer || { answerId: "", category: "", question: "", answerText: "", keywords: [], evidence: [], status: "Draft", reviewDate: "" };
    const cats = [...new Set((state.library || []).map((x) => x.category))].sort();
    const selected = new Set(a.evidence.map(resolveDoc).filter(Boolean).map((d) => d.title));
    const evOptions = state.evidence.map((d) => {
      const on = selected.has(d.title);
      return `<label><input type="checkbox" name="tpEv" value="${esc(d.title)}" ${on ? "checked" : ""}> <span>${esc(d.title)}<br><span class="tp-hint" style="margin:0;">${esc(d.kind)}</span></span></label>`;
    }).join("");
    const wasApproved = a.status === "Approved";
    showModal(`<div class="tp-modal-box" role="dialog" aria-modal="true" aria-labelledby="tpEdTitle">
      <div class="tp-modal-head"><h2 id="tpEdTitle">${answer ? "Edit answer" : "Add answer"}</h2><button type="button" class="tp-close" data-tp-close aria-label="Close">×</button></div>
      <div class="tp-modal-body"><div class="tp-form">
        <div class="tp-field"><label for="edCat">Category</label><input id="edCat" list="edCats" value="${esc(a.category)}"><datalist id="edCats">${cats.map((c) => `<option value="${esc(c)}">`).join("")}</datalist></div>
        <div class="tp-field"><label for="edReview">Review by</label><input id="edReview" type="date" value="${esc(a.reviewDate || "")}"></div>
        <div class="tp-field tp-full"><label for="edQ">Typical question</label><input id="edQ" value="${esc(a.question)}"></div>
        <div class="tp-field tp-full"><label for="edText">Answer wording</label><textarea id="edText" style="min-height:150px;">${esc(a.answerText)}</textarea>
          <div class="tp-hint">Write [confirm: …] for anything not yet verified; it blocks approval until replaced.${wasApproved ? " Changing the wording or evidence sends the answer back to Draft for re-approval." : ""}</div></div>
        <div class="tp-field tp-full"><label for="edKw">Keywords</label><input id="edKw" value="${esc(a.keywords.join(", "))}"><div class="tp-hint">Comma-separated words and phrases buyers use for this question.</div></div>
        <div class="tp-field tp-full"><label>Evidence</label>${evOptions ? `<div class="tp-checks">${evOptions}</div>` : `<p class="tp-hint">No Policy &amp; Compliance records found.</p>`}</div>
        ${answer ? `<div class="tp-field"><label for="edStatus">Status</label><select id="edStatus">
          ${(wasApproved ? ["Approved", "Draft", "Retired"] : ["Draft", "Retired"]).map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select></div>` : ""}
      </div><div id="edErr"></div></div>
      <div class="tp-modal-foot"><button type="button" class="btn tp-btn-ghost" data-tp-close>Cancel</button>
        <button type="button" class="btn btn-primary" id="edSave">Save</button></div></div>`);
    $("#edSave").onclick = async () => {
      const body = {
        answerId: a.answerId || undefined, category: $("#edCat").value, question: $("#edQ").value, answerText: $("#edText").value,
        keywords: $("#edKw").value, reviewDate: $("#edReview").value || null, owner: a.owner,
        evidence: [...document.querySelectorAll('input[name="tpEv"]:checked')].map((x) => x.value),
        status: $("#edStatus") ? $("#edStatus").value : "Draft",
      };
      $("#edSave").disabled = true;
      try {
        await api("/tender/library", { method: "POST", body });
        closeModal(); await loadLibrary(true); toast("Answer saved.");
      } catch (e) { $("#edErr").innerHTML = `<div class="error-box" role="alert">${esc(e.message)}</div>`; $("#edSave").disabled = false; }
    };
  }

  // ------------------------------------------------------------ issued packs
  function renderPacks() {
    if (!state.packs) return `<div class="card"><div class="tp-empty">Loading issued packs…</div></div>`;
    if (!state.packs.length) return `<div class="card"><div class="tp-empty">No packs issued yet. Start one from New pack.</div></div>`;
    return `<div class="card"><div class="tp-table-wrap"><table class="tp-table"><thead><tr>
      <th>Pack</th><th>Client</th><th>Deadline</th><th>Answers</th><th>Prepared by</th><th>Issued</th></tr></thead><tbody>
      ${state.packs.map((p) => `<tr class="tp-row-click" tabindex="0" data-tp-pack="${esc(p.packId)}">
        <td><b>${esc(p.packRef)}</b>${p.bidReference ? `<br><span class="tp-hint" style="margin:0;">${esc(p.bidReference)}</span>` : ""}</td>
        <td>${esc(p.clientName)}</td><td style="white-space:nowrap;">${esc(fmtDate(p.deadline))}</td>
        <td>${p.summary.questions}${p.summary.edited ? `<br><span class="tp-hint" style="margin:0;">${p.summary.edited} edited</span>` : ""}</td>
        <td>${esc(p.preparedBy)}</td><td style="white-space:nowrap;">${esc(fmtDateTime(p.createdAt))}</td></tr>`).join("")}
      </tbody></table></div></div>`;
  }

  async function openPack(packId) {
    try {
      const { pack } = await api(`/tender/packs/${encodeURIComponent(packId)}`);
      const s = pack.snapshot;
      showModal(`<div class="tp-modal-box wide" role="dialog" aria-modal="true" aria-labelledby="tpPkTitle">
        <div class="tp-modal-head"><h2 id="tpPkTitle">${esc(s.packRef)} – ${esc(s.clientName)}</h2>
          <div class="tp-actions"><button type="button" class="btn btn-primary" id="pkWord">Download Word</button>
            <button type="button" class="btn tp-btn-ghost" id="pkPrint">Print or save as PDF</button>
            <button type="button" class="tp-close" data-tp-close aria-label="Close">×</button></div></div>
        <div class="tp-modal-body"><div class="tp-paper">${renderPackDocument(s)}</div></div></div>`);
      $("#pkWord").onclick = () => downloadWord(s);
      $("#pkPrint").onclick = () => printPack(s);
    } catch (e) { toast(e.message); }
  }

  // ------------------------------------------------------------------ modal
  function showModal(html) {
    closeModal();
    const m = document.createElement("div");
    m.className = "tp-modal"; m.id = "tpModal"; m.innerHTML = html;
    m.addEventListener("click", (ev) => { if (ev.target === m || ev.target.closest("[data-tp-close]")) closeModal(); });
    document.body.appendChild(m);
    const first = m.querySelector("input, textarea, select, button.btn-primary");
    if (first) first.focus();
  }
  function closeModal() { const m = document.getElementById("tpModal"); if (m) m.remove(); }
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") closeModal(); });

  // ----------------------------------------------------------------- loaders
  async function loadEvidence() {
    try { state.evidence = (await api("/tender/evidence")).evidence || []; }
    catch (e) { state.evidence = []; state.error = e.message; }
    state.loadedEvidence = true;
  }
  async function loadLibrary(force) {
    if (state.library && !force) return;
    try {
      const [lib] = await Promise.all([api("/tender/library"), state.loadedEvidence ? null : loadEvidence()]);
      state.library = lib.answers || [];
    } catch (e) { state.error = e.message; state.library = []; }
    render();
  }
  async function loadPacks() {
    try { state.packs = (await api("/tender/packs")).packs || []; } catch (e) { state.error = e.message; state.packs = []; }
    render();
  }

  // ----------------------------------------------------------------- actions
  async function findAnswers() {
    const b = state.bid; state.error = "";
    if (!b.clientName.trim()) state.error = "Enter the client or buyer name.";
    else if (!b.deadline) state.error = "Enter the submission deadline.";
    else if (b.deadline < todayIso()) state.error = "The submission deadline is in the past.";
    else if (!b.questions.trim()) state.error = "Paste at least one question.";
    if (state.error) { render(); return; }
    state.busy = true; render();
    try {
      const res = await api("/tender/match", { method: "POST", body: { deadline: b.deadline, questions: b.questions } });
      state.items = res.items.map((i) => ({ ...i, include: i.status !== "blocked" && i.status !== "unmatched", reviewed: false }));
      state.step = 2; state.filter = "all";
      window.scrollTo({ top: 0 });
    } catch (e) { state.error = e.message; }
    state.busy = false; render();
  }

  async function issuePack() {
    state.busy = true; state.error = ""; render();
    try {
      const body = {
        clientName: state.bid.clientName, bidReference: state.bid.bidReference, deadline: state.bid.deadline,
        items: state.items.map((i) => ({ question: i.question, answerId: i.answer ? i.answer.answerId : null,
          answerText: i.answerText, include: i.include, reviewed: i.reviewed })),
      };
      const res = await api("/tender/packs", { method: "POST", body });
      state.pack = res.pack; state.step = 3; state.packs = null;
      window.scrollTo({ top: 0 });
    } catch (e) { state.error = e.message; }
    state.busy = false; render();
  }

  async function swapAnswer(index, answerId) {
    const item = state.items.find((i) => i.index === index);
    if (!item || !answerId) return;
    try {
      const res = await api("/tender/evaluate", { method: "POST", body: { question: item.question, answerId, deadline: state.bid.deadline } });
      const previous = item.answer;
      Object.assign(item, res, { include: res.status !== "blocked", reviewed: false });
      item.alternatives = (item.alternatives || []).filter((x) => x.answerId !== answerId);
      if (previous) item.alternatives.unshift({ answerId: previous.answerId, question: previous.question, confidence: "Previous" });
    } catch (e) { toast(e.message); }
    render();
  }

  async function approve(answerId) {
    try { await api(`/tender/library/${encodeURIComponent(answerId)}/approve`, { method: "POST", body: {} }); await loadLibrary(true); toast("Answer approved."); }
    catch (e) { toast(e.message); }
  }

  // Patch only the parts of a card that change while typing, so focus and cursor stay put.
  function refreshCard(index) {
    const item = state.items.find((i) => i.index === index);
    const card = document.querySelector(`.tp-q[data-item="${index}"]`);
    if (!item || !card) return;
    const st = effective(item);
    card.className = `tp-q ${st} ${item.include ? "" : "is-excluded"}`;
    const pill = card.querySelector(".tp-status"); pill.className = `tp-status ${st}`; pill.textContent = STATUS_LABEL[st];
    card.querySelector("textarea").classList.toggle("has-placeholder", hasPlaceholder(item.answerText));
    const foot = card.querySelector(".tp-q-foot");
    if (st === "needs_review" && !foot.querySelector("[data-tp-reviewed]")) {
      foot.insertAdjacentHTML("beforeend", `<label><input type="checkbox" data-tp-reviewed="${index}" ${item.include ? "" : "disabled"}> I have checked this answer</label>`);
    }
    const bar = document.querySelector(".tp-bar"); if (bar) bar.outerHTML = renderBar();
    const stats = document.querySelector(".tp-stats");
    if (stats) {
      const counts = { ready: 0, needs_review: 0, blocked: 0, unmatched: 0 };
      state.items.forEach((i) => { counts[effective(i)]++; });
      stats.querySelectorAll(".tp-stat").forEach((b) => { b.querySelector(".n").textContent = counts[b.dataset.tpFilter]; });
    }
  }

  // ---------------------------------------------------------------- events
  function bind() {
    const r = root(); if (!r || r.dataset.bound) return;
    r.dataset.bound = "1";
    r.addEventListener("click", (ev) => {
      const t = ev.target.closest("button, tr[data-tp-pack]"); if (!t) return;
      if (t.dataset.tpView) {
        state.view = t.dataset.tpView; state.error = ""; render();
        if (state.view === "library") loadLibrary(); if (state.view === "packs") loadPacks();
        return;
      }
      if (t.dataset.tpFilter) { state.filter = t.dataset.tpFilter === state.filter ? "all" : t.dataset.tpFilter; render(); return; }
      if (t.dataset.tpEdit) { openAnswerEditor(state.library.find((a) => a.answerId === t.dataset.tpEdit)); return; }
      if (t.dataset.tpApprove) { approve(t.dataset.tpApprove); return; }
      if (t.dataset.tpPack) { openPack(t.dataset.tpPack); return; }
      const act = t.dataset.tpAction;
      if (act === "example") { state.bid.questions = EXAMPLE_QUESTIONS; render(); }
      else if (act === "match") findAnswers();
      else if (act === "back") { state.step = 1; state.error = ""; render(); }
      else if (act === "issue") issuePack();
      else if (act === "word") downloadWord(state.pack.snapshot);
      else if (act === "print") printPack(state.pack.snapshot);
      else if (act === "copy") copyAnswers(state.pack.snapshot);
      else if (act === "restart") { state.step = 1; state.items = []; state.pack = null; state.bid = { clientName: "", bidReference: "", deadline: addDays(todayIso(), 14), questions: "" }; render(); }
      else if (act === "new-answer") openAnswerEditor(null);
    });
    r.addEventListener("keydown", (ev) => { const tr = ev.target.closest("tr[data-tp-pack]"); if (tr && ev.key === "Enter") openPack(tr.dataset.tpPack); });
    r.addEventListener("input", (ev) => {
      const el = ev.target;
      if (el.dataset.bid) {
        state.bid[el.dataset.bid] = el.value;
        if (el.dataset.bid === "deadline") { const pos = document.activeElement; render(); const d = $("#tpDeadline"); if (d && pos === el) d.focus(); }
        return;
      }
      if (el.dataset.lib) { state[el.dataset.lib] = el.value; const id = el.dataset.lib; render(); const back = document.querySelector(`[data-lib="${id}"]`); if (back && back.type === "search") { back.focus(); back.setSelectionRange(back.value.length, back.value.length); } return; }
      if (el.dataset.tpText) {
        const item = state.items.find((i) => i.index === Number(el.dataset.tpText));
        item.answerText = el.value;
        if (item.status === "unmatched" && el.value.trim() && !item.include) { item.include = true; const box = document.querySelector(`[data-tp-include="${item.index}"]`); if (box) box.checked = true; }
        item.reviewed = false; const rv = document.querySelector(`[data-tp-reviewed="${item.index}"]`); if (rv) rv.checked = false;
        refreshCard(item.index);
      }
    });
    r.addEventListener("change", (ev) => {
      const el = ev.target;
      if (el.dataset.tpInclude) { const item = state.items.find((i) => i.index === Number(el.dataset.tpInclude)); item.include = el.checked; render(); }
      else if (el.dataset.tpReviewed) { const item = state.items.find((i) => i.index === Number(el.dataset.tpReviewed)); item.reviewed = el.checked; refreshCard(item.index); }
      else if (el.dataset.tpAlt) swapAnswer(Number(el.dataset.tpAlt), el.value);
      else if (el.dataset.lib && el.tagName === "SELECT") { state[el.dataset.lib] = el.value; render(); }
    });
  }

  window.TenderPack = {
    open: async function () {
      if (!state.bid.deadline) state.bid.deadline = addDays(todayIso(), 14);
      bind(); render();
      if (!state.loadedEvidence) { await loadEvidence(); render(); }
    },
    _renderPackDocument: renderPackDocument,
  };
})();
