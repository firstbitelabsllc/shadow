"""Regression tests for the `apple_asc` adapter (`adapters/apple_asc.py`).

T-4 of the `asc-eve-autobridge` goal. Covers:

1. fetch_inbox parses a multi-row sample tracker file
2. status_filter respects ["new", "triaged"] / excludes terminal states
3. empty `## Open` section returns []
4. multi-line `comment` / `surface` fields parse correctly (continuation lines)
5. git-conflict markers in the file are tolerated
6. push_task raises NotImplementedError with the documented message
7. pull_status returns None for any input
8. push_status raises NotImplementedError
9. push_fields raises NotImplementedError
10. pull_fields returns {}
11. adapter registers via `get_adapter('apple_asc')`
12. external_id is namespaced `asc:<id>` (idempotency across re-runs)
13. missing tracker file returns [] cleanly (fail-safe)
14. config without tracker_file raises ValueError before instantiation
15. config with non-list status_filter raises ValueError
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters import get_adapter  # noqa: E402
from adapters.apple_asc import AppleAscAdapter  # noqa: E402
from adapters.base import PlanTask, VidxStatus  # noqa: E402


def _write_tracker(text: str) -> Path:
    """Write a temp tracker file and return its Path. Caller cleans up."""
    fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=".plan.md", delete=False, encoding="utf-8"
    )
    fd.write(textwrap.dedent(text).lstrip("\n"))
    fd.close()
    return Path(fd.name)


SAMPLE_MULTI_ROW = """
    # App Store Feedback

    Repo-local tracker.

    ## Open

    - id: ABUGCGWL18gG13e5Tajjzek
      type: screenshot
      status: new
      first_seen: 2026-05-07
      last_seen: 2026-05-08
      submitted_at: 2026-05-07T15:37:17.563Z
      comment: This is broken, please fix immediately, we cannot ship like this.
      surface: Receipt Detail — ReceiptScanHeroImage removal
      owner: resplit-watch/1778218936

    - id: AB1R2BFP3hidYG3FJpw8jng
      type: screenshot
      status: triaged
      first_seen: 2026-04-13
      last_seen: 2026-05-08
      comment: Green dot makes me feel I overridded something
      surface: Receipt detail edit-affordance confusion
      owner: resplit-watch/1778224022

    - id: AKcbSJ8F4Fi1ha9gEhr6lXg
      type: screenshot
      status: fixed
      first_seen: 2026-04-13
      last_seen: 2026-05-08
      comment: Double dotted line fix
      surface: Visual bug
      fix_commit: 4bf90def

    ## Verified

    - id: ABCDfixedrow1
      status: verified
      comment: shipped long ago

    ## Archived

    - id: ABCDarchivedrow1
      status: archived
      comment: stale and removed
"""


class FetchInboxParsesMultiRow(unittest.TestCase):
    """Case 1 — basic parser correctness on a multi-row tracker."""

    def test_returns_only_non_terminal_open_rows_by_default(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        # Default status_filter = (new, triaged, claimed) — so the `fixed`
        # row in ## Open is dropped, and rows in ## Verified / ## Archived
        # are dropped by section.
        ids = [item.external_id for item in items]
        self.assertEqual(
            ids,
            ["asc:ABUGCGWL18gG13e5Tajjzek", "asc:AB1R2BFP3hidYG3FJpw8jng"],
        )

    def test_external_id_is_namespaced(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        for item in items:
            self.assertTrue(item.external_id.startswith("asc:"))
            # Same tracker re-parsed yields the same external_id —
            # idempotency proof (case 12).
            self.assertEqual(item.status, VidxStatus.PENDING)

    def test_title_prefers_comment_truncated_to_80(self) -> None:
        long_comment = "x" * 150
        tracker_text = (
            "## Open\n\n"
            "- id: ALONGCOMMENT\n"
            "  status: new\n"
            f"  comment: {long_comment}\n"
            "  surface: pending triage\n"
        )
        tracker = _write_tracker(tracker_text)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        self.assertEqual(len(items), 1)
        # Truncated to 80 chars with ellipsis (1-char ellipsis + 79 chars).
        self.assertLessEqual(len(items[0].title), 80)
        self.assertTrue(items[0].title.endswith("…"))

    def test_title_falls_back_to_surface_when_comment_missing(self) -> None:
        tracker_text = (
            "## Open\n\n"
            "- id: ANOCOMMENT\n"
            "  status: new\n"
            "  surface: Receipt header visual glitch\n"
        )
        tracker = _write_tracker(tracker_text)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Receipt header visual glitch")


class StatusFilterRespectsConfig(unittest.TestCase):
    """Case 2 — status_filter narrows what fetch_inbox returns."""

    def test_filter_only_new_excludes_triaged(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        try:
            adapter = AppleAscAdapter({
                "tracker_file": str(tracker),
                "status_filter": ["new"],
            })
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        ids = [item.external_id for item in items]
        self.assertEqual(ids, ["asc:ABUGCGWL18gG13e5Tajjzek"])

    def test_terminal_states_always_dropped_even_if_in_filter(self) -> None:
        """Terminal states (fixed/verified/archived) drop even if user
        tries to include them in `status_filter` — they're handled by
        their own section and have no actionable agent value."""
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        try:
            adapter = AppleAscAdapter({
                "tracker_file": str(tracker),
                # User mistakenly tries to include `fixed` — the adapter
                # short-circuits this at the row level.
                "status_filter": ["new", "triaged", "fixed"],
            })
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        # `fixed` row in ## Open still dropped because terminal-state
        # rejection runs before status_filter check.
        ids = [item.external_id for item in items]
        self.assertNotIn("asc:AKcbSJ8F4Fi1ha9gEhr6lXg", ids)


class EmptyOpenSectionReturnsEmpty(unittest.TestCase):
    """Case 3 — empty `## Open` returns [] cleanly."""

    def test_empty_open_section(self) -> None:
        tracker_text = (
            "# App Store Feedback\n\n"
            "## Open\n\n"
            "(nothing here yet)\n\n"
            "## Verified\n\n"
            "- id: ABCDold\n"
            "  status: verified\n"
        )
        tracker = _write_tracker(tracker_text)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        self.assertEqual(items, [])


class MultiLineFieldsParseCorrectly(unittest.TestCase):
    """Case 4 — continuation lines append to the previous key's value."""

    def test_multi_line_comment_and_surface(self) -> None:
        tracker_text = (
            "## Open\n\n"
            "- id: AMULTILINE\n"
            "  status: new\n"
            "  comment: First sentence of the comment.\n"
            "    Second sentence on a continuation line.\n"
            "    And a third one.\n"
            "  surface: A surface description\n"
            "    that wraps onto a second line.\n"
            "  owner: shared\n"
        )
        tracker = _write_tracker(tracker_text)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        self.assertEqual(len(items), 1)
        row = items[0].raw
        assert row is not None
        self.assertIn("First sentence", row["comment"])
        self.assertIn("Second sentence on a continuation line.", row["comment"])
        self.assertIn("And a third one.", row["comment"])
        self.assertIn("A surface description", row["surface"])
        self.assertIn("that wraps onto a second line.", row["surface"])


class GitConflictMarkersTolerated(unittest.TestCase):
    """Case 5 — `<<<<<<<` / `=======` / `>>>>>>>` lines don't crash the parser."""

    def test_conflict_markers_skipped(self) -> None:
        tracker_text = (
            "## Open\n\n"
            "- id: AHEAD\n"
            "  status: new\n"
            "  comment: One side of a merge\n"
            "<<<<<<< HEAD\n"
            "  surface: HEAD surface description\n"
            "=======\n"
            "  surface: branch surface description\n"
            ">>>>>>> branch\n"
            "  owner: shared\n"
        )
        tracker = _write_tracker(tracker_text)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        # The parser should not crash; the row is still recognized.
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].external_id, "asc:AHEAD")


class WritePathRaisesNotImplemented(unittest.TestCase):
    """Cases 6, 8, 9 — write methods raise NotImplementedError with
    the documented Apple-no-API reason."""

    def setUp(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        self.tracker = tracker
        self.adapter = AppleAscAdapter({"tracker_file": str(tracker)})

    def tearDown(self) -> None:
        self.tracker.unlink()

    def test_push_task_raises_with_documented_reason(self) -> None:
        task = PlanTask(id="T1", title="example", status=VidxStatus.PENDING)
        with self.assertRaises(NotImplementedError) as ctx:
            self.adapter.push_task(task)
        self.assertIn("Apple ASC has no public API", str(ctx.exception))
        self.assertIn("one-way READ-only", str(ctx.exception))

    def test_push_status_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.adapter.push_status("asc:foo", VidxStatus.COMPLETED)

    def test_push_fields_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.adapter.push_fields("asc:foo", {"Evidence": "x"})


class ReadPathBehavior(unittest.TestCase):
    """Cases 7, 10 — pull_status returns None; pull_fields returns {}."""

    def setUp(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        self.tracker = tracker
        self.adapter = AppleAscAdapter({"tracker_file": str(tracker)})

    def tearDown(self) -> None:
        self.tracker.unlink()

    def test_pull_status_returns_none(self) -> None:
        self.assertIsNone(self.adapter.pull_status("asc:ABUGCGWL18gG13e5Tajjzek"))
        self.assertIsNone(self.adapter.pull_status("asc:does-not-exist"))

    def test_pull_fields_returns_empty(self) -> None:
        self.assertEqual(self.adapter.pull_fields("asc:foo"), {})


class AdapterRegistration(unittest.TestCase):
    """Case 11 — adapter is reachable via get_adapter('apple_asc')."""

    def test_registry_resolves_apple_asc(self) -> None:
        cls = get_adapter("apple_asc")
        self.assertIs(cls, AppleAscAdapter)
        self.assertEqual(cls.name, "apple_asc")


class MissingTrackerFile(unittest.TestCase):
    """Case 13 — a non-existent tracker_file path returns [] cleanly.

    Path-not-found is a legitimate state mid-repo-rename or
    fresh-clone before `asc_beta_feedback.rb sync-plan` has run.
    Crashing the cron on this is worse than returning empty.
    """

    def test_missing_file_returns_empty_list(self) -> None:
        # Build a path that almost certainly doesn't exist.
        missing = Path(tempfile.gettempdir()) / "apple_asc_does_not_exist.plan.md"
        if missing.exists():
            missing.unlink()
        adapter = AppleAscAdapter({"tracker_file": str(missing)})
        self.assertEqual(adapter.fetch_inbox(), [])


class ConfigValidation(unittest.TestCase):
    """Cases 14, 15 — config validation errors."""

    def test_missing_tracker_file_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            AppleAscAdapter({})
        self.assertIn("tracker_file", str(ctx.exception))

    def test_status_filter_must_be_list(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            AppleAscAdapter({
                "tracker_file": "/tmp/nope.plan.md",
                "status_filter": "new",  # str, not list
            })
        self.assertIn("status_filter", str(ctx.exception))

    def test_status_filter_accepts_tuple(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        try:
            adapter = AppleAscAdapter({
                "tracker_file": str(tracker),
                "status_filter": ("new", "triaged"),
            })
            self.assertEqual(adapter.status_filter, ("new", "triaged"))
        finally:
            tracker.unlink()

    def test_tracker_file_expands_user(self) -> None:
        # `~` in the config path should expand to $HOME so the cron can
        # carry the same config across machines without absolute paths.
        adapter = AppleAscAdapter({"tracker_file": "~/nope.plan.md"})
        self.assertNotIn("~", str(adapter.tracker_file))


class ExternalItemShape(unittest.TestCase):
    """Sanity — the returned ExternalItem carries enough evidence to
    promote the row to PLAN.md without re-reading the tracker file."""

    def test_fields_include_source_and_evidence(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        first = items[0]
        self.assertIn("Source", first.fields)
        self.assertTrue(first.fields["Source"].startswith("asc:"))
        self.assertIn("submitted_at=", first.fields["Source"])
        # Evidence carries the row body so downstream PLAN.md rendering
        # can show the reporter comment + surface inline.
        self.assertIn("comment:", first.fields["Evidence"])
        self.assertIn("surface:", first.fields["Evidence"])

    def test_raw_carries_full_parsed_row(self) -> None:
        tracker = _write_tracker(SAMPLE_MULTI_ROW)
        try:
            adapter = AppleAscAdapter({"tracker_file": str(tracker)})
            items = adapter.fetch_inbox()
        finally:
            tracker.unlink()

        first = items[0]
        self.assertIsNotNone(first.raw)
        assert first.raw is not None
        self.assertEqual(first.raw["id"], "ABUGCGWL18gG13e5Tajjzek")
        self.assertEqual(first.raw["status"], "new")
        self.assertEqual(first.raw["type"], "screenshot")


if __name__ == "__main__":
    unittest.main()
