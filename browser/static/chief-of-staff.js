// Bounded desk rendering for the shared Pilot Puppy Chief-of-Staff brief.
// The caller supplies an already-validated semantic payload.  This module
// never fetches, routes, writes, or turns a brief into a second queue.
(function () {
  const BRIEF_SCHEMA = "vidux.chief-of-staff.v1";
  const MAX_TEXT = 280;
  const MAX_CHOICES = 3;
  const PRIVATE_TEXT_RE = /(?:\/Users\/|\/home\/|\/private\/var\/|[A-Za-z]:[\\/]|\\\\|~\/|\$HOME|file:\/\/|\b(?:provider|model|prompt|transcript|credential|secret|password|token)\b)/i;
  const STATES = new Set(["working", "needs_you", "blocked", "finished_with_proof", "not_delivered"]);

  function escapeText(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escapeAttr(value) {
    return escapeText(value).replace(/"/g, "&quot;");
  }

  function safeText(value) {
    if (typeof value !== "string") return null;
    const text = value.replace(/\s+/g, " ").trim();
    if (!text || text.length > MAX_TEXT || PRIVATE_TEXT_RE.test(text)) return null;
    return text;
  }

  function normalize(brief) {
    if (!brief || brief.schema !== BRIEF_SCHEMA || !Number.isInteger(brief.revision)) return null;
    if (typeof brief.outcome_id !== "string" || !/^[a-z][a-z0-9_-]{2,63}$/.test(brief.outcome_id)) return null;
    if (!STATES.has(brief.state)) return null;
    const changed = safeText(brief.changed);
    const matters = safeText(brief.matters);
    const recommendation = safeText(brief.recommendation);
    if (!changed || !matters || !recommendation) return null;
    const blocker = brief.blocker == null ? null : safeText(brief.blocker);
    const action = brief.action == null ? null : safeText(brief.action);
    if (brief.blocker != null && !blocker) return null;
    if (brief.action != null && !action) return null;
    const choices = Array.isArray(brief.choices)
      ? brief.choices.slice(0, MAX_CHOICES).map(choice => {
        if (!choice || typeof choice.id !== "string" || !/^[a-z][a-z0-9_-]{2,63}$/.test(choice.id)) return null;
        const label = safeText(choice.label);
        const consequence = safeText(choice.consequence);
        return label && consequence ? { id: choice.id, label, consequence } : null;
      }).filter(Boolean)
      : [];
    const proof = Array.isArray(brief.proof) && brief.proof[0]
      ? safeText(brief.proof[0].verification_summary)
      : null;
    return {
      revision: brief.revision,
      outcome_id: brief.outcome_id,
      state: brief.state,
      changed,
      matters,
      blocker,
      action,
      recommendation,
      choices,
      proof,
    };
  }

  function field(label, value) {
    if (!value) return "";
    return `<div class="chief-of-staff-field"><span>${escapeText(label)}</span><p>${escapeText(value)}</p></div>`;
  }

  function render(brief) {
    const safe = normalize(brief);
    if (!safe) return "";
    const choices = safe.choices.length
      ? `<div class="chief-of-staff-choices"><div class="chief-of-staff-label">Choices</div><ul>${safe.choices.map(choice => `
        <li><strong>${escapeText(choice.label)}</strong><span>${escapeText(choice.consequence)}</span></li>`).join("")}</ul></div>`
      : "";
    const proof = safe.proof
      ? `<details class="chief-of-staff-proof"><summary>Why Pilot Puppy says this</summary><p>${escapeText(safe.proof)}</p></details>`
      : "";
    return `<section class="chief-of-staff-brief" data-chief-schema="${BRIEF_SCHEMA}" data-outcome-id="${escapeAttr(safe.outcome_id)}" aria-label="Chief of Staff brief">
      <div class="chief-of-staff-head"><div><div class="chief-of-staff-kicker">Pilot Puppy · Chief of Staff</div><h3>Here’s what matters</h3></div><span class="chief-of-staff-state">${escapeText(safe.state.replace(/_/g, " "))}</span></div>
      <div class="chief-of-staff-fields">
        ${field("Changed", safe.changed)}
        ${field("Why it matters", safe.matters)}
        ${field("Needs you", safe.blocker)}
        ${field("Next action", safe.action)}
        ${field("Recommendation", safe.recommendation)}
      </div>
      ${choices}
      ${proof}
    </section>`;
  }

  window.ViduxChiefOfStaff = { BRIEF_SCHEMA, normalize, render };
})();
