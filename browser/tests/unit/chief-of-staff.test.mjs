// @vitest-environment node
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const source = fs.readFileSync(
  fileURLToPath(new URL('../../static/chief-of-staff.js', import.meta.url)),
  'utf8',
);
const context = { window: {} };
vm.runInNewContext(source, context);
const chief = context.window.ViduxChiefOfStaff;

function brief(overrides = {}) {
  return {
    schema: 'vidux.chief-of-staff.v1',
    revision: 4,
    outcome_id: 'outcome-demo',
    state: 'needs_you',
    changed: 'The current move is ready for your choice.',
    matters: 'This keeps one outcome moving without exposing the machinery.',
    blocker: 'Which direction should Pilot Puppy take?',
    action: 'Choose one option.',
    recommendation: 'Choose one of the listed options.',
    choices: [
      { id: 'hold-review', label: 'Hold review', consequence: 'Keep the current checkpoint.' },
      { id: 'continue', label: 'Continue', consequence: 'Move to the next bounded step.' },
      { id: 'pause', label: 'Pause', consequence: 'Leave the work ready to resume.' },
      { id: 'hidden', label: 'Hidden fourth', consequence: 'Must not be shown.' },
    ],
    proof: [{ verification_summary: 'The brief came from the current validated outcome.' }],
    ...overrides,
  };
}

describe('Chief of Staff desk brief', () => {
  it('renders the same bounded fields and caps choices at three', () => {
    const html = chief.render(brief());

    expect(html).toContain('Pilot Puppy · Chief of Staff');
    expect(html).toContain('Here’s what matters');
    expect(html).toContain('The current move is ready for your choice.');
    expect((html.match(/class="chief-of-staff-choices/g) || []).length).toBe(1);
    expect((html.match(/<li>/g) || []).length).toBe(3);
    expect(html).not.toContain('Hidden fourth');
    expect(html).toContain('Why Pilot Puppy says this');
  });

  it('fails closed without a typed semantic payload', () => {
    expect(chief.render()).toBe('');
    expect(chief.render({ ...brief(), schema: 'vidux.outcome.v1' })).toBe('');
    expect(chief.render({ ...brief(), state: 'running' })).toBe('');
  });

  it('escapes content and refuses private or implementation detail', () => {
    const escaped = chief.render({ ...brief(), changed: '<script>alert(1)</script>' });
    expect(escaped).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(escaped).not.toContain('<script>');
    const privatePath = ['', 'Users', 'leo', 'private'].join('/');
    expect(chief.render({ ...brief(), matters: privatePath })).toBe('');
    expect(chief.render({ ...brief(), recommendation: 'Ask the provider to retry' })).toBe('');
  });

  it('does not render unallowlisted proof fields or a locator', () => {
    const privateLocator = ['', 'Users', 'leo', 'secret.log'].join('/');
    const html = chief.render({
      ...brief(),
      proof: [{ verification_summary: 'One bounded proof.', locator: privateLocator }],
      implementation: 'do not display',
    });

    expect(html).toContain('One bounded proof.');
    expect(html).not.toContain(privateLocator);
    expect(html).not.toContain('do not display');
  });

  it('projects the same bounded brief into concise on-the-go speech', () => {
    const speech = chief.toSpeech(brief());

    expect(speech).toContain('Pilot Puppy. The current move is ready for your choice.');
    expect(speech).toContain('Needs you: Which direction should Pilot Puppy take?');
    expect(speech).toContain('Choices: A: Hold review; B: Continue; C: Pause.');
    expect(speech).not.toContain('Hidden fourth');
    expect(speech).not.toContain('<');
  });

  it('fails closed for the same malformed or private payloads as the desk view', () => {
    const privatePath = ['', 'Users', 'leo', 'private'].join('/');

    expect(chief.toSpeech()).toBe('');
    expect(chief.toSpeech({ ...brief(), matters: privatePath })).toBe('');
    expect(chief.toSpeech({ ...brief(), schema: 'vidux.outcome.v1' })).toBe('');
  });

  it('keeps desk and on-the-go views on one typed brief source', () => {
    const payload = brief();
    const normalized = chief.normalize(payload);
    const html = chief.render(payload);
    const speech = chief.toSpeech(payload);

    expect(normalized).toMatchObject({
      revision: payload.revision,
      outcome_id: payload.outcome_id,
      changed: payload.changed,
      recommendation: payload.recommendation,
    });
    expect(html).toContain(normalized.changed);
    expect(html).toContain(normalized.recommendation);
    expect(speech).toContain(normalized.changed);
    expect(speech).toContain(normalized.recommendation);
  });
});
