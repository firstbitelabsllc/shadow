"""
Tests for scripts/vidux-init.sh.

Style matches test_write_verify.py: stdlib unittest, no pip, subprocess
against the real script with an isolated VIDUX_ROOT/cwd per test.

Run:
    python3 -m unittest tests.test_vidux_init -v
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vidux-init.sh"


def run_init(vidux_root, cwd, *args):
    env = dict(os.environ)
    env["VIDUX_ROOT"] = str(vidux_root)
    result = subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


class ViduxInitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.vidux_root = Path(self._tmp.name) / "vidux-checkout"
        self.vidux_root.mkdir()
        self.elsewhere = Path(self._tmp.name) / "my-real-app"
        self.elsewhere.mkdir()

    def test_creates_plan_under_vidux_root_regardless_of_cwd(self):
        # Round-3 panel finding: vidux init writes into VIDUX_ROOT/projects/
        # regardless of $PWD, by design (one vidux install acts as a
        # dashboard over many projects' plans) -- but the success message
        # used to read as if it were relative to $PWD, misleading a user
        # running this from their own project directory. This locks in the
        # documented behavior: run from an unrelated cwd, still lands under
        # VIDUX_ROOT.
        rc, out, err = run_init(self.vidux_root, self.elsewhere, "my-project")
        self.assertEqual(rc, 0, f"stderr={err}")
        target = self.vidux_root / "projects" / "my-project" / "PLAN.md"
        self.assertTrue(target.exists())
        self.assertFalse((self.elsewhere / "PLAN.md").exists(),
                          "must not write into the caller's cwd")
        self.assertFalse((self.elsewhere / "projects").exists())

    def test_success_message_prints_the_real_absolute_path(self):
        # The old message ("created projects/<slug>/PLAN.md") looked
        # cwd-relative but wasn't -- fixed to print the actual absolute
        # target so a confused first-run user can find the file.
        rc, out, _err = run_init(self.vidux_root, self.elsewhere, "my-project")
        self.assertEqual(rc, 0)
        expected = str(self.vidux_root / "projects" / "my-project" / "PLAN.md")
        self.assertIn(expected, out)
        self.assertNotEqual(out.strip(), "created projects/my-project/PLAN.md")

    def test_refuses_to_overwrite_and_error_shows_absolute_path(self):
        run_init(self.vidux_root, self.elsewhere, "my-project")
        rc, _out, err = run_init(self.vidux_root, self.elsewhere, "my-project")
        self.assertEqual(rc, 1)
        expected = str(self.vidux_root / "projects" / "my-project" / "PLAN.md")
        self.assertIn(expected, err)

    def test_template_has_canonical_sections(self):
        run_init(self.vidux_root, self.elsewhere, "my-project")
        text = (self.vidux_root / "projects" / "my-project" / "PLAN.md").read_text()
        for section in ("## Purpose", "## Evidence", "## Constraints",
                         "## Tasks", "## Decision Log", "## Progress"):
            self.assertIn(section, text)

    def test_invalid_slug_rejected(self):
        rc, _out, err = run_init(self.vidux_root, self.elsewhere, "Not Valid!")
        self.assertEqual(rc, 2)
        self.assertIn("invalid slug", err)


if __name__ == "__main__":
    unittest.main()
