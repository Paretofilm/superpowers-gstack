import { esc } from "../../helpers/render.ts";
import type { FeedbackPanel } from "../../schemas.ts";

// Renders the feedback panel: a form-like block at the end of a companion HTML
// that lets the user check off premises, pick an approach, answer custom
// questions, and write a free-text comment. A "Copy as prompt" button gathers
// state and copies a JSON blob to the clipboard so the user can paste it back
// into the next Claude Code session.
//
// No server, no backend. Pure HTML + a single inline script. Clipboard API has
// broad support; falls back to selecting a <pre> if `navigator.clipboard` is
// unavailable.
//
// Plan-supplied strings (premise labels, approach names) are HTML-escaped
// before interpolation. The script body is static and trusted.

export interface FeedbackPanelData extends FeedbackPanel {}

function checkboxRow(id: string, label: string, group: string): string {
  return `<label class="fb-row">
  <input type="checkbox" name="${esc(group)}" value="${esc(id)}" data-fb-group="${esc(group)}" data-fb-id="${esc(id)}">
  <span>${esc(label)}</span>
</label>`;
}

function radioRow(id: string, label: string, group: string): string {
  return `<label class="fb-row">
  <input type="radio" name="${esc(group)}" value="${esc(id)}" data-fb-group="${esc(group)}" data-fb-id="${esc(id)}">
  <span>${esc(label)}</span>
</label>`;
}

function customQuestion(q: {
  id: string;
  label: string;
  type: "checkbox" | "radio" | "text";
  options?: string[];
}): string {
  if (q.type === "text") {
    return `<div class="fb-question fb-question-text">
  <label class="fb-question-label" for="fb-q-${esc(q.id)}">${esc(q.label)}</label>
  <input type="text" id="fb-q-${esc(q.id)}" data-fb-question="${esc(q.id)}">
</div>`;
  }
  if (q.type === "radio") {
    const opts = (q.options ?? [])
      .map(
        (opt) =>
          `<label class="fb-row">
  <input type="radio" name="fb-q-${esc(q.id)}" value="${esc(opt)}" data-fb-question="${esc(q.id)}" data-fb-value="${esc(opt)}">
  <span>${esc(opt)}</span>
</label>`
      )
      .join("\n");
    return `<fieldset class="fb-question fb-question-radio">
  <legend class="fb-question-label">${esc(q.label)}</legend>
  ${opts}
</fieldset>`;
  }
  // checkbox
  const opts = (q.options ?? [q.label])
    .map(
      (opt) =>
        `<label class="fb-row">
  <input type="checkbox" name="fb-q-${esc(q.id)}" value="${esc(opt)}" data-fb-question="${esc(q.id)}" data-fb-value="${esc(opt)}">
  <span>${esc(opt)}</span>
</label>`
    )
    .join("\n");
  return `<fieldset class="fb-question fb-question-checkbox">
  <legend class="fb-question-label">${esc(q.label)}</legend>
  ${opts}
</fieldset>`;
}

// Static inline script — gathers form state into JSON and copies it. Strings
// inside the script are not user-controllable; safe to embed verbatim. The
// `data-fb-*` attribute scheme keeps the DOM agnostic of label content so
// escaped HTML in labels stays cosmetic and never leaks into the JSON.
const PANEL_SCRIPT = `
(function () {
  const panel = document.currentScript.closest('.feedback-panel');
  if (!panel) return;
  const button = panel.querySelector('.fb-copy');
  const status = panel.querySelector('.fb-status');
  const fallback = panel.querySelector('.fb-fallback');
  if (!button) return;

  function gather() {
    const out = { premises: [], approach: null, custom: {}, comment: '' };
    panel.querySelectorAll('input[data-fb-group="premises"]:checked').forEach((el) => {
      out.premises.push(el.dataset.fbId);
    });
    const a = panel.querySelector('input[data-fb-group="approach"]:checked');
    if (a) out.approach = a.dataset.fbId;
    panel.querySelectorAll('[data-fb-question]').forEach((el) => {
      const q = el.dataset.fbQuestion;
      if (el.type === 'text') {
        if (el.value.trim()) out.custom[q] = el.value.trim();
      } else if (el.type === 'checkbox' && el.checked) {
        out.custom[q] = out.custom[q] || [];
        out.custom[q].push(el.dataset.fbValue);
      } else if (el.type === 'radio' && el.checked) {
        out.custom[q] = el.dataset.fbValue;
      }
    });
    const c = panel.querySelector('.fb-comment');
    if (c) out.comment = c.value.trim();
    return out;
  }

  function showStatus(msg, ok) {
    if (!status) return;
    status.textContent = msg;
    status.classList.toggle('fb-ok', !!ok);
    status.classList.toggle('fb-err', !ok);
  }

  button.addEventListener('click', async function () {
    const payload = gather();
    const text = JSON.stringify(payload, null, 2);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        showStatus('Copied to clipboard. Paste into next session.', true);
        return;
      }
      throw new Error('no clipboard');
    } catch (e) {
      if (fallback) {
        fallback.textContent = text;
        fallback.hidden = false;
        const range = document.createRange();
        range.selectNodeContents(fallback);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
      showStatus('Clipboard unavailable — text is selected, press Cmd/Ctrl-C.', false);
    }
  });
})();
`;

export function renderFeedbackPanel(data: FeedbackPanelData): string {
  if (data.enabled === false) return "";

  const premises = (data.premises ?? [])
    .map((id, i) => checkboxRow(id, id, "premises"))
    .join("\n");
  const approaches = (data.approaches ?? [])
    .map((id) => radioRow(id, id, "approach"))
    .join("\n");
  const customs = (data.custom_questions ?? [])
    .map((q) => customQuestion(q))
    .join("\n");

  const premisesBlock = premises
    ? `<fieldset class="fb-section">
  <legend>Premises that need more thought</legend>
  ${premises}
</fieldset>`
    : "";
  const approachesBlock = approaches
    ? `<fieldset class="fb-section">
  <legend>I'd actually pick this approach</legend>
  ${approaches}
</fieldset>`
    : "";
  const customsBlock = customs
    ? `<div class="fb-section fb-customs">${customs}</div>`
    : "";

  return `<aside class="feedback-panel">
  <h2>Send feedback for next round</h2>
  <p class="fb-intro">Tick what needs revising, pick an approach if you want to commit, and add a comment. Copy the JSON and paste it into the next Claude Code session.</p>
  ${premisesBlock}
  ${approachesBlock}
  ${customsBlock}
  <div class="fb-section fb-comment-section">
    <label class="fb-question-label" for="fb-comment">Comment (always included)</label>
    <textarea id="fb-comment" class="fb-comment" rows="5" placeholder="Anything I should know before the next round..."></textarea>
  </div>
  <div class="fb-actions">
    <button type="button" class="fb-copy">Copy feedback as prompt</button>
    <span class="fb-status" aria-live="polite"></span>
  </div>
  <pre class="fb-fallback" hidden></pre>
  <script>${PANEL_SCRIPT}</script>
</aside>`;
}
