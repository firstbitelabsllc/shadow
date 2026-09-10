# Reproduce the demo

Run `python3 examples/demo.py` from this clone. It reuses Shadow's existing
isolated-board harness, runs the actual `init`, `status`, `throw`, and `accept`
commands against a temporary repository, and verifies three results:

- the failing greeting test prevents completion;
- committing the fix allows acceptance;
- a fresh status command finds the next task with no abandoned claim.

The published terminal recording shows Claude Code asking to run this local
example. The script performs the demonstrated lifecycle; the recording does
not simulate terminal output or claim that the agent made the fix itself.

To rebuild the screenshots and video, install ttyd, FFmpeg, Node.js 20+,
and the Playwright capture dependency:

```sh
capture_tools="$(mktemp -d)"
npm install --prefix "$capture_tools" playwright@1.62.0
"$capture_tools/node_modules/.bin/playwright" install chromium
PLAYWRIGHT_MODULE="$capture_tools/node_modules/playwright/index.mjs" node docs/capture.mjs
```

The recorder uses local port 8832 and saves the result under `docs/public`.
It starts the locally authenticated Claude Code CLI with a constrained local
prompt, waits for its actual completion output before taking the still, and
closes its browser and terminal server afterward. Rebuild the site with
`cd docs && npm ci && npm run docs:build:pages`.

The ribbon mark is a generated illustration made with OpenAI's built-in image
tool: a compact S-shaped folded bookmark, forest ink and sage, broad shapes,
transparent background. The terminal capture comes from the working example.
Space Grotesk is included under the SIL Open Font License in `public/OFL.txt`.
