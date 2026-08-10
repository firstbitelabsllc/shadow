from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
DOCTOR = ROOT / "scripts" / "shadow-doctor.py"


class DoctorTests(unittest.TestCase):
    def run_doctor(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(CLI), "doctor", *args],
            cwd=ROOT,
            env={**os.environ, **(env or {})},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_json_report_has_one_product_and_native_host_floor(self) -> None:
        result = self.run_doctor("--json")
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "shadow.doctor.v1")
        self.assertEqual(report["product"], "Shadow")
        self.assertEqual(result.returncode, 0 if report["ok"] else 1)
        names = {item["name"] for item in report["checks"]}
        self.assertIn("product identity", names)
        self.assertIn("native host floor", names)
        self.assertIn("skill mount: .agents", names)
        self.assertNotIn("skill mount: .codex", names)
        self.assertNotIn("token permissions", names)
        self.assertNotIn("background process", names)

    def test_bad_root_fails_identity_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            result = subprocess.run(
                ["python3", str(DOCTOR), "--json"],
                cwd=ROOT,
                env={**os.environ, "SHADOW_ROOT": dirname},
                capture_output=True,
                text=True,
                check=False,
            )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["ok"])
        self.assertNotIn("Traceback", result.stderr)

    def test_text_output_is_human_readable(self) -> None:
        result = self.run_doctor()
        self.assertIn("[PASS] product identity", result.stdout)
        self.assertIn("checks without hard failure", result.stdout)


class TheGateUsesTheResolvedPythonNotBarePython3(unittest.TestCase):
    def test_documented_install_uses_the_versioned_python_and_stays_doctor_clean(self) -> None:
        candidates = [
            name
            for name in ("python3.10", "python3.11", "python3.12", "python3.13", "python3.14")
            if shutil.which(name)
        ]
        if not candidates:
            self.skipTest("no versioned Python 3.10+ interpreter is installed")
        versioned = max(candidates, key=lambda name: int(name.rsplit(".", 1)[1]))
        real_interpreter = Path(shutil.which(versioned) or versioned).resolve()

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            home = root / "home"
            for host_dir in (".claude", ".agents", ".cursor", ".codex"):
                (home / host_dir).mkdir(parents=True)

            bare_python_used = root / "bare-python-used"
            versioned_python_used = root / "versioned-python-used"
            bare_python = fake_bin / "python3"
            bare_python.write_text(
                "#!/bin/sh\n"
                f"printf x >> {shlex.quote(str(bare_python_used))}\n"
                "exit 1\n",
                encoding="utf-8",
            )
            bare_python.chmod(0o755)
            versioned_python = fake_bin / versioned
            versioned_python.write_text(
                "#!/bin/sh\n"
                f"printf x >> {shlex.quote(str(versioned_python_used))}\n"
                f"exec {shlex.quote(str(real_interpreter))} \"$@\"\n",
                encoding="utf-8",
            )
            versioned_python.chmod(0o755)
            codex = fake_bin / "codex"
            codex.write_text("#!/bin/sh\nprintf 'codex test host\\n'\n", encoding="utf-8")
            codex.chmod(0o755)

            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "SHADOW_PYTHON": "",
            }
            env.pop("SHADOW_ROOT", None)
            env.pop("SHADOW_DOCTOR_EXPECTED_CLI", None)
            install = subprocess.run(
                ["bash", str(ROOT / "install.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            installed_bin = home / ".local" / "bin"
            doctor: subprocess.CompletedProcess[str] | None = None
            if install.returncode == 0:
                doctor = subprocess.run(
                    [str(installed_bin / "shadow"), "doctor", "--json"],
                    cwd=ROOT,
                    env={**env, "PATH": f"{installed_bin}{os.pathsep}{env['PATH']}"},
                    capture_output=True,
                    text=True,
                    check=False,
                )
            bare_python_was_used = bare_python_used.exists()
            versioned_python_was_used = versioned_python_used.exists()

        self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
        self.assertIn(f"next: {installed_bin}/shadow doctor", install.stdout)
        self.assertFalse(bare_python_was_used)
        self.assertTrue(versioned_python_was_used)
        self.assertIsNotNone(doctor)
        assert doctor is not None
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        report = json.loads(doctor.stdout)
        self.assertTrue(report["ok"])
        checks = {item["name"]: item["state"] for item in report["checks"]}
        self.assertEqual(checks["standing goal: claude"], "pass")
        self.assertEqual(checks["standing goal: codex"], "pass")

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("writes or\nrefreshes the standing goal", readme)
        self.assertIn("Do not paste the goal separately", readme)
        self.assertNotIn("Then paste the standing goal", readme)


if __name__ == "__main__":
    unittest.main()
