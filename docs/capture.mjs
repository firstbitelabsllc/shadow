import { pathToFileURL, fileURLToPath } from "node:url";
import { spawn, execFileSync } from "node:child_process";
import { mkdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE
    ? pathToFileURL(path.resolve(process.env.PLAYWRIGHT_MODULE)).href
    : "playwright"
);
const root = fileURLToPath(new URL("../", import.meta.url));
execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
const output = path.join(root, "docs/public");
await mkdir(output, { recursive: true });
const server = spawn(
  "ttyd",
  [
    "-p",
    "8832",
    "-i",
    "127.0.0.1",
    "-O",
    "-o",
    "-W",
    "-w",
    root,
    "-t",
    "fontSize=20",
    "-t",
    "screenReaderMode=true",
    "-t",
    "fontFamily=Menlo",
    "-t",
    'theme={"background":"#f4f2eb","foreground":"#212920","cursor":"#b6532a"}',
    "claude",
    "--safe-mode",
    "--setting-sources", "",
    "--strict-mcp-config",
    "--mcp-config", '{"mcpServers":{}}',
    "--model", "sonnet",
    "--effort", "low",
    "--tools", "Bash,Read",
    "--allowedTools", "Bash(python3 examples/demo.py)",
  ],
  {
    env: {
      ...process.env,
      BASH_SILENCE_DEPRECATION_WARNING: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  },
);
let logs = "";
server.stderr.on("data", (chunk) => (logs += chunk));
let browser;
try {
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(
      () => reject(Error(logs || "ttyd startup timeout")),
      10000,
    );
    server.stderr.on("data", () => {
      if (logs.includes("Listening on port")) {
        clearTimeout(timeout);
        resolve();
      }
    });
    server.once("exit", (code) => {
      clearTimeout(timeout);
      reject(Error("ttyd exited " + code + " " + logs));
    });
  });
  browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 820 },
    recordVideo: { dir: output, size: { width: 1440, height: 820 } },
  });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:8832");
  await page.locator(".xterm-helper-textarea").waitFor({ state: "attached" });
  await page.addStyleTag({
    content:
      "body{background:#e6e4dd!important;padding:40px;box-sizing:border-box}#terminal-container{height:calc(100vh - 80px)!important;border-radius:12px;overflow:hidden;padding:28px;background:#f4f2eb;box-sizing:border-box}.xterm{height:100%}",
  });
  // ttyd fits xterm before the injected frame padding lands. Resize twice after
  // the frame is present so the terminal recalculates its full visible grid.
  await page.setViewportSize({ width: 1439, height: 820 });
  await page.setViewportSize({ width: 1440, height: 820 });
  await page.waitForTimeout(800);
  await page.waitForFunction(
    () => document.body.textContent.includes("Claude Code"),
    null,
    { timeout: 15000 },
  );
  await page.locator(".xterm-helper-textarea").focus();
  await page.keyboard.type(
    "Show me how Shadow handles a failing check and finds the next task. Run the local example and explain the result in three short bullets.",
    { delay: 25 },
  );
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () => /done \d+:\d+ [AP]M/.test(document.body.textContent),
    null,
    { timeout: 120000 },
  );
  await page.screenshot({ path: path.join(output, "shadow-demo.png") });
  await page.waitForTimeout(2200);
  await page.waitForTimeout(4000);
  const video = page.video();
  await context.close();
  await video.saveAs(path.join(output, "shadow-demo.webm"));
  await video.delete();
  for (const name of ["shadow-demo.png", "shadow-demo.webm"])
    if ((await stat(path.join(output, name))).size < 1000)
      throw Error("Capture missing: " + name);
  await writeFile(
    path.join(output, "capture-result.json"),
    JSON.stringify(
      {
        commands: ["Claude Code runs python3 examples/demo.py"],
        browser: browser.version(),
        recordedAt: new Date().toISOString(),
      },
      null,
      2,
    ) + "\n",
  );
  execFileSync(
    "ffmpeg",
    [
      "-y",
      "-i",
      path.join(output, "shadow-demo.webm"),
      "-an",
      "-c:v",
      "libx264",
      "-pix_fmt",
      "yuv420p",
      "-movflags",
      "+faststart",
      path.join(output, "shadow-demo.mp4"),
    ],
    { stdio: "ignore" },
  );
  console.log("Verified native Claude Code screenshot and recording exist.");
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
}
