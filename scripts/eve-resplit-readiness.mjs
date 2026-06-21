#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";

const root = process.cwd();
const devRoot = process.env.EVE_DEV_ROOT ?? path.join(os.homedir(), "Development");

const requiredPacketFiles = [
  "agent/instructions.md",
  "agent/skills/vidux/references/resplit-fleet.md",
  "agent/skills/captain/SKILL.md",
  "agent/skills/nia/SKILL.md",
  "agent/subagents/resplit-onboarding/instructions.md",
  "scripts/eve-capability-check.mjs",
];

const repoTargets = [
  "resplit-ios",
  "resplit-web",
  "resplit-currency-api",
  "resplit-website",
  "ai-leo",
  "vidux",
];

function exists(relPath) {
  return fs.existsSync(path.join(root, relPath));
}

function read(relPath) {
  return fs.readFileSync(path.join(root, relPath), "utf8");
}

function gitBranch(repoPath) {
  try {
    return execFileSync("git", ["-C", repoPath, "branch", "--show-current"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function gitDirtyCount(repoPath) {
  try {
    return execFileSync("git", ["-C", repoPath, "status", "--short"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    })
      .split("\n")
      .filter(Boolean).length;
  } catch {
    return null;
  }
}

const errors = [];
const warnings = [];

for (const file of requiredPacketFiles) {
  if (!exists(file)) errors.push(`Missing Resplit Eve packet file: ${file}`);
}

const packetPath = "agent/skills/vidux/references/resplit-fleet.md";
const packet = exists(packetPath)
  ? read(packetPath)
  : "";

for (const phrase of [
  "P0 selection order",
  "ios-core-proof",
  "web-flow-proof",
  "currency-api-trust-proof",
  "skill-port-captain",
  "Nia read-first",
]) {
  if (!packet.includes(phrase)) errors.push(`Resplit Eve packet missing: ${phrase}`);
}

const repos = repoTargets.map((name) => {
  const repoPath = path.join(devRoot, name);
  const existsOnDisk = fs.existsSync(repoPath);
  const hasGit = existsOnDisk && fs.existsSync(path.join(repoPath, ".git"));
  if (!existsOnDisk) warnings.push(`Repo root not found locally: ${name}`);
  return {
    name,
    exists: existsOnDisk,
    git: hasGit,
    branch: hasGit ? gitBranch(repoPath) : "",
    dirtyFiles: hasGit ? gitDirtyCount(repoPath) : null,
  };
});

const report = {
  ok: errors.length === 0,
  verdict: errors.length === 0 ? "resplit_eve_onboarding_packet_ready" : "resplit_eve_onboarding_packet_incomplete",
  repo: root,
  devRoot,
  filesChecked: requiredPacketFiles.length,
  repoTargets: repos,
  gatesNotCrossed: [
    "no git commit",
    "no git push",
    "no branch mutation",
    "no hosted workflow dispatch",
    "no credential or config mutation",
    "no external board sync",
    "no package publish",
    "no remote-machine mutation",
  ],
  errors,
  warnings,
};

if (process.argv.includes("--json")) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log(`Resplit Eve readiness: ${report.ok ? "PASS" : "FAIL"}`);
  console.log(`Verdict: ${report.verdict}`);
  for (const repo of repos) {
    console.log(`${repo.name}: ${repo.exists ? "present" : "missing"}${repo.branch ? ` branch=${repo.branch}` : ""}`);
  }
  if (warnings.length) console.log(`Warnings:\n- ${warnings.join("\n- ")}`);
  if (errors.length) console.error(`Errors:\n- ${errors.join("\n- ")}`);
}

process.exitCode = report.ok ? 0 : 1;
