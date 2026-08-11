"""One VERSION grammar: the Python reader agrees with the bash launcher.

Before ~vgra there were three grammars — the launcher skipped blank and
comment lines, four Python readers took the naive first line, and one test
stripped the whole file — so a VERSION file with a trailing note made
`shadow --version`, doctor, and the distribution test disagree. This pins the
single reader against the launcher on exactly the input that split them.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from shadow_version import read_version, VersionError  # noqa: E402

LAUNCHER = ROOT / "bin" / "shadow"


def _launcher_version(root: Path) -> str:
    """The launcher's own awk grammar, invoked exactly as bin/shadow does."""
    result = subprocess.run(
        ["awk", "NF && $1 !~ /^#/ { print; exit }", str(root / "VERSION")],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


class TheReaderMatchesTheLauncher(unittest.TestCase):
    def _fixture(self, contents: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        (directory / "VERSION").write_text(contents, encoding="utf-8")
        self.addCleanup(lambda: __import__("shutil").rmtree(directory, ignore_errors=True))
        return directory

    def test_bare_version_agrees(self) -> None:
        root = self._fixture("1.0.0\n")
        self.assertEqual(read_version(root), "1.0.0")
        self.assertEqual(read_version(root), _launcher_version(root))

    def test_leading_comment_and_blank_are_skipped_by_both(self) -> None:
        # The exact input that split the three old grammars: a comment first.
        root = self._fixture("# release notes below\n\n2.3.4\ntrailing note\n")
        self.assertEqual(read_version(root), "2.3.4")
        self.assertEqual(read_version(root), _launcher_version(root),
                         "the Python reader diverged from the launcher on a commented VERSION")

    def test_shipped_version_file_is_bare_semver(self) -> None:
        self.assertEqual(read_version(ROOT), _launcher_version(ROOT))

    def test_a_non_semver_payload_is_refused(self) -> None:
        root = self._fixture("v1.0\n")
        with self.assertRaises(VersionError):
            read_version(root)

    def test_a_file_with_no_payload_is_refused(self) -> None:
        root = self._fixture("# only a comment\n\n")
        with self.assertRaises(VersionError):
            read_version(root)


if __name__ == "__main__":
    unittest.main()
