# V18 Segment Inventory Evidence — 2026-05-03

Task: `V18` segment inventory contract for vidux-browse read-aloud.

Scope: no model download, no MLX synthesis, no `/v1/audio/speech` call. Browser proof only imports `/static/readaloud.js` and evaluates the DOM segmentation helper.

## Files changed

- `browser/static/readaloud.js`
- `tests/test_browser_server.py`
- `projects/voxtral-reader-addon/PLAN.md`
- `projects/voxtral-reader-addon/INBOX.md`

## Contract

`readaloudCollectSegments(body, sourceRange)` now returns stable segment records:

```js
{
  id,
  kind,
  text,
  hash,
  element,
  range,
}
```

Supported segment kinds in this pass:

- `heading`
- `paragraph`
- `list-item`
- `code-block`
- `quote`
- `table-cell`
- `artifact-block`
- `selection`
- `block`

The full-pane read path now keeps `source.segments` with the current playback metadata so V19 can synthesize/cache per segment instead of one whole document.

## Browser smoke: synthetic rendered blocks

Command:

```bash
browse open 'http://127.0.0.1:7192/?plan=vidux%2Fprojects%2Fvoxtral-reader-addon%2FPLAN.md'
browse wait load
browse eval '(async () => { const mod = await import("/static/readaloud.js?v=v18-smoke"); const body = document.createElement("div"); body.id = "md-body"; body.innerHTML = `<h1>Segment Title</h1><p>First paragraph for reading.</p><ul><li>One nested idea <p>nested paragraph ignored as duplicate child</p></li></ul><pre><code>const x = 1;</code></pre><button>Ignore button</button><section><span>Artifact block fallback.</span></section>`; document.body.appendChild(body); const segments = mod.readaloudCollectSegments(body).map((s) => ({ id: s.id, kind: s.kind, text: s.text, hash: s.hash, hasRange: Boolean(s.range) })); body.remove(); return segments; })()'
```

Result:

```json
[
  {
    "id": "ra-seg-0-heading-5b33b8cc",
    "kind": "heading",
    "text": "Segment Title",
    "hash": "5b33b8cc",
    "hasRange": false
  },
  {
    "id": "ra-seg-1-paragraph-5e2c765a",
    "kind": "paragraph",
    "text": "First paragraph for reading.",
    "hash": "5e2c765a",
    "hasRange": false
  },
  {
    "id": "ra-seg-2-list-item-f8a4b2fd",
    "kind": "list-item",
    "text": "One nested idea nested paragraph ignored as duplicate child",
    "hash": "f8a4b2fd",
    "hasRange": false
  },
  {
    "id": "ra-seg-3-code-block-4658d292",
    "kind": "code-block",
    "text": "const x = 1;",
    "hash": "4658d292",
    "hasRange": false
  },
  {
    "id": "ra-seg-4-artifact-block-aaa23b94",
    "kind": "artifact-block",
    "text": "Artifact block fallback.",
    "hash": "aaa23b94",
    "hasRange": false
  }
]
```

Button chrome was ignored.

## Browser smoke: selected text

Command:

```bash
browse eval '(async () => { const mod = await import("/static/readaloud.js?v=v18-smoke"); const body = document.createElement("div"); body.id = "md-body"; body.innerHTML = `<p>Alpha beta gamma delta.</p>`; document.body.appendChild(body); const textNode = body.querySelector("p").firstChild; const range = document.createRange(); range.setStart(textNode, 6); range.setEnd(textNode, 16); const segments = mod.readaloudCollectSegments(body, range).map((s) => ({ id: s.id, kind: s.kind, text: s.text, hash: s.hash, hasRange: Boolean(s.range) })); body.remove(); return segments; })()'
```

Result:

```json
[
  {
    "id": "ra-seg-0-selection-2bbef392",
    "kind": "selection",
    "text": "beta gamma",
    "hash": "2bbef392",
    "hasRange": true
  }
]
```

## Browser smoke: live PLAN.md pane

Command:

```bash
browse eval '(async () => { const mod = await import("/static/readaloud.js?v=v18-smoke"); const body = document.getElementById("md-body"); const segments = mod.readaloudCollectSegments(body); return { count: segments.length, first: segments.slice(0, 8).map((s) => ({ kind: s.kind, text: s.text.slice(0, 90), hash: s.hash })) }; })()'
```

Result:

```json
{
  "count": 100,
  "first": [
    {
      "kind": "heading",
      "text": "Voxtral Reader Add-on for vidux-browse",
      "hash": "b7be3527"
    },
    {
      "kind": "heading",
      "text": "Purpose",
      "hash": "4c7dff89"
    },
    {
      "kind": "paragraph",
      "text": "Ship a 🔊 \"Read aloud\" button in vidux-browse that reads the current artifact / PLAN.md al",
      "hash": "d866583e"
    },
    {
      "kind": "paragraph",
      "text": "The killer use case is hands-free consumption of agent output during walks / commutes / do",
      "hash": "5001d6f6"
    },
    {
      "kind": "paragraph",
      "text": "Two-agent coordination (2026-05-01). Codex is joining this plan. Both agents (Claude + Cod",
      "hash": "e2b6b821"
    },
    {
      "kind": "heading",
      "text": "Evidence",
      "hash": "9e1d970c"
    },
    {
      "kind": "list-item",
      "text": "[Source: shell verify 2026-05-01] mlx-audio installed via uv tool install --with mlx-audio",
      "hash": "0b481c39"
    },
    {
      "kind": "list-item",
      "text": "[Source: WebFetch 2026-05-01 — github.com/Blaizzy/mlx-audio README] mlx-audio supports mlx",
      "hash": "6a24970c"
    }
  ]
}
```

## Verification

```bash
node --check browser/static/readaloud.js
python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests
npm test
```

Results:

- `node --check browser/static/readaloud.js`: passed.
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`: passed, 3 tests.
- `npm test`: passed, 182 tests in 87.648s.

V19 can now replace whole-pane synthesis with a per-segment scheduler keyed by `{model, voice, segment.hash}`.
