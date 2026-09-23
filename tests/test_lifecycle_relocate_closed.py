"""`shadow lifecycle --relocate-closed` moves only closed plan text, whole.

Hand relocation failed twice in one pass on 2026-09-22: moving only `- `
head lines orphaned indented continuations, and treating every unkeyed
contradiction as closed archived open ones. These tests pin both failures and
the rest of the closure rules to the verb.
"""

from __future__ import annotations

import collections
import importlib.util
from pathlib import Path
import tempfile
import unittest

from tests.plan_tree_fixture import install_plan_tree
from tests.proc_fixture import git
from tests.test_lifecycle import LINT, apply_with_cas, lifecycle, make_repo, run

_LINT_SPEC = importlib.util.spec_from_file_location("shadow_lint_relocate_test", LINT)
assert _LINT_SPEC and _LINT_SPEC.loader
_lint = importlib.util.module_from_spec(_LINT_SPEC)
_LINT_SPEC.loader.exec_module(_lint)


# Closed items carry real bulk, as they do in a plan near its byte cap.
BULK = " ".join(["closed history detail"] * 12)

PLAN = f"""# Relief

## Brief

- Project: relief
- Mode: ship

## Tasks

### Live work
- [pending] Live row keeps its context ~aa11 | proof: read live -> kept
- [pending] Live work is done ~bb22 (DoD) | proof: read done -> done

## Deferred

- ~aa11 live deferral stays | waiting on owner | wake: owner answers
- ~zz01 archived row's deferral | its milestone left | wake: never again
  continuation of the archived deferral {BULK}
- unkeyed open deferral stays | no row to check | wake: Leo picks a channel

## Contradictions

- open unkeyed contradiction stays | provisional winner: measure
  its indented continuation must stay attached
- RESOLVED 2026-09-02T00:00:00Z: settled question | winner: smaller
  resolved continuation moves with its head {BULK}

## Progress

- 2026-09-01T00:00:00Z ~zz01 PROOF read old -> pass
  multi-line receipt continuation {BULK}
- 2026-09-01T00:00:01Z ~aa11 STRUCT live row note stays
- 2026-09-01T00:00:02Z ~zz02 ~aa11 mixed note stays because one row is live
- 2026-09-01T00:00:03Z LESSON ~zz01 lessons never move
- 2026-09-01T00:00:04Z STRUCT unkeyed history stays
- 2026-09-01T00:00:05Z DECISION ~zz03 keep -> decisions never move
- 2026-09-01T00:00:06Z ~zz04 carries its own | wake: a wake line never moves
"""

MOVED = (
    "- ~zz01 archived row's deferral | its milestone left | wake: never again\n"
    f"  continuation of the archived deferral {BULK}\n",
    "- RESOLVED 2026-09-02T00:00:00Z: settled question | winner: smaller\n"
    f"  resolved continuation moves with its head {BULK}\n",
    "- 2026-09-01T00:00:00Z ~zz01 PROOF read old -> pass\n"
    f"  multi-line receipt continuation {BULK}\n",
)

STAYS = (
    "- ~aa11 live deferral stays | waiting on owner | wake: owner answers\n",
    "- unkeyed open deferral stays | no row to check | wake: Leo picks a channel\n",
    "- open unkeyed contradiction stays | provisional winner: measure\n"
    "  its indented continuation must stay attached\n",
    "- 2026-09-01T00:00:01Z ~aa11 STRUCT live row note stays\n",
    "- 2026-09-01T00:00:02Z ~zz02 ~aa11 mixed note stays because one row is live\n",
    "- 2026-09-01T00:00:03Z LESSON ~zz01 lessons never move\n",
    "- 2026-09-01T00:00:04Z STRUCT unkeyed history stays\n",
    "- 2026-09-01T00:00:05Z DECISION ~zz03 keep -> decisions never move\n",
    "- 2026-09-01T00:00:06Z ~zz04 carries its own | wake: a wake line never moves\n",
)

FLAG = "--relocate-closed"


def section(text: str, name: str) -> str:
    _, _, rest = text.partition(f"\n## {name}\n")
    return rest.split("\n## ", 1)[0]


def blocking(text: str) -> collections.Counter:
    return collections.Counter(
        f["check"] for f in _lint.lint_plan(text) if f["severity"] == "blocking"
    )


class RelocateClosedPlanText(unittest.TestCase):
    def local_entity(self, root: Path) -> tuple[Path, dict[str, str]]:
        home = root / "home"
        entity = home / ".shadow" / "plans" / "relief"
        entity.mkdir(parents=True)
        install_plan_tree(entity, PLAN.encode("utf-8"))
        return entity, {"HOME": str(home)}

    def live(self, entity: Path) -> str:
        return lifecycle._board.open_plan(entity / "PLAN.md").materialize().decode("utf-8")

    def test_only_closed_whole_items_move_and_each_section_gets_one_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            entity, env = self.local_entity(Path(dirname).resolve())
            result, preview = run(entity, FLAG, extra_env=env)
            self.assertEqual(result.returncode, 0, preview)
            self.assertEqual(preview["action"], "would_relocate_closed")
            self.assertEqual(
                preview["relocated"], {"Deferred": 1, "Contradictions": 1, "Progress": 1}
            )
            self.assertEqual(self.live(entity), PLAN, "a dry run never writes")

            applied, report, _ = apply_with_cas(
                entity, FLAG, cas=preview["cas"], extra_env=env
            )
            self.assertEqual(applied.returncode, 0, report)
            self.assertEqual(report["action"], "relocated_closed")
            live = self.live(entity)
            archive = Path(report["archive"]).read_text(encoding="utf-8")

            for item in MOVED:
                self.assertNotIn(item.splitlines()[1], live)
                self.assertIn(item, archive, "a moved item keeps its continuation lines")
            for item in STAYS:
                self.assertIn(item, live, "open or protected text stays whole in place")
                self.assertNotIn(item, archive)

            link = f"](docs/plan-archive/{Path(report['archive']).name})"
            for name in ("Deferred", "Contradictions", "Progress"):
                self.assertEqual(section(live, name).count(link), 1, name)
            deferred_pointer = next(
                line for line in section(live, "Deferred").splitlines() if link in line
            )
            self.assertRegex(deferred_pointer, r"\| wake: \S")
            self.assertEqual(section(live, "Tasks"), section(PLAN, "Tasks"))

    def test_relocation_opens_no_contradiction_and_adds_no_blocking_lint(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            entity, env = self.local_entity(Path(dirname).resolve())
            applied, report, _ = apply_with_cas(entity, FLAG, extra_env=env)
            self.assertEqual(applied.returncode, 0, report)
            live = self.live(entity)
            amp = lifecycle.amp_module()
            self.assertEqual(
                amp._parse(live)["contradictions"], amp._parse(PLAN)["contradictions"]
            )
            self.assertEqual(blocking(live), collections.Counter())
            self.assertLess(
                report["budget"]["after"]["bytes"], report["budget"]["before"]["bytes"]
            )

    def test_a_stale_cas_refuses_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            entity, env = self.local_entity(Path(dirname).resolve())
            applied, report, _ = apply_with_cas(entity, FLAG, cas="0" * 64, extra_env=env)
            self.assertNotEqual(applied.returncode, 0, report)
            self.assertEqual(report["action"], "refused")
            self.assertEqual(self.live(entity), PLAN)
            self.assertFalse((entity / "docs").exists())

    def test_nothing_closed_left_refuses_and_pointers_never_move_again(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            entity, env = self.local_entity(Path(dirname).resolve())
            applied, report, _ = apply_with_cas(entity, FLAG, extra_env=env)
            self.assertEqual(applied.returncode, 0, report)
            after = self.live(entity)
            again, repeat = run(entity, FLAG, extra_env=env)
            self.assertNotEqual(again.returncode, 0, repeat)
            self.assertIn("no closed plan text", repeat["error"])
            self.assertEqual(self.live(entity), after)

    def test_a_git_backed_plan_commits_plan_and_archive_together(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            repo = make_repo(Path(dirname).resolve(), PLAN)
            applied, report, _ = apply_with_cas(repo, FLAG)
            self.assertEqual(applied.returncode, 0, report)
            self.assertEqual(git(repo, "status", "--porcelain"), "")
            self.assertIn(
                f"docs/plan-archive/{Path(report['archive']).name}",
                git(repo, "show", "--name-only", "--format=", "HEAD"),
            )


if __name__ == "__main__":
    unittest.main()
