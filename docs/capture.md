# Reproduce the demo

Run `python3 examples/demo.py` from this clone. It reuses Shadow's existing
isolated-board harness, runs the actual `init`, `status`, `throw`, and `accept`
commands against a temporary repository, and verifies three results:

- the failing greeting test prevents completion;
- committing the fix allows acceptance;
- a fresh status command finds the next task with no abandoned claim.

No coding agent runs, and no model account is needed. This demonstrates the
local command workflow, not a live conversation between two AI tools.

To rebuild the screenshots, video, and cover, install ttyd, FFmpeg, Node.js 20+,
and the Playwright capture dependency:

```sh
capture_tools="$(mktemp -d)"
npm install --prefix "$capture_tools" playwright@1.62.0
"$capture_tools/node_modules/.bin/playwright" install chromium
PLAYWRIGHT_MODULE="$capture_tools/node_modules/playwright/index.mjs" node docs/capture.mjs
```

The recorder uses local port 8832 and saves the result under `docs/public`.
It waits for the terminal's actual completion output before taking the still.
Its browser and terminal server close afterward. Rebuild the site with
`cd docs && npm ci && npm run docs:build:pages`.

The ribbon mark is a generated illustration made with OpenAI's built-in image
tool: a compact S-shaped folded bookmark, forest ink and sage, broad shapes,
transparent background. The terminal capture comes from the working example.
Space Grotesk is included under the SIL Open Font License in `public/OFL.txt`.
