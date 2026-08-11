from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "shadow"
DOCTOR = ROOT / "scripts" / "shadow-doctor.py"


class TheGateUsesTheResolvedPythonNotBarePython3(unittest.TestCase):
    def test_documented_install_and_doctor_use_the_versioned_interpreter(self) -> None:
        candidates = [
            name
            for name in ("python3.10", "python3.11", "python3.12", "python3.13", "python3.14")
            if shutil.which(name)
        ]
        if not candidates:
            self.skipTest("no versioned Python 3 interpreter is installed")
        versioned = max(candidates, key=lambda name: int(name.rsplit(".", 1)[1]))
        real_interpreter = Path(shutil.which(versioned) or sys.executable).resolve()

        with tempfile.TemporaryDirectory() as dirname:
            scratch = Path(dirname)
            home = scratch / "home"
            bin_dir = scratch / "bin"
            home.mkdir()
            bin_dir.mkdir()
            for host_home in (".claude", ".agents", ".cursor"):
                (home / host_home).mkdir()
            marker = scratch / "versioned-interpreter-used"

            low = bin_dir / "python3"
            low.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            low.chmod(0o755)
            wrapper = bin_dir / versioned
            wrapper.write_text(
                "#!/bin/sh\n"
                f"printf x >> {shlex.quote(str(marker))}\n"
                f"exec {shlex.quote(str(real_interpreter))} \"$@\"\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            host = bin_dir / "codex"
            host.write_text("#!/bin/sh\necho 'codex-cli fixture'\n", encoding="utf-8")
            host.chmod(0o755)
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}{os.pathsep}{Path(real_interpreter).parent}"
                        f"{os.pathsep}{os.environ.get('PATH', '')}",
                "SHADOW_PYTHON": "",
            }
            install = subprocess.run(
                ["bash", "install.sh", "--bin-dir", str(bin_dir)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            doctor = subprocess.run(
                [str(bin_dir / "shadow"), "doctor", "--json"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            used_versioned = marker.is_file()

        self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
        self.assertIn("next: shadow doctor", install.stdout)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertTrue(json.loads(doctor.stdout)["ok"])
        self.assertTrue(used_versioned, "the versioned interpreter was never used")


class DoctorNamesEverySupportedHostThatDidNotReceiveTheDirective(unittest.TestCase):
    def test_missing_instruction_files_name_each_documented_activation_host(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            scratch = Path(dirname)
            home = scratch / "home"
            bin_dir = scratch / "bin"
            home.mkdir()
            bin_dir.mkdir()
            for directory in (".claude", ".codex", ".agents", ".cursor"):
                (home / directory).mkdir()
            shadow = bin_dir / "shadow"
            shadow.symlink_to(CLI)
            host = bin_dir / "codex"
            host.write_text("#!/bin/sh\necho 'codex-cli fixture'\n", encoding="utf-8")
            host.chmod(0o755)
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                "SHADOW_DOCTOR_EXPECTED_CLI": str(CLI),
            }
            result = subprocess.run(
                [sys.executable, str(DOCTOR), "--json"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        report = json.loads(result.stdout)
        goal_checks = {
            item["name"]: item
            for item in report["checks"]
            if item["name"].startswith("standing goal:")
        }
        self.assertEqual(set(goal_checks), {
            "standing goal: claude-code",
            "standing goal: codex",
        })
        for item in goal_checks.values():
            self.assertEqual(item["state"], "warn")
            self.assertIn("shadow goal --install", item["detail"])


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


if __name__ == "__main__":
    unittest.main()
