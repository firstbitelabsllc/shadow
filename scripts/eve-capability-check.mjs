#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const root = process.cwd();
const requiredFiles = [
  "agent/agent.ts",
  "agent/instructions.md",
  "agent/skills/vidux/SKILL.md",
  "agent/skills/auto/SKILL.md",
  "agent/skills/captain/SKILL.md",
  "agent/skills/ledger/SKILL.md",
  "agent/skills/moussey/SKILL.md",
  "agent/skills/nia/SKILL.md",
  "agent/skills/vidux/references/resplit-fleet.md",
  "agent/subagents/plan-readiness/agent.ts",
  "agent/subagents/plan-readiness/instructions.md",
  "agent/subagents/resplit-onboarding/agent.ts",
  "agent/subagents/resplit-onboarding/instructions.md",
  "PLAN.md",
  "SKILL.md",
  "README.md",
  "package.json",
  "package-lock.json",
  "scripts/lib/ledger-config.sh",
  "scripts/lib/ledger-emit.sh",
  "scripts/lib/ledger-query.sh",
  "scripts/vidux-public-ready-grep-gate.py",
  "scripts/vidux-worktree-gc.py",
  "scripts/vidux-status.py",
];

const requiredScripts = [
  "eve:info",
  "eve:build",
  "eve:dev:local",
  "eve:capabilities",
  "eve:resplit:readiness",
];

const requiredDeps = {
  ai: "7.0.0-beta.178",
  eve: "0.11.5",
  zod: "4.4.3",
};

const requiredBinaries = [
  "node_modules/.bin/eve",
];

const expectedBranchFragments = [
  "codex/eve-studio-vidux-20260620",
];

const forbiddenFiles = [
  ".env",
  ".env.local",
  "vidux.config.json",
  ".external-board-state.json",
  ".hosted-project-state.json",
];

const forbiddenTokens = [
  "npm publish",
  "gh workflow run",
  "git push --force",
  "git push -f",
  "AI_GATEWAY_API_KEY=",
  "ANTHROPIC_API_KEY=",
  "GLM_API_KEY=",
  "GITHUB_TOKEN=",
];

const requiredPhrases = {
  "agent/skills/vidux/references/resplit-fleet.md": [
    "Resplit Eve Onboarding Fleet",
    "P0 selection order",
    "ios-core-proof",
    "web-flow-proof",
    "currency-api-trust-proof",
    "skill-port-captain",
    "Nia read-first",
  ],
  "agent/skills/captain/SKILL.md": [
    "narrowest correct tier",
    "Specific staging only",
    "shared/private boundary",
  ],
  "agent/skills/nia/SKILL.md": [
    "read-first",
    "manage_resource",
    "indexed source",
  ],
  "agent/subagents/resplit-onboarding/instructions.md": [
    "Resplit Eve onboarding",
    "read-only",
    "P0 selection order",
  ],
};

function readJson(relPath) {
  return JSON.parse(fs.readFileSync(path.join(root, relPath), "utf8"));
}

function exists(relPath) {
  return fs.existsSync(path.join(root, relPath));
}

function readText(relPath) {
  return fs.readFileSync(path.join(root, relPath), "utf8");
}

function gitStatus() {
  try {
    return execFileSync("git", ["status", "--short", "--branch"], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "git_status_unavailable";
  }
}

const errors = [];
const warnings = [];

for (const file of requiredFiles) {
  if (!exists(file)) errors.push(`Missing required file: ${file}`);
}

for (const [file, phrases] of Object.entries(requiredPhrases)) {
  if (!exists(file)) continue;
  const text = readText(file);
  for (const phrase of phrases) {
    if (!text.includes(phrase)) errors.push(`${file} missing required phrase: ${phrase}`);
  }
}

for (const file of forbiddenFiles) {
  if (exists(file)) errors.push(`Forbidden local config/credential file exists: ${file}`);
}

const packageJson = readJson("package.json");
for (const script of requiredScripts) {
  if (!packageJson.scripts?.[script]) errors.push(`Missing package script: ${script}`);
}

for (const [name, version] of Object.entries(requiredDeps)) {
  const actual = packageJson.dependencies?.[name] ?? packageJson.devDependencies?.[name];
  if (actual !== version) errors.push(`Dependency ${name} must be ${version}, got ${actual ?? "missing"}`);

  const installedPackagePath = path.join("node_modules", name, "package.json");
  if (!exists(installedPackagePath)) {
    errors.push(`Installed dependency ${name} is missing from node_modules`);
    continue;
  }

  const installedPackage = readJson(installedPackagePath);
  if (installedPackage.version !== version) {
    errors.push(`Installed dependency ${name} must be ${version}, got ${installedPackage.version ?? "unknown"}`);
  }
}

for (const binary of requiredBinaries) {
  if (!exists(binary)) errors.push(`Missing required local binary: ${binary}`);
}

const searchable = requiredFiles.filter(
  (file) => exists(file) && file.startsWith("agent/") && file.endsWith(".md"),
);
for (const file of searchable) {
  const text = readText(file);
  for (const token of forbiddenTokens) {
    if (text.includes(token)) errors.push(`${file} contains forbidden token: ${token}`);
  }
}

const status = gitStatus();
if (!expectedBranchFragments.some((fragment) => status.includes(fragment))) {
  warnings.push(`Expected clean Eve worktree branch name was not detected: ${expectedBranchFragments.join(" or ")}`);
}

const report = {
  ok: errors.length === 0,
  verdict: errors.length === 0 ? "vidux_eve_installed_local_only" : "vidux_eve_install_incomplete",
  repo: root,
  gitStatus: status.split("\n"),
  dependencyVersions: Object.fromEntries(
    Object.keys(requiredDeps).map((name) => [
      name,
      packageJson.dependencies?.[name] ?? packageJson.devDependencies?.[name],
    ]),
  ),
  dependencyLocation: "package.json and node_modules",
  binaries: requiredBinaries,
  scripts: requiredScripts,
  filesChecked: requiredFiles.length,
  specialists: [
    "plan-readiness",
    "resplit-onboarding",
    "captain-skill-port",
    "nia-read-first",
    "moussey-awareness",
  ],
  gatesNotCrossed: [
    "no package publication",
    "no release/tag publication",
    "no hosted workflow dispatch",
    "no external board sync",
    "no token or credential mutation",
    "no local config mutation",
    "no hosted model/API call",
    "no remote-machine mutation",
  ],
  errors,
  warnings,
};

if (process.argv.includes("--json")) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log(`Vidux Eve capability check: ${report.ok ? "PASS" : "FAIL"}`);
  console.log(`Verdict: ${report.verdict}`);
  console.log(`Files checked: ${report.filesChecked}`);
  console.log(`Scripts: ${report.scripts.join(", ")}`);
  if (report.warnings.length) console.log(`Warnings:\n- ${report.warnings.join("\n- ")}`);
  if (report.errors.length) console.error(`Errors:\n- ${report.errors.join("\n- ")}`);
}

process.exitCode = report.ok ? 0 : 1;
