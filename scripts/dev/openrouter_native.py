"""Shared native isolation for the unregistered OpenRouter experiment.

The caller owns admission and the provider source. No credentials are read here.
The native characterization and private wrapper must use this same preparation.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.18.25"
BINARY_SHA256 = "88eed7b0c2431162422cb0625aa68a55239970446951e4c9aad6a4f1fbc232b9"
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



@dataclass
class NativeSession:
    root: Path
    launch: list
    env: dict
    config: dict


@contextmanager
def native_session(binary, sdk, *, provider_source=None, guard_source=None):
    """Prepare one network-denied, isolated native session; clean up on return.

    provider_source=None retains the historical plugin characterization only.
    Every mandatory-provider caller supplies trusted module bytes explicitly.
    The apiKey is a placeholder, never a real credential.
    """
    binary = Path(binary).resolve(strict=True)
    sdk = Path(sdk).resolve(strict=True)
    with binary.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != BINARY_SHA256:
            raise ValueError("uncharacterized native binary refused before launch")
    package = json.loads((sdk / "@opencode-ai/plugin/package.json").read_text())
    if package["version"] != VERSION:
        raise ValueError("SDK version differs from characterized binary")
    if provider_source is not None:
        if not isinstance(provider_source, bytes) or not provider_source:
            raise ValueError("mandatory provider source is required")
        package = json.loads((sdk / "@openrouter/ai-sdk-provider/package.json").read_text())
        if package["version"] != "2.9.0":
            raise ValueError("provider SDK differs from characterized version")
    for item in sdk.rglob("*"):
        if item.is_symlink():
            item.resolve(strict=True).relative_to(sdk)
    minimal_env = {"PATH": "/opt/homebrew/bin:/usr/bin:/bin", "SHELL": "/bin/sh"}
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
        (temp / "home").mkdir()
        (temp / "tmp").mkdir()
        minimal_env = {**minimal_env, "HOME": str(temp / "home"), "TMPDIR": str(temp / "tmp")}
        xdg = {f"XDG_{key}_HOME": str(temp / key.lower()) for key in ("CONFIG", "DATA", "CACHE", "STATE")}
        isolated_env = {**minimal_env, **xdg,
                        "OPENCODE_DISABLE_MODELS_FETCH": "1", "OPENCODE_DISABLE_AUTOUPDATE": "1"}
        version = run_native(launch + ["--version"], env=isolated_env, cwd=temp, timeout=10)
        if version.returncode or version.stdout.strip() != VERSION:
            raise ValueError("native binary version probe failed")
        (temp / "config/opencode").mkdir(parents=True, exist_ok=True)
        (temp / "config/opencode/node_modules").symlink_to(sdk, target_is_directory=True)
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(sdk.parent / name, temp / "config/opencode" / name)
        if guard_source is None:
            guard_source = (ROOT / "scripts/dev/openrouter-transport-guard.mjs").read_bytes()
        if not isinstance(guard_source, bytes) or not guard_source:
            raise ValueError("guard source is required")
        (temp / "transport-guard.mjs").write_bytes(guard_source)
        env = {**minimal_env, **xdg,
               "OPENCODE_CONFIG": str(temp / "config.json"), "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
               "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1", "OPENCODE_DISABLE_MODELS_FETCH": "1", "OPENCODE_DISABLE_AUTOUPDATE": "1"}
        config = {"$schema": "https://opencode.ai/config.json", "model": "openrouter/openrouter/free",
                  "small_model": "openrouter/openrouter/free", "enabled_providers": ["openrouter"],
                  "share": "disabled", "autoupdate": False, "permission": {"*": "deny"},
                  "plugin": [], "provider": {"openrouter": {
                      "options": {"apiKey": "deferred-placeholder-not-a-credential", "baseURL": "https://openrouter.ai/api/v1"},
                      "models": {"openrouter/free": {"name": "Free router", "options": {"provider": POLICY}}}}}}
        if provider_source is not None:
            (temp / "provider.mjs").write_bytes(provider_source)
            config["provider"]["openrouter"]["npm"] = (temp / "provider.mjs").as_uri()
            env.update({"OPENCODE_PURE": "true", "OPENCODE_EXPERIMENTAL_NATIVE_LLM": "false",
                        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "true", "OPENCODE_DISABLE_CLAUDE_CODE": "true",
                        "OPENCODE_DISABLE_LSP_DOWNLOAD": "true"})
        yield NativeSession(temp, launch, env, config)
