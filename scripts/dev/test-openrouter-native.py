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
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
from openrouter_native import POLICY, VERSION, native_session, run_native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--sdk-node-modules", type=Path, required=True)
    parser.add_argument("--required-provider", action="store_true",
                        help="test mandatory provider initialization instead of the earlier plugin seam")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    provider_source = (ROOT / "tests/fixtures/openrouter-offline-provider.mjs").read_bytes() if args.required_provider else None
    with native_session(binary, args.sdk_node_modules, provider_source=provider_source) as session:
        temp, launch, env, config = session.root, session.launch, session.env, session.config
        shutil.copyfile(ROOT / "tests/fixtures/openrouter-offline-plugin.mjs", temp / "witness.mjs")
        if not args.required_provider:
            config["plugin"] = [(temp / "witness.mjs").as_uri()]
        cases = [("policy-present", POLICY), ("policy-missing", {})]
        if args.required_provider:
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
                assert checked["test_process_exit_code"] == 0, checked
                assert checked["accepted"] is False
                results[-1]["candidate_test_process_exit_code"] = checked["test_process_exit_code"]
                results[-1]["candidate_accepted"] = False
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
