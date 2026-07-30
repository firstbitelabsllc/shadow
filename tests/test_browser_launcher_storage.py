"""Launcher storage identity and immutable-package regressions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "bin" / "vidux-browse"


def store_id(path: Path) -> str:
    return hashlib.sha256(str(path.expanduser().resolve()).encode()).hexdigest()[:16]


class BrowserLauncherStorageTests(unittest.TestCase):
    def test_server_default_artifacts_live_outside_package_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            data = Path(tmp) / "data"
            env = dict(os.environ)
            env.update({"HOME": str(home), "XDG_DATA_HOME": str(data)})
            env.pop("VIDUX_BROWSER_ARTIFACTS_DIR", None)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import importlib.util, pathlib; "
                        f"p=pathlib.Path({str(ROOT / 'browser' / 'server.py')!r}); "
                        "s=importlib.util.spec_from_file_location('vidux_browser_storage_test', p); "
                        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                        "print(m.ARTIFACTS_DIR)"
                    ),
                ],
                capture_output=True,
                text=True,
                env=env,
                cwd=tmp,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            Path(result.stdout.strip()),
            (data / "vidux" / "artifacts").resolve(),
        )
        self.assertFalse(str(Path(result.stdout.strip())).startswith(str(ROOT)))

    def test_reuse_identity_covers_comments_and_artifacts_without_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            data = base / "data"
            dev_root = base / "projects"
            fakebin = base / "fakebin"
            for path in (home, data, dev_root, fakebin):
                path.mkdir(parents=True)

            (fakebin / "lsof").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fakebin / "curl").write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$VIDUX_TEST_HEALTH\"\n",
                encoding="utf-8",
            )
            (fakebin / "lsof").chmod(0o755)
            (fakebin / "curl").chmod(0o755)

            comments_a = base / "comments-a.jsonl"
            comments_b = base / "comments-b.jsonl"
            artifacts_a = data / "vidux" / "artifacts"
            artifacts_b = base / "artifacts-b"
            steering = home / ".vidux-browser" / "steering.jsonl"
            claims = home / ".agent-ledger" / "claims.jsonl"
            health = {
                "ok": True,
                "dev_root": str(dev_root.resolve()),
                "repo_root": str(ROOT.resolve()),
                "port": 7191,
                "server_mtime_ns": (ROOT / "browser" / "server.py").stat().st_mtime_ns,
                "steering_module_mtime_ns": (
                    ROOT / "browser" / "steering_mailbox.py"
                ).stat().st_mtime_ns,
                "coordination_module_mtime_ns": (
                    ROOT / "browser" / "coordination_claims.py"
                ).stat().st_mtime_ns,
                "steering_store_id": store_id(steering),
                "coordination_store_id": store_id(claims),
                "comments_store_id": store_id(comments_a),
                "artifacts_store_id": store_id(artifacts_a),
            }
            self.assertNotIn(str(home), json.dumps(health))
            self.assertNotIn(str(data), json.dumps(health))

            env = dict(os.environ)
            env.update(
                {
                    "HOME": str(home),
                    "XDG_DATA_HOME": str(data),
                    "PATH": f"{fakebin}{os.pathsep}{env['PATH']}",
                    "VIDUX_TEST_HEALTH": json.dumps(health),
                }
            )
            base_args = [
                str(LAUNCHER),
                "--no-open",
                "--port",
                "7191",
                "--root",
                str(dev_root),
            ]
            matched = subprocess.run(
                [*base_args, "--comments-path", str(comments_a)],
                capture_output=True,
                text=True,
                env=env,
            )
            wrong_comments = subprocess.run(
                [*base_args, "--comments-path", str(comments_b)],
                capture_output=True,
                text=True,
                env=env,
            )
            wrong_artifacts = subprocess.run(
                [
                    *base_args,
                    "--comments-path",
                    str(comments_a),
                    "--artifacts-dir",
                    str(artifacts_b),
                ],
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(matched.returncode, 0, matched.stderr)
        self.assertIn("already on", matched.stdout)
        self.assertEqual(wrong_comments.returncode, 1)
        self.assertIn("does not match", wrong_comments.stderr)
        self.assertEqual(wrong_artifacts.returncode, 1)
        self.assertIn("does not match", wrong_artifacts.stderr)


if __name__ == "__main__":
    unittest.main()
