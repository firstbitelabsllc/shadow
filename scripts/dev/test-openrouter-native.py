#!/usr/bin/env python3
"""Opt-in, network-denied native OpenCode characterization, not live admission.

Requires an already installed @opencode-ai/plugin SDK matching OpenCode 1.18.25.
Downloads nothing, inherits no credentials, and changes no installed config.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pwd
import os
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.18.25"
POLICY = {"zdr": True, "data_collection": "deny", "require_parameters": True,
          "allow_fallbacks": False, "max_price": dict.fromkeys(("prompt", "completion", "request", "image"), 0)}


def run_native(command, *, env, cwd, timeout):
    """Own the full native process group, including startup descendants."""
    process = subprocess.Popen(command, env=env, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--sdk-node-modules", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    sdk = args.sdk_node_modules.resolve(strict=True)
    package = json.loads((sdk / "@opencode-ai/plugin/package.json").read_text())
    if package["version"] != VERSION:
        raise SystemExit("refused: SDK version differs from characterized binary")
    minimal_env = {"PATH": "/opt/homebrew/bin:/usr/bin:/bin", "SHELL": "/bin/sh"}
    # Probe all native execution under the same network/home-denied profile.
    with tempfile.TemporaryDirectory(prefix="openrouter-native-", dir="/private/tmp") as dirname:
        temp = Path(dirname)
        home_path = pwd.getpwuid(os.getuid()).pw_dir
        sandbox = temp / "offline.sb"
        sandbox.write_text('(version 1)\n(allow default)\n(deny network*)\n'
                           '(deny file-read* file-write* (subpath ' + json.dumps(home_path) + '))\n'
                           '(deny file-read* file-write* (subpath "/Library/Keychains"))\n')
        launch = ["/usr/bin/sandbox-exec", "-f", str(sandbox), str(binary)]
        isolated_env = {**minimal_env, **{f"XDG_{key}_HOME": str(temp / key.lower()) for key in ("CONFIG", "DATA", "CACHE", "STATE")},
                        "OPENCODE_DISABLE_MODELS_FETCH": "1", "OPENCODE_DISABLE_AUTOUPDATE": "1"}
        version = run_native(launch + ["--version"], env=isolated_env, cwd=temp, timeout=10)
        if version.returncode or version.stdout.strip() != VERSION:
            raise SystemExit("refused: native binary version probe failed: " + repr((version.returncode, version.stdout, version.stderr)))
        shutil.copytree(sdk, temp / "config/opencode/node_modules", symlinks=False)
        # Native dependency readiness compares declared names with the npm lock.
        # Preserve the prepared SDK's real package/lock pair, not a fabricated one.
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(sdk.parent / name, temp / "config/opencode" / name)
        shutil.copyfile(ROOT / "scripts/dev/openrouter-transport-guard.mjs", temp / "transport-guard.mjs")
        shutil.copyfile(ROOT / "tests/fixtures/openrouter-offline-plugin.mjs", temp / "witness.mjs")
        env = {**minimal_env, **{f"XDG_{key}_HOME": str(temp / key.lower()) for key in ("CONFIG", "DATA", "CACHE", "STATE")},
               "OPENCODE_CONFIG": str(temp / "config.json"), "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
               "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1", "OPENCODE_DISABLE_MODELS_FETCH": "1", "OPENCODE_DISABLE_AUTOUPDATE": "1"}
        config = {"$schema": "https://opencode.ai/config.json", "model": "openrouter/openrouter/free",
                  "small_model": "openrouter/openrouter/free", "enabled_providers": ["openrouter"],
                  "share": "disabled", "autoupdate": False, "permission": {"*": "deny"},
                  "plugin": [(temp / "witness.mjs").as_uri()], "provider": {"openrouter": {
                      "options": {"apiKey": "offline-fixture-not-a-credential", "baseURL": "https://openrouter.ai/api/v1"},
                      "models": {"openrouter/free": {"name": "Offline free router", "options": {"provider": POLICY}}}}}}
        results = []
        for label, policy in (("policy-present", POLICY), ("policy-missing", {})):
            config["provider"]["openrouter"]["models"]["openrouter/free"]["options"] = {"provider": policy}
            (temp / "config.json").write_text(json.dumps(config))
            try:
                result = run_native(launch + ["run", "--print-logs", "--format", "json", "--title", "Offline guard proof",
                                        "--model", "openrouter/openrouter/free", "Reply with READY only."],
                                        env=env, cwd=temp, timeout=30)
            except subprocess.TimeoutExpired as error:
                raise SystemExit("native fixture timeout: " + str(error.stderr or b"")[-6000:])
            transcript = result.stdout + result.stderr
            requests = [json.loads(line.removeprefix("OFFLINE_REQUEST ")) for line in result.stderr.splitlines() if line.startswith("OFFLINE_REQUEST ")]
            receipts = [json.loads(line.removeprefix("OFFLINE_RECEIPT ")) for line in result.stderr.splitlines() if line.startswith("OFFLINE_RECEIPT ")]
            if policy:
                assert result.returncode == 0, transcript[-2000:]
                assert len(requests) == len(receipts) == 1, transcript[-2000:]
                assert requests[0] == {"url": "https://openrouter.ai/api/v1/chat/completions", "model": "openrouter/free", "provider": POLICY}
                assert receipts[0]["model"] == "fixture/concrete-free-model" and receipts[0]["cost"] == 0
                assert '"text":"READY"' in result.stdout, result.stdout[-2000:]
            else:
                assert not requests and not receipts, "missing policy reached transport"
                assert "openrouter_guard_refused" in transcript, transcript[-2000:]
                assert '"text":"READY"' not in result.stdout
            results.append({"case": label, "transport_calls": len(requests), "receipts": len(receipts), "passed": True})
        with binary.open("rb") as source:
            binary_digest = hashlib.file_digest(source, "sha256").hexdigest()
        print(json.dumps({"scope": "offline-native-only", "version": VERSION,
                          "binary_sha256": binary_digest,
                          "guard_sha256": hashlib.sha256((temp / "transport-guard.mjs").read_bytes()).hexdigest(),
                          "results": results}, sort_keys=True))


if __name__ == "__main__":
    main()
