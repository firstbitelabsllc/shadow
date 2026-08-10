from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


def activation_targets(home: Path) -> dict[str, Path]:
    """Read the same public supported-list contract a fresh install reads."""
    import importlib.util

    directives = ROOT / "scripts" / "shadow-host-directives.py"
    spec = importlib.util.spec_from_file_location("shadow_host_directives_for_test", directives)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.supported_activation_targets(home=home)


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


class DoctorNamesEverySupportedHostThatDidNotReceiveTheDirective(unittest.TestCase):
    def test_every_documented_target_has_its_own_actionable_missing_directive_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            targets = activation_targets(home)
            result = subprocess.run(
                [sys.executable, str(DOCTOR), "--json"],
                cwd=ROOT,
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
        report = json.loads(result.stdout)
        checks = {entry["name"]: entry for entry in report["checks"]}
        self.assertNotIn("standing goal: cursor", checks)
        for selector in targets:
            with self.subTest(selector):
                missing = checks[f"standing goal: {selector}"]
                self.assertEqual(missing["state"], "warn")
                self.assertIn("no host instruction file", missing["detail"])
                self.assertIn("shadow goal --install", missing["detail"])


class DoctorReportsCursorProjectionWithoutClaimingGUIInspection(unittest.TestCase):
    def test_cursor_projection_is_a_manual_hash_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "DIRECTIVES.md"
            source.write_text(doctor_block := subprocess.run(
                [str(CLI), "goal"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(), encoding="utf-8")

            fake = SimpleNamespace(
                configured_directive_topology=lambda **_: {
                    "source": source,
                    "targets": {"claude": source, "codex": source},
                    "projections": {"cursor": "user_rules"},
                },
                verify_declared_topology=lambda _source, _targets: None,
                projection_sha256=lambda block: hashlib.sha256(block.encode("utf-8")).hexdigest(),
            )
            loader = SimpleNamespace(exec_module=lambda _module: None)
            spec = SimpleNamespace(loader=loader)
            doctor = import_doctor_module()
            with mock.patch.object(doctor.importlib.util, "spec_from_file_location", return_value=spec), mock.patch.object(
                doctor.importlib.util, "module_from_spec", return_value=fake
            ):
                checks = {item["name"]: item for item in doctor.host_goal_checks()}

        cursor = checks["standing goal: cursor"]
        self.assertEqual(cursor["state"], "warn")
        self.assertEqual(cursor["projection"], "user_rules")
        self.assertEqual(cursor["expected_sha256"], hashlib.sha256(doctor_block.encode()).hexdigest())
        self.assertIn("cannot inspect application settings", cursor["detail"])


def import_doctor_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("shadow_doctor_projection_test", DOCTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheGateUsesTheResolvedPythonNotBarePython3(unittest.TestCase):
    def test_readme_doctor_step_selects_the_default_installed_command(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('bash install.sh && PATH="$HOME/.local/bin:$PATH" shadow doctor', readme)
        self.assertNotIn("bash install.sh && shadow doctor", readme)

    def test_install_and_printed_doctor_command_use_the_versioned_interpreter(self) -> None:
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
            shim_dir = root / "shim-bin"
            shim_dir.mkdir()
            marker = root / "versioned-python-was-used"
            bare_python = shim_dir / "python3"
            bare_python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            bare_python.chmod(0o755)
            resolved_python = shim_dir / versioned
            resolved_python.write_text(
                "#!/bin/sh\n"
                f"printf x >> {shlex.quote(str(marker))}\n"
                f"exec {shlex.quote(str(real_interpreter))} \"$@\"\n",
                encoding="utf-8",
            )
            resolved_python.chmod(0o755)
            installed_bin = root / "installed-bin"
            home = root / "home"
            home.mkdir()
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{shim_dir}{os.pathsep}{Path(real_interpreter).parent}{os.pathsep}{os.environ.get('PATH', '')}",
                "SHADOW_PYTHON": "",
            }
            install = subprocess.run(
                ["bash", "install.sh", "--no-skills", "--bin-dir", str(installed_bin)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            doctor = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"PATH={shlex.quote(str(installed_bin))}:$PATH shadow doctor --json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            used_versioned_python = marker.is_file()

        self.assertEqual(install.returncode, 0, install.stderr)
        self.assertIn(f"next: PATH={installed_bin}:$PATH shadow doctor", install.stdout)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertTrue(json.loads(doctor.stdout)["ok"])
        self.assertTrue(used_versioned_python)


if __name__ == "__main__":
    unittest.main()
