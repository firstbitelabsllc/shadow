from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from browser.server import plan_record


ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "scripts" / "shadow-init.py"
SPEC = importlib.util.spec_from_file_location("shadow_init", INIT)
assert SPEC and SPEC.loader
shadow_init = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow_init)


def run(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INIT), *args],
        cwd=cwd,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


class InitTests(unittest.TestCase):
    def make_repo(self, root: Path, name: str = "useful-project") -> Path:
        repo = root / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo

    def call_main(
        self,
        repo: Path,
        home: Path,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        previous = Path.cwd()
        try:
            os.chdir(repo)
            with (
                mock.patch.dict(os.environ, {"HOME": str(home)}),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = shadow_init.main(["--here"])
        finally:
            os.chdir(previous)
        return result, stdout.getvalue(), stderr.getvalue()

    def strand_generated_plan(self, repo: Path, home: Path) -> Path:
        with mock.patch.object(
            shadow_init.board,
            "complete_init_registration",
            side_effect=shadow_init.board.BoardError("injected registration failure"),
        ):
            result, _, stderr = self.call_main(repo, home)
        self.assertEqual(result, 1)
        self.assertIn("could not register", stderr)
        destination = (
            home
            / ".shadow"
            / "plans"
            / shadow_init.board.local_plan_slug(repo.name)
            / "PLAN.md"
        )
        self.assertTrue(destination.is_file())
        self.assertFalse(destination.is_symlink())
        self.assertIsNotNone(
            shadow_init.board.read_init_registration(destination, home=home)
        )
        self.assertEqual(
            json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8")),
            shadow_init.board._empty(),
        )
        return destination

    def locator_state(self, path: Path) -> tuple[object, ...]:
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            target = Path(os.readlink(path))
            if not target.is_absolute():
                target = path.parent / target
            payload: object = (os.readlink(path), target.read_bytes())
        else:
            payload = path.read_bytes()
        return (
            metadata.st_mode,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            payload,
        )

    def journal_ref(self, destination: Path) -> str:
        return shadow_init.board._init_registration_ref(destination)

    def journal_oid(self, destination: Path, home: Path) -> str | None:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(home / ".shadow"),
                "rev-parse",
                "--verify",
                "--quiet",
                self.journal_ref(destination),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 1:
            return None
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def journal_head(self, home: Path) -> str:
        result = subprocess.run(
            ["git", "-C", str(home / ".shadow"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def replace_journal_ref(
        self,
        destination: Path,
        home: Path,
        *,
        content: bytes | None = None,
        target: str | None = None,
    ) -> str:
        root = home / ".shadow"
        if content is not None:
            stored = subprocess.run(
                ["git", "-C", str(root), "hash-object", "-w", "--stdin"],
                input=content,
                capture_output=True,
                check=True,
            )
            target = stored.stdout.decode("ascii").strip()
        self.assertIsNotNone(target)
        current = self.journal_oid(destination, home)
        self.assertIsNotNone(current)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "update-ref",
                self.journal_ref(destination),
                target,
                current,
            ],
            check=True,
        )
        return target

    def authority_state(
        self,
        destination: Path,
        home: Path,
    ) -> tuple[bytes, str, str | None]:
        return (
            (home / ".shadow" / "board.json").read_bytes(),
            self.journal_head(home),
            self.journal_oid(destination, home),
        )

    def test_creates_one_typed_local_plan_for_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = home / ".shadow" / "plans" / "useful-project" / "PLAN.md"
            result = run("--here", cwd=repo, home=home)
            record = plan_record(destination, home)
            plan = destination.read_text(encoding="utf-8")
            board = json.loads((home / ".shadow" / "board.json").read_text(encoding="utf-8"))
            pending = shadow_init.board.read_init_registration(destination, home=home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"created local PLAN.md: {destination}\n")
        self.assertIsNone(record["contract_error"])
        self.assertEqual(record["briefing"]["state"], "needs_you")
        self.assertEqual(len(record["briefing"]["choices"]), 3)
        self.assertEqual(board["entities"][0]["plan"], str(destination.resolve()))
        self.assertNotIn(dirname, json.dumps(record))
        self.assertIn("Complete the full declared outcome", plan)
        self.assertIn("every safe reachable lane", plan)
        self.assertIn("- Option A ID: derive-and-execute", plan)
        self.assertNotIn("smallest", plan.lower())
        self.assertNotIn(" ".join(("one", "bounded")), plan.lower())
        self.assertNotIn("- Origin:", plan)
        self.assertIsNone(pending)

    def test_long_repo_name_separates_plan_storage_from_project_identity(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            name = "shadow-pex-root-isolation-20260828-long-checkout-name"
            repo = self.make_repo(root, name)
            home = root / "home"
            storage_slug = shadow_init.board.local_plan_slug(name)
            project_id = storage_slug[:32]
            destination = home / ".shadow" / "plans" / storage_slug / "PLAN.md"
            result = run("--here", cwd=repo, home=home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, f"created local PLAN.md: {destination}\n")
            plan = destination.read_text(encoding="utf-8")
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            resolved = shadow_init.board.local_plan_for_repo(repo, home=home)
        self.assertGreater(len(name), 48)
        self.assertEqual(
            storage_slug, "shadow-pex-root-isolation-20260828-long-checkout"
        )
        self.assertEqual(project_id, "shadow-pex-root-isolation-202608")
        self.assertEqual(len(storage_slug), 48)
        self.assertEqual(len(project_id), 32)
        self.assertIn(f"- Project: {project_id}\n", plan)
        self.assertEqual(board["entities"][0]["project"], project_id)
        self.assertEqual(board["entities"][0]["plan"], str(destination.resolve()))
        self.assertEqual(resolved, destination.resolve())

    def test_writes_normalized_origin_from_ssh_or_https(self) -> None:
        urls = (
            "git@github.com:example/widget.git",
            "https://github.com/example/widget.git",
            "ssh://git@github.com/example/widget.git",
        )
        for url in urls:
            with self.subTest(url=url):
                with tempfile.TemporaryDirectory() as dirname:
                    root = Path(dirname)
                    repo = self.make_repo(root)
                    subprocess.run(
                        ["git", "-C", str(repo), "remote", "add", "origin", url],
                        check=True,
                    )
                    home = root / "home"
                    destination = home / ".shadow" / "plans" / "useful-project" / "PLAN.md"
                    result = run("--here", cwd=repo, home=home)
                    plan = destination.read_text(encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("- Origin: github.com/example/widget\n", plan)
                self.assertNotIn("git@github.com", plan)
                self.assertNotIn("https://", plan)
                self.assertNotIn(dirname, plan)

    def test_omits_origin_when_the_remote_is_a_filesystem_path(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            cases = (("relative-repo", "../forge.git"), ("absolute-repo", str(root / "forge.git")))
            for name, url in cases:
                with self.subTest(url=url):
                    repo = root / name
                    repo.mkdir()
                    subprocess.run(["git", "init", "-q", str(repo)], check=True)
                    subprocess.run(
                        ["git", "-C", str(repo), "remote", "add", "origin", url],
                        check=True,
                    )
                    home = root / f"home-{name}"
                    destination = home / ".shadow" / "plans" / name / "PLAN.md"
                    result = run("--here", cwd=repo, home=home)
                    plan = destination.read_text(encoding="utf-8")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn("- Origin:", plan)
                    self.assertNotIn(dirname, plan)
                    self.assertNotIn("/Users/", plan)

    def test_exclusive_plan_write_fsyncs_its_file_and_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            destination = Path(dirname) / "nested" / "PLAN.md"
            destination.parent.mkdir()
            kinds = {"file": False, "dir": False}
            real_fsync = os.fsync

            def spy(fd: int) -> None:
                kinds["dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"] = True
                real_fsync(fd)

            with mock.patch.object(shadow_init.os, "fsync", side_effect=spy):
                shadow_init.write_exclusive(destination, "# Plan\n")
        self.assertEqual(kinds, {"file": True, "dir": True})

    def test_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = home / ".shadow" / "plans" / "useful-project" / "PLAN.md"
            destination.parent.mkdir(parents=True)
            destination.write_text("keep me\n", encoding="utf-8")
            result = run("--here", cwd=repo, home=home)
            self.assertEqual(destination.read_text(encoding="utf-8"), "keep me\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to overwrite", result.stderr)

    def test_retry_after_catchable_registration_failure_registers_untouched_plan_once(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = self.strand_generated_plan(repo, home)
            before = self.locator_state(destination)
            pending = shadow_init.board.read_init_registration(destination, home=home)
            self.assertIsNotNone(pending)

            retried, stdout, stderr = self.call_main(repo, home)

            self.assertEqual(retried, 0, stderr)
            self.assertEqual(stdout, f"recognized local PLAN.md: {destination}\n")
            self.assertEqual(self.locator_state(destination), before)
            board_path = home / ".shadow" / "board.json"
            board = json.loads(board_path.read_text(encoding="utf-8"))
            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                expected_identity = shadow_init.board.entity_id(destination)
            self.assertEqual(
                board["entities"],
                [{
                    "id": expected_identity,
                    "project": "useful-project",
                    "plan": str(destination.resolve()),
                    "resume": "~a1b2",
                }],
            )
            self.assertEqual(board["claims"], [])
            self.assertIsNone(
                shadow_init.board.read_init_registration(destination, home=home)
            )
            registered = board_path.read_bytes()

            third, _, third_stderr = self.call_main(repo, home)

            self.assertEqual(third, 1)
            self.assertIn("refusing to overwrite", third_stderr)
            self.assertEqual(self.locator_state(destination), before)
            self.assertEqual(board_path.read_bytes(), registered)
            self.assertIsNone(
                shadow_init.board.read_init_registration(destination, home=home)
            )

    def test_retry_after_pre_plan_interruption_reuses_anchored_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = home / ".shadow" / "plans" / "useful-project" / "PLAN.md"
            first = shadow_init.datetime(
                2026,
                1,
                2,
                3,
                4,
                5,
                tzinfo=shadow_init.timezone.utc,
            )
            second = shadow_init.datetime(
                2030,
                6,
                7,
                8,
                9,
                10,
                tzinfo=shadow_init.timezone.utc,
            )

            with (
                mock.patch.object(shadow_init, "datetime") as clock,
                mock.patch.object(
                    shadow_init,
                    "write_exclusive",
                    side_effect=OSError("injected publication failure"),
                ),
            ):
                clock.now.return_value = first
                result, _, stderr = self.call_main(repo, home)

            self.assertEqual(result, 1)
            self.assertIn("could not write", stderr)
            self.assertFalse(destination.exists())
            pending = shadow_init.board.read_init_registration(destination, home=home)
            self.assertIsNotNone(pending)
            receipt = shadow_init.parse_registration_receipt(pending)
            self.assertEqual(receipt["generated_at"], "2026-01-02T03:04:05Z")

            with mock.patch.object(shadow_init, "datetime") as clock:
                clock.now.return_value = second
                recovered, _, recovery_error = self.call_main(repo, home)

            self.assertEqual(recovered, 0, recovery_error)
            plan = destination.read_text(encoding="utf-8")
            self.assertIn("2026-01-02T03:04:05Z", plan)
            self.assertNotIn("2030-06-07T08:09:10Z", plan)
            self.assertIsNone(
                shadow_init.board.read_init_registration(destination, home=home)
            )
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(board["entities"]), 1)
            self.assertEqual(board["claims"], [])

    def test_retry_recovery_refuses_changed_or_raced_state_without_authority_mutation(
        self,
    ) -> None:
        def add_origin(repo: Path) -> None:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "remote",
                    "add",
                    "origin",
                    "git@github.com:example/useful-project.git",
                ],
                check=True,
            )

        def edited(destination: Path, _: Path) -> None:
            destination.write_bytes(destination.read_bytes() + b"\n- user note\n")

        def retimestamped(destination: Path, _: Path) -> None:
            timestamps = shadow_init.UTC_TIMESTAMP.findall(
                destination.read_text(encoding="utf-8")
            )
            self.assertEqual(len(timestamps), 2)
            destination.write_text(
                destination.read_text(encoding="utf-8").replace(
                    timestamps[0],
                    "2000-01-01T00:00:00Z",
                ),
                encoding="utf-8",
            )

        def malformed(destination: Path, _: Path) -> None:
            destination.write_bytes(b"\xff\xfe")

        def symlinked(destination: Path, root: Path) -> None:
            target = root / "other-writer-plan"
            target.write_bytes(b"owned elsewhere\n")
            destination.unlink()
            destination.symlink_to(target)

        def wrong_origin(destination: Path, _: Path) -> None:
            destination.write_bytes(
                destination.read_bytes().replace(
                    b"github.com/example/useful-project",
                    b"github.com/other/useful-project",
                )
            )

        def replaced(destination: Path, _: Path) -> None:
            content = destination.read_bytes()
            destination.unlink()
            destination.write_bytes(content + b"\n")

        def changed_checkout_origin(_: Path, repo: Path) -> None:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "remote",
                    "set-url",
                    "origin",
                    "git@github.com:other/useful-project.git",
                ],
                check=True,
            )

        cases = {
            "edited": edited,
            "retimestamped": retimestamped,
            "malformed": malformed,
            "symlinked": symlinked,
            "wrong-origin": wrong_origin,
            "replaced": replaced,
            "checkout-origin-changed": changed_checkout_origin,
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = self.make_repo(root)
                add_origin(repo)
                home = root / "home"
                destination = self.strand_generated_plan(repo, home)
                mutate(destination, repo if name == "checkout-origin-changed" else root)
                before = self.locator_state(destination)
                authority_before = self.authority_state(destination, home)

                result, _, stderr = self.call_main(repo, home)

                self.assertEqual(result, 1)
                self.assertTrue(
                    "refusing to overwrite" in stderr
                    or "belongs to another repository" in stderr
                )
                self.assertEqual(self.locator_state(destination), before)
                self.assertEqual(
                    self.authority_state(destination, home),
                    authority_before,
                )

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            add_origin(repo)
            home = root / "home"
            destination = self.strand_generated_plan(repo, home)
            original = destination.read_bytes()
            real_register = shadow_init.board.complete_init_registration
            replacement_state: tuple[object, ...] | None = None
            reached_registration = False

            def replace_then_register(*args, **kwargs):
                nonlocal reached_registration, replacement_state
                reached_registration = True
                destination.unlink()
                destination.write_bytes(original)
                replacement_state = self.locator_state(destination)
                return real_register(*args, **kwargs)

            with mock.patch.object(
                shadow_init.board,
                "complete_init_registration",
                side_effect=replace_then_register,
            ):
                result, _, _ = self.call_main(repo, home)

            self.assertTrue(reached_registration)
            self.assertEqual(result, 1)
            self.assertEqual(self.locator_state(destination), replacement_state)

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            add_origin(repo)
            home = root / "home"
            destination = self.strand_generated_plan(repo, home)
            before = self.locator_state(destination)
            authority_before = self.authority_state(destination, home)

            with mock.patch.object(
                shadow_init,
                "proof_source_origin",
                side_effect=(
                    "github.com/example/useful-project",
                    "github.com/other/useful-project",
                ),
            ):
                result, _, _ = self.call_main(repo, home)

            self.assertEqual(result, 1)
            self.assertEqual(self.locator_state(destination), before)
            self.assertEqual(
                self.authority_state(destination, home),
                authority_before,
            )

        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            add_origin(repo)
            home = root / "home"
            destination = self.strand_generated_plan(repo, home)
            real_register = shadow_init.board.complete_init_registration
            board_path = home / ".shadow" / "board.json"
            peer_board: bytes | None = None
            reached_registration = False

            def peer_then_register(*args, **kwargs):
                nonlocal reached_registration, peer_board
                reached_registration = True
                shadow_init.board.reconcile([args[0]], [], home=kwargs["home"])
                peer_board = board_path.read_bytes()
                return real_register(*args, **kwargs)

            with mock.patch.object(
                shadow_init.board,
                "complete_init_registration",
                side_effect=peer_then_register,
            ):
                result, _, stderr = self.call_main(repo, home)

            self.assertTrue(reached_registration)
            self.assertEqual(result, 0, stderr)
            self.assertEqual(board_path.read_bytes(), peer_board)
            board = json.loads(board_path.read_text(encoding="utf-8"))
            self.assertEqual(len(board["entities"]), 1)
            self.assertEqual(board["claims"], [])
            self.assertIsNone(self.journal_oid(destination, home))

    def test_retry_refuses_missing_malformed_replaced_or_wrong_repository_ref(
        self,
    ) -> None:
        mutations = (
            "missing",
            "malformed",
            "replaced",
            "symbolic",
            "wrong-repository",
        )
        for name in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = self.make_repo(root)
                home = root / "home"
                destination = self.strand_generated_plan(repo, home)
                plan_before = self.locator_state(destination)
                current = self.journal_oid(destination, home)
                self.assertIsNotNone(current)
                if name == "missing":
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(home / ".shadow"),
                            "update-ref",
                            "-d",
                            self.journal_ref(destination),
                            current,
                        ],
                        check=True,
                    )
                elif name == "malformed":
                    self.replace_journal_ref(
                        destination,
                        home,
                        target=self.journal_head(home),
                    )
                elif name == "replaced":
                    self.replace_journal_ref(
                        destination,
                        home,
                        content=b"not-json\n",
                    )
                elif name == "symbolic":
                    target_ref = "refs/shadow/test-init-target"
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(home / ".shadow"),
                            "update-ref",
                            target_ref,
                            current,
                        ],
                        check=True,
                    )
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(home / ".shadow"),
                            "symbolic-ref",
                            self.journal_ref(destination),
                            target_ref,
                        ],
                        check=True,
                    )
                else:
                    pending = shadow_init.board.read_init_registration(
                        destination,
                        home=home,
                    )
                    self.assertIsNotNone(pending)
                    parsed = shadow_init.parse_registration_receipt(pending)
                    self.replace_journal_ref(
                        destination,
                        home,
                        content=shadow_init.registration_receipt(
                            "0" * 64,
                            parsed["generated_at"],
                            destination.read_bytes(),
                        ),
                    )
                authority_before = self.authority_state(destination, home)

                result, _, stderr = self.call_main(repo, home)

                self.assertEqual(result, 1)
                self.assertTrue(
                    "refusing to overwrite" in stderr
                    or "receipt" in stderr
                    or "belongs to another repository" in stderr
                )
                if name == "symbolic":
                    self.assertIn("receipt ref is symbolic", stderr)
                self.assertEqual(self.locator_state(destination), plan_before)
                self.assertEqual(
                    self.authority_state(destination, home),
                    authority_before,
                )

    def test_retry_receipt_binds_a_private_repository_identity(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            first_root = root / "first"
            second_root = root / "second"
            first_root.mkdir()
            second_root.mkdir()
            first = self.make_repo(first_root, "same-name")
            second = self.make_repo(second_root, "same-name")
            home = root / "home"
            destination = self.strand_generated_plan(first, home)
            plan_before = self.locator_state(destination)
            authority_before = self.authority_state(destination, home)

            result, _, stderr = self.call_main(second, home)

            self.assertEqual(result, 1)
            self.assertIn("belongs to another repository", stderr)
            self.assertEqual(self.locator_state(destination), plan_before)
            self.assertEqual(
                self.authority_state(destination, home),
                authority_before,
            )

            recovered, _, recovery_error = self.call_main(first, home)

            self.assertEqual(recovered, 0, recovery_error)
            board = json.loads(
                (home / ".shadow" / "board.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(board["entities"]), 1)
            self.assertEqual(board["claims"], [])
            self.assertIsNone(self.journal_oid(destination, home))

    def test_retry_recovery_ignores_coordinated_plan_and_adjacent_receipt_rewrite(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = self.strand_generated_plan(repo, home)
            anchored = self.authority_state(destination, home)
            timestamps = shadow_init.UTC_TIMESTAMP.findall(
                destination.read_text(encoding="utf-8")
            )
            self.assertEqual(len(timestamps), 2)
            rewritten = destination.read_text(encoding="utf-8").replace(
                timestamps[0],
                "2000-01-01T00:00:00Z",
            )
            destination.write_text(rewritten, encoding="utf-8")
            adjacent = destination.parent / ".shadow-init-registration.json"
            adjacent.write_bytes(
                shadow_init.registration_receipt(
                    shadow_init.repository_recovery_identity(repo, None),
                    "2000-01-01T00:00:00Z",
                    rewritten.encode("utf-8"),
                )
            )
            plan_before = self.locator_state(destination)
            adjacent_before = self.locator_state(adjacent)

            result, _, stderr = self.call_main(repo, home)

            self.assertEqual(result, 1)
            self.assertIn("refusing to overwrite", stderr)
            self.assertEqual(self.locator_state(destination), plan_before)
            self.assertEqual(self.locator_state(adjacent), adjacent_before)
            self.assertEqual(self.authority_state(destination, home), anchored)

    def test_completion_revalidates_receipt_and_repository_before_registration(
        self,
    ) -> None:
        for mutation in ("delete-receipt", "replace-receipt", "change-origin"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = self.make_repo(root)
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "remote",
                        "add",
                        "origin",
                        "git@github.com:example/useful-project.git",
                    ],
                    check=True,
                )
                home = root / "home"
                destination = self.strand_generated_plan(repo, home)
                board_path = home / ".shadow" / "board.json"
                board_before = board_path.read_bytes()
                head_before = self.journal_head(home)
                mutated_ref: str | None = None
                real_register = shadow_init.board.complete_init_registration

                def mutate_then_register(*args, **kwargs):
                    nonlocal mutated_ref
                    if mutation == "delete-receipt":
                        current = self.journal_oid(destination, home)
                        self.assertIsNotNone(current)
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(home / ".shadow"),
                                "update-ref",
                                "--no-deref",
                                "-d",
                                self.journal_ref(destination),
                                current,
                            ],
                            check=True,
                        )
                    elif mutation == "replace-receipt":
                        mutated_ref = self.replace_journal_ref(
                            destination,
                            home,
                            content=b"replacement\n",
                        )
                    else:
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(repo),
                                "remote",
                                "set-url",
                                "origin",
                                "git@github.com:other/useful-project.git",
                            ],
                            check=True,
                        )
                    return real_register(*args, **kwargs)

                with mock.patch.object(
                    shadow_init.board,
                    "complete_init_registration",
                    side_effect=mutate_then_register,
                ):
                    result, _, stderr = self.call_main(repo, home)

                self.assertEqual(result, 1)
                self.assertIn("could not register", stderr)
                self.assertEqual(board_path.read_bytes(), board_before)
                self.assertEqual(self.journal_head(home), head_before)
                if mutation == "replace-receipt":
                    self.assertEqual(
                        self.journal_oid(destination, home),
                        mutated_ref,
                    )
                elif mutation == "delete-receipt":
                    self.assertIsNone(self.journal_oid(destination, home))

    def test_completion_rolls_back_when_receipt_or_repository_changes_during_commit(
        self,
    ) -> None:
        for mutation in ("delete-receipt", "replace-receipt", "change-origin"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as dirname:
                root = Path(dirname)
                repo = self.make_repo(root)
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "remote",
                        "add",
                        "origin",
                        "git@github.com:example/useful-project.git",
                    ],
                    check=True,
                )
                home = root / "home"
                destination = self.strand_generated_plan(repo, home)
                board_path = home / ".shadow" / "board.json"
                board_before = board_path.read_bytes()
                head_before = self.journal_head(home)
                plan_before = self.locator_state(destination)
                receipt_before = self.journal_oid(destination, home)
                self.assertIsNotNone(receipt_before)
                mutated_ref: str | None = None

                if mutation == "change-origin":
                    real_commit = shadow_init.board._commit_consuming_ref

                    def mutate_origin_then_commit(*args, **kwargs):
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(repo),
                                "remote",
                                "set-url",
                                "origin",
                                "git@github.com:other/useful-project.git",
                            ],
                            check=True,
                        )
                        return real_commit(*args, **kwargs)

                    patch = mock.patch.object(
                        shadow_init.board,
                        "_commit_consuming_ref",
                        side_effect=mutate_origin_then_commit,
                    )
                else:
                    real_transaction = shadow_init.board._git_ref_transaction

                    def mutate_ref_then_transaction(*args, **kwargs):
                        nonlocal mutated_ref
                        current = self.journal_oid(destination, home)
                        self.assertIsNotNone(current)
                        if mutation == "delete-receipt":
                            subprocess.run(
                                [
                                    "git",
                                    "-C",
                                    str(home / ".shadow"),
                                    "update-ref",
                                    "--no-deref",
                                    "-d",
                                    self.journal_ref(destination),
                                    current,
                                ],
                                check=True,
                            )
                        else:
                            mutated_ref = self.replace_journal_ref(
                                destination,
                                home,
                                content=b"replacement\n",
                            )
                        return real_transaction(*args, **kwargs)

                    patch = mock.patch.object(
                        shadow_init.board,
                        "_git_ref_transaction",
                        side_effect=mutate_ref_then_transaction,
                    )

                with patch:
                    result, _, stderr = self.call_main(repo, home)

                self.assertEqual(result, 1)
                self.assertIn("could not register", stderr)
                self.assertEqual(board_path.read_bytes(), board_before)
                self.assertEqual(self.journal_head(home), head_before)
                self.assertEqual(self.locator_state(destination), plan_before)
                if mutation == "replace-receipt":
                    self.assertEqual(
                        self.journal_oid(destination, home),
                        mutated_ref,
                    )
                elif mutation == "delete-receipt":
                    self.assertIsNone(self.journal_oid(destination, home))
                else:
                    self.assertEqual(
                        self.journal_oid(destination, home),
                        receipt_before,
                    )

    def test_retry_after_registration_cleanup_failure_clears_ref_without_duplicate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            destination = self.strand_generated_plan(repo, home)
            self.assertIsNotNone(self.journal_oid(destination, home))
            state, content = shadow_init.generated_plan_snapshot(
                destination,
                destination.read_bytes(),
            )
            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                seed = shadow_init.registration_seed(
                    destination,
                    repo,
                    state,
                    content,
                )
                shadow_init.board.reconcile([seed], [], home=home)
            board_path = home / ".shadow" / "board.json"
            registered = board_path.read_bytes()

            retried, _, retry_error = self.call_main(repo, home)

            self.assertEqual(retried, 0, retry_error)
            self.assertEqual(board_path.read_bytes(), registered)
            self.assertIsNone(self.journal_oid(destination, home))

    def test_registration_commit_joins_foreground_git_maintenance(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            repo = self.make_repo(root)
            home = root / "home"
            trace = root / "git-trace.json"

            with mock.patch.dict(os.environ, {"GIT_TRACE2_EVENT": str(trace)}):
                result, _, stderr = self.call_main(repo, home)

            self.assertEqual(result, 0, stderr)
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            maintenance_argv = [
                event["argv"]
                for event in events
                if event.get("event") == "start"
                and "maintenance" in event.get("argv", [])
                and "run" in event.get("argv", [])
            ]
            self.assertTrue(maintenance_argv)
            self.assertTrue(
                all(
                    "--auto" in argv
                    and "--quiet" in argv
                    and "--no-detach" in argv
                    for argv in maintenance_argv
                )
            )

    def test_requires_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            outside = root / "outside"
            outside.mkdir()
            result = run("--here", cwd=outside, home=root / "home")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not inside a Git worktree", result.stderr)

    def test_rejects_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = self.make_repo(Path(dirname))
            nested = repo / "nested"
            nested.mkdir()
            result = run("--here", cwd=nested, home=Path(dirname) / "home")
        self.assertEqual(result.returncode, 2)
        self.assertIn("project root", result.stderr)


if __name__ == "__main__":
    unittest.main()
