#!/usr/bin/env python3
"""Opt-in, network-denied native OpenCode characterization, not live admission.

Requires an already installed @opencode-ai/plugin SDK matching OpenCode 1.18.25.
Downloads nothing, inherits no credentials, and changes no installed config.
"""
import argparse
import hashlib
import importlib.util
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
    if env.get("OPENCODE_EXPERIMENTAL_NATIVE_LLM", "false").lower() not in ("false", "0"):
        raise ValueError("alternate runtime refused before native launch")
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
    parser.add_argument("--required-provider", action="store_true",
                        help="test mandatory provider initialization instead of the earlier plugin seam")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    sdk = args.sdk_node_modules.resolve(strict=True)
    package = json.loads((sdk / "@opencode-ai/plugin/package.json").read_text())
    if package["version"] != VERSION:
        raise SystemExit("refused: SDK version differs from characterized binary")
    if args.required_provider:
        provider_package = json.loads((sdk / "@openrouter/ai-sdk-provider/package.json").read_text())
        if provider_package["version"] != "2.9.0":
            raise SystemExit("refused: provider SDK differs from the version used by native OpenCode")
    minimal_env = {"PATH": "/opt/homebrew/bin:/usr/bin:/bin", "SHELL": "/bin/sh"}
    # Probe all native execution under the same network/home-denied profile.
    with tempfile.TemporaryDirectory(prefix="openrouter-native-", dir="/private/tmp") as dirname:
        temp = Path(dirname)
        home_path = pwd.getpwuid(os.getuid()).pw_dir
        sandbox = temp / "offline.sb"
        sandbox.write_text('(version 1)\n(allow default)\n(deny network*)\n'
                           '(deny file-read* file-write* (subpath ' + json.dumps(home_path) + '))\n'
                           '(deny file-read* file-write* (subpath "/Library/Keychains"))\n'
                           '(deny file-write* (subpath ' + json.dumps(str(sdk)) + '))\n'
                           '(allow file-read-metadata ' + ' '.join('(literal ' + json.dumps(str(parent)) + ')' for parent in sdk.parents) + ')\n'
                           '(allow file-read* (subpath ' + json.dumps(str(sdk)) + '))\n')
        launch = ["/usr/bin/sandbox-exec", "-f", str(sandbox), str(binary)]
        isolated_env = {**minimal_env, **{f"XDG_{key}_HOME": str(temp / key.lower()) for key in ("CONFIG", "DATA", "CACHE", "STATE")},
                        "OPENCODE_DISABLE_MODELS_FETCH": "1", "OPENCODE_DISABLE_AUTOUPDATE": "1"}
        version = run_native(launch + ["--version"], env=isolated_env, cwd=temp, timeout=10)
        if version.returncode or version.stdout.strip() != VERSION:
            raise SystemExit("refused: native binary version probe failed: " + repr((version.returncode, version.stdout, version.stderr)))
        # Public dependencies stay read-only at the caller's declared SDK path.
        # Copying thousands of SDK docs hit a native filesystem stall; no runtime
        # dependency needs a mutable duplicate. Refuse escaping package links.
        for item in sdk.rglob("*"):
            if item.is_symlink():
                item.resolve(strict=True).relative_to(sdk)
        (temp / "config/opencode").mkdir(parents=True, exist_ok=True)
        (temp / "config/opencode/node_modules").symlink_to(sdk, target_is_directory=True)
        # Native dependency readiness compares declared names with the npm lock.
        # Preserve the prepared SDK's real package/lock pair, not a fabricated one.
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(sdk.parent / name, temp / "config/opencode" / name)
        shutil.copyfile(ROOT / "scripts/dev/openrouter-transport-guard.mjs", temp / "transport-guard.mjs")
        shutil.copyfile(ROOT / "tests/fixtures/openrouter-offline-plugin.mjs", temp / "witness.mjs")
        if args.required_provider:
            shutil.copyfile(ROOT / "tests/fixtures/openrouter-offline-provider.mjs", temp / "provider.mjs")
        env = {**minimal_env, **{f"XDG_{key}_HOME": str(temp / key.lower()) for key in ("CONFIG", "DATA", "CACHE", "STATE")},
               "OPENCODE_CONFIG": str(temp / "config.json"), "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
               "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1", "OPENCODE_DISABLE_MODELS_FETCH": "1", "OPENCODE_DISABLE_AUTOUPDATE": "1"}
        config = {"$schema": "https://opencode.ai/config.json", "model": "openrouter/openrouter/free",
                  "small_model": "openrouter/openrouter/free", "enabled_providers": ["openrouter"],
                  "share": "disabled", "autoupdate": False, "permission": {"*": "deny"},
                  "plugin": [(temp / "witness.mjs").as_uri()], "provider": {"openrouter": {
                      "options": {"apiKey": "offline-fixture-not-a-credential", "baseURL": "https://openrouter.ai/api/v1"},
                      "models": {"openrouter/free": {"name": "Offline free router", "options": {"provider": POLICY}}}}}}
        cases = [("policy-present", POLICY), ("policy-missing", {})]
        if args.required_provider:
            env.update({"OPENCODE_PURE": "true", "OPENCODE_EXPERIMENTAL_NATIVE_LLM": "false",
                        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "true", "OPENCODE_DISABLE_CLAUDE_CODE": "true",
                        "OPENCODE_DISABLE_LSP_DOWNLOAD": "true"})
            config["plugin"] = []
            config["provider"]["openrouter"]["npm"] = (temp / "provider.mjs").as_uri()
            cases.extend((label, POLICY) for label in ("provider-missing", "provider-malformed", "provider-init-failure", "guard-missing"))
            cases.append(("candidate", POLICY))
            cases.append(("ambient-plugin", POLICY))
        results = []
        for label, policy in cases:
            if args.required_provider:
                config["plugin"] = []
                shutil.copyfile(ROOT / "tests/fixtures/openrouter-offline-provider.mjs", temp / "provider.mjs")
                shutil.copyfile(ROOT / "scripts/dev/openrouter-transport-guard.mjs", temp / "transport-guard.mjs")
                if label == "provider-missing":
                    (temp / "provider.mjs").unlink()
                elif label == "provider-malformed":
                    (temp / "provider.mjs").write_text("export function createBroken( { invalid syntax")
                elif label == "provider-init-failure":
                    (temp / "provider.mjs").write_text("export function createBroken() { throw new Error('fixture initialization failure'); }")
                elif label == "guard-missing":
                    (temp / "transport-guard.mjs").unlink()
                elif label == "ambient-plugin":
                    poison = temp / "ambient.mjs"
                    poison.write_text("import {writeFileSync} from 'node:fs'; writeFileSync(new URL('./ambient-effect', import.meta.url), 'ran'); export const Poison = async () => { throw new Error('ambient plugin ran'); };")
                    config["plugin"] = [poison.as_uri()]
            config["provider"]["openrouter"]["models"]["openrouter/free"]["options"] = {"provider": policy}
            expected_text = json.dumps({"answer.py": "VALUE = 42\n"}) if label == "candidate" else "READY"
            if args.required_provider:
                config["provider"]["openrouter"]["options"]["fixtureText"] = expected_text
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
            lookups = sum(line == "OFFLINE_CREDENTIAL_LOOKUP" for line in result.stderr.splitlines())
            if label in ("policy-present", "candidate", "ambient-plugin"):
                assert result.returncode == 0, transcript[-2000:]
                assert len(requests) == len(receipts) == 1, transcript[-2000:]
                assert requests[0] == {"url": "https://openrouter.ai/api/v1/chat/completions", "model": "openrouter/free", "provider": POLICY}
                assert receipts[0]["model"] == "fixture/concrete-free-model" and receipts[0]["cost"] == 0
                text_events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
                returned_text = "".join(event.get("part", {}).get("text", "") for event in text_events if event.get("type") == "text")
                assert returned_text == expected_text, result.stdout[-2000:]
                if args.required_provider:
                    assert lookups == 1
                assert not (temp / "ambient-effect").exists(), "ambient plugin executed"
            else:
                assert not requests and not receipts and not lookups, "invalid boundary reached credential lookup or transport"
                if label == "policy-missing":
                    assert "openrouter_guard_refused" in transcript, transcript[-2000:]
                else:
                    assert "Failed to initialize provider: openrouter" in transcript, transcript[-2000:]
                assert '"text":"READY"' not in result.stdout
            results.append({"case": label, "transport_calls": len(requests), "receipts": len(receipts),
                            "fixture_credential_lookups": lookups, "passed": True})
            if label == "candidate":
                spec = importlib.util.spec_from_file_location("candidate", ROOT / "scripts/dev/openrouter-candidate.py")
                candidate = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(candidate)
                checked = candidate.evaluate({"answer.py": "VALUE = 0\n", "check.py": "from answer import VALUE\nassert VALUE == 42\n"},
                                             {"answer.py"}, "check.py", returned_text)
                assert checked["test_exit_code"] == 0, checked
                results[-1]["candidate_test_exit_code"] = checked["test_exit_code"]
        try:
            run_native(launch + ["--version"], env={**env, "OPENCODE_EXPERIMENTAL_NATIVE_LLM": "true"}, cwd=temp, timeout=10)
        except ValueError as error:
            assert str(error) == "alternate runtime refused before native launch"
            results.append({"case": "alternate-runtime", "native_launches": 0, "passed": True})
        else:
            raise AssertionError("alternate runtime was launched")
        with binary.open("rb") as source:
            binary_digest = hashlib.file_digest(source, "sha256").hexdigest()
        print(json.dumps({"scope": "offline-native-only", "version": VERSION,
                          "binary_sha256": binary_digest,
                          "guard_sha256": hashlib.sha256((ROOT / "scripts/dev/openrouter-transport-guard.mjs").read_bytes()).hexdigest(),
                          "required_provider": args.required_provider,
                          "results": results}, sort_keys=True))


if __name__ == "__main__":
    main()
