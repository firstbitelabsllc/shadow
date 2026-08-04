import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

const html = readFileSync('browser/static/index.html', 'utf8');
const app = readFileSync('browser/static/app.js', 'utf8');
const css = readFileSync('browser/static/style.css', 'utf8');

describe('Pilot Puppy browser shell', () => {
  it('has one product identity and one application script', () => {
    expect(html).toContain('<title>Pilot Puppy</title>');
    expect(html).toContain('Your coding chief of staff');
    expect(html.match(/<script /g)).toHaveLength(1);
  });

  it('reads plans and sends only the typed A/B/C decision envelope', () => {
    expect(app).toContain("fetch('/api/plans')");
    expect(app).toContain("fetch('/api/decision'");
    expect(app).toContain("{ plan: plan.path, option_id: option.id, revision: plan.outcome.revision }");
    expect(app).not.toContain('localStorage');
    expect(app).not.toContain('WebSocket');
  });

  it('names the chief-of-staff brief sections plainly', () => {
    expect(app).toContain("text: 'Now'");
    expect(app).toContain("row('Change', briefing.changed)");
    expect(app).toContain("text: 'A/B/C decision'");
    expect(app).toContain("briefing.proof ? 'Proof' : 'Proof not available yet'");
  });

  it('keeps responsive and reduced-motion behavior', () => {
    expect(css).toContain('@media (max-width: 760px)');
    expect(css).toContain('@media (prefers-reduced-motion: no-preference)');
    expect(css).toContain('@media (prefers-color-scheme: dark)');
  });
});
