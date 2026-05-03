# M17 — Simplify voice picker verification

Leo's 2026-05-03 voice memo: *"we don't need so much customization with voice."*

The picker had 20 voice options across 9 languages. After M17 it has 5 English presets — the only ones Leo's actually used in M5/M9/M11/M12 testing. Multilingual options were never user-validated, so they were decision-fatigue noise rather than feature.

## Implementation

`browser/static/index.html`:
- Removed `<optgroup label="Other languages">` wrapper + 15 multilingual `<option>` entries (Arabic, German, Spanish, French, Hindi, Italian, Dutch, Portuguese — male+female pairs).
- Flattened the remaining 5 English options out of the `<optgroup label="English (default)">` since there's only one group now (no need for the visual grouping).

`browser/static/readaloud.js`:
- Added `else { localStorage.removeItem(VOICE_STORAGE_KEY) }` to the saved-voice load path. Without this, a user who previously saved one of the 15 dropped voices (e.g. `fr_male`) would have the picker silently fall back to default but the stale value would linger in localStorage indefinitely.

## End-to-end verification (browse CLI on isolated Chromium :7191)

Test setup:

```js
// Prime stale value matching one of the just-dropped options
localStorage.setItem('vidux.readaloud.voice', 'fr_male');
// Reload to trigger the cleanup path
location.reload();
```

After reload:

```json
{
  "optionCount": 5,
  "options": ["casual_male", "casual_female", "neutral_male", "neutral_female", "cheerful_female"],
  "optgroups": [],
  "currentValue": "casual_male",
  "staleStorage": null
}
```

All four assertions pass:
- `optionCount: 5` — picker is the simplified set.
- `options: [casual_male, casual_female, neutral_male, neutral_female, cheerful_female]` — exact 5 English presets, no multilingual leakage.
- `optgroups: []` — the `<optgroup>` wrapper was correctly stripped (was visually redundant with only one group).
- `currentValue: "casual_male"` — falls back to default when the saved value can't be applied.
- `staleStorage: null` — the new `localStorage.removeItem` path fired, cleaning up the now-invalid `fr_male` entry. Future loads start clean.

## Files touched

| File | Change |
|------|--------|
| `browser/static/index.html` | -22/+5 lines. Dropped multilingual `<optgroup>` + 15 options. Flattened the English `<optgroup>` to bare `<option>`s. |
| `browser/static/readaloud.js` | +5 lines. Added stale-value cleanup branch in the saved-voice load path. |

## Screenshot

- `2026-05-03-m17-voice-picker.png` — top bar showing the 5-option picker after reload + cleanup
