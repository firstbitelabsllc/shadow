#!/usr/bin/env python3
"""Bounded migration from project plans into this computer's pointer board."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shadow_root_board as board


THROWN = re.compile(
    r"^- (?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) "
    r"THROWN (?P<row>~[0-9a-z]{4})\b(?P<tail>.*)$",
    flags=re.M,
)
OWNER = re.compile(r"\| by: (?P<owner>[^|]+)")


@dataclass(frozen=True)
class SuppressionReceipt:
    """The complete public shape of one inspectable discovery suppression."""

    path: str
    shadowed_by: str | None
    reason: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "path": self.path,
            "shadowed_by": self.shadowed_by,
            "reason": self.reason,
        }


def volatile_roots() -> tuple[Path, ...]:
    """Directories whose contents are deleted without asking.

    `SHADOW_VOLATILE_ROOTS` (colon-separated) overrides the default set, so a
    test can name a swept root without depending on where this platform's
    `tempfile` happens to put fixtures.
    """
    override = os.environ.get("SHADOW_VOLATILE_ROOTS")
    if override is not None:
        return tuple(
            Path(part).expanduser().resolve()
            for part in override.split(":")
            if part.strip()
        )
    # The shared, world-writable temp root, which is what this host's cleanup
    # sweeps and the OS reap on an idle timer, and where the lane checkouts this
    # rule exists for sit. On Linux it is also `tempfile`'s default, so every
    # fixture lands inside it; requiring a durable, import-grade repair target,
    # not a narrower root set, is what keeps an entirely ephemeral tree inert.
    roots = ["/tmp", "/private/tmp"]
    resolved: list[Path] = []
    for raw in roots:
        candidate = Path(raw)
        if not candidate.is_dir():
            continue
        # `/tmp` is a symlink to `/private/tmp` on macOS, so resolve then
        # deduplicate rather than reporting the same root twice.
        real = candidate.resolve()
        if real not in resolved:
            resolved.append(real)
    return tuple(resolved)


def volatile_locator(pointer: Path) -> bool:
    """Whether this registered plan sits on storage that gets swept."""
    try:
        resolved = Path(os.path.abspath(pointer)).resolve()
    except OSError:
        return False
    for root in volatile_roots():
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        return True
    return False


def portfolio_root(fallback: Path) -> Path:
    configured = os.environ.get("SHADOW_PORTFOLIO_ROOT") or os.environ.get("SHADOW_DEV_ROOT")
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if not candidate.is_dir():
            raise board.BoardError("SHADOW_PORTFOLIO_ROOT is not a directory")
        return candidate
    default = Path.home() / "Development"
    return default.resolve() if default.is_dir() else fallback.resolve()


def _priority(plan: dict) -> int:
    raw = plan["brief"].get("Priority", "3")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise board.BoardError("project Priority must be 1-5 for board import") from exc
    if value not in range(1, 6):
        raise board.BoardError("project Priority must be 1-5 for board import")
    return value


def _assert_authority_grade(
    content: bytes,
    *,
    amp: ModuleType,
    declared_globs,
    operator_brief,
) -> None:
    """Raise unless this frozen plan text is fit to hold board authority.

    One definition, two readers: the trust check below, and the check a copy
    must pass before authority is repaired ONTO it. A repair target held to a
    weaker standard than the locator it replaces is how a healthy pointer ends
    up replaced by a plan the import then refuses.
    """
    if len(content) > board.MAX_PLAN_BYTES:
        raise board.BoardError("registered plan exceeds the bounded size limit")
    text = content.decode("utf-8")
    parsed = amp._parse(text)
    if not parsed["brief"].get("Project") or not parsed["brief"].get("Mode"):
        raise board.BoardError("registered plan lacks current board fields")
    if amp.unclean_note(parsed):
        raise board.BoardError("registered plan is not grammar-clean")
    _priority(parsed)
    amp._candidate_ids(parsed)
    declaration = operator_brief(text).get("plans", "")
    if any(
        not candidate
        or candidate.startswith("/")
        or ".." in Path(candidate).parts
        for candidate in (part.strip() for part in declaration.split(","))
        if declaration
    ):
        raise board.BoardError("registered plan declaration is unsafe")
    declared_globs(text)


def _registered_state(
    amp: ModuleType,
    *,
    home: Path | None,
    archive_veto_text,
    declared_globs,
    operator_brief,
    browser_error: type[Exception],
) -> tuple[
    dict[str, Path],
    dict[str, dict],
    dict[str, tuple[Path, str]],
    dict[str, tuple[Path, str]],
]:
    """Unique healthy, retired, repairable, and swept registered locators.

    The last group is a SUBSET of the healthy one, not an alternative to it: a
    locator on volatile storage is still trusted, and only stops being the
    authority once a durable replacement good enough to hold it is in hand.
    """
    trusted: dict[str, Path] = {}
    retired: dict[str, dict] = {}
    repairable: dict[str, tuple[Path, str]] = {}
    volatile: dict[str, tuple[Path, str]] = {}
    for identity, pointers in board.registered_locator_index(home=home).items():
        frozen = {
            pointer: board.plan_state_snapshot(pointer)
            for pointer in sorted(pointers, key=str)
        }
        # Demotion is identity-wide even when two old board records have
        # converged onto one Git identity. Multiplicity disables canonical
        # substitution and repair, but it must not hide an exact registered
        # plan's own archive verdict.
        for pointer, (state_fingerprint, content) in frozen.items():
            if content is None:
                continue
            try:
                if board.entity_id(pointer) != identity:
                    continue
            except board.BoardError:
                continue
            head = content[:65_536].decode("utf-8", errors="ignore")
            if archive_veto_text(head):
                retired[identity] = {
                    "identity": identity,
                    "plan": str(pointer.resolve()),
                    "expected_state": state_fingerprint,
                    "registered_plan": str(pointer),
                }
                break
        if identity in retired:
            if len(pointers) == 1:
                trusted[identity] = pointers[0].resolve()
            continue
        if len(pointers) != 1:
            continue
        pointer = pointers[0]
        state_fingerprint, content = frozen[pointer]
        if state_fingerprint == "unavailable" or content is None:
            repairable[identity] = (pointer, state_fingerprint)
            continue
        try:
            if board.entity_id(pointer) != identity:
                continue
            _assert_authority_grade(
                content,
                amp=amp,
                declared_globs=declared_globs,
                operator_brief=operator_brief,
            )
        except (
            board.BoardError,
            browser_error,
            KeyError,
            OSError,
            TypeError,
            UnicodeError,
            ValueError,
        ):
            repairable[identity] = (pointer, state_fingerprint)
            continue
        if volatile_locator(pointer):
            # A readable plan on volatile storage is a bad place to keep board
            # authority: the operating system, and this machine's own cleanup
            # sweeps, delete temp roots on an idle timer. But it is STILL the
            # authority here, because demoting it before a replacement is in
            # hand is what breaks the two cases this rule must not break: a
            # broken same-identity sibling would refuse the whole import, and a
            # second copy under the same temp root would just take the pointer
            # from one swept path to another. Reconcile repairs it only onto a
            # durable, import-grade copy; with none, nothing changes and the
            # temp copy is used exactly as before.
            volatile[identity] = (pointer, state_fingerprint)
        trusted[identity] = pointer.resolve()
    return trusted, retired, repairable, volatile


def reconcile_portfolio(
    root: Path,
    amp: ModuleType,
    *,
    home: Path | None = None,
) -> dict:
    """Import exactly the plans returned by shipped bounded discovery."""
    from browser.server import (
        BrowserError,
        _archive_veto_text,
        declared_plan_globs,
        discover_plans,
        is_live,
        operator_brief,
        read_plan,
    )

    seeds: list[dict] = []
    historical: list[dict] = []
    registered, registered_retired, repairable, volatile = _registered_state(
        amp,
        home=home,
        archive_veto_text=_archive_veto_text,
        declared_globs=declared_plan_globs,
        operator_brief=operator_brief,
        browser_error=BrowserError,
    )
    retired: dict[str, dict] = {}
    observed_identities: set[str] = set()
    try:
        records = discover_plans(
            root,
            fail_on_skipped=True,
            registered_plans=registered,
            repairable_plans={
                identity: pointer
                for identity, (pointer, _) in repairable.items()
            },
            retired_registered=set(registered_retired),
            capture_tokens=True,
        )
    except BrowserError as exc:
        raise board.BoardError(f"portfolio import refused: {exc}") from exc

    def durable_authority_grade(candidate: Path) -> bool:
        """Whether authority may be repaired from swept storage onto this copy.

        Both halves are load-bearing. Durable, or the repair is a move from one
        path the sweeps reap to another. Import-grade, or a healthy registered
        locator is given up for a plan the very next step refuses, which turns
        a working board into `showing the last-good computer board`.
        """
        if volatile_locator(candidate):
            return False
        _, content = board.plan_state_snapshot(candidate)
        if content is None:
            return False
        try:
            _assert_authority_grade(
                content,
                amp=amp,
                declared_globs=declared_plan_globs,
                operator_brief=operator_brief,
            )
        except (
            board.BoardError,
            BrowserError,
            KeyError,
            OSError,
            TypeError,
            UnicodeError,
            ValueError,
        ):
            return False
        return True

    for record in records:
        relative = record.get("path")
        if not relative:
            continue
        plan_path = Path(os.path.abspath(root / relative))
        identity = record.get("_logical_entity") or board.entity_id(plan_path)
        observed_identities.add(identity)
        if not is_live(record):
            registered_retirement = registered_retired.get(identity)
            if registered_retirement is not None and record.get("_retired_plan") is None:
                retirement = dict(registered_retirement)
            else:
                retirement = {
                    "identity": identity,
                    "plan": record.get("_retired_plan"),
                    "expected_state": record.get("_retired_state"),
                    # Every copy the supersession comparison read, not just the
                    # demotion it quotes: a sibling that turns live between
                    # discovery and the transaction must void this retirement.
                    "witnesses": record.get("_retired_witnesses") or [],
                }
                if (
                    registered_retirement is not None
                    and registered_retirement.get("plan") == retirement["plan"]
                ):
                    retirement["registered_plan"] = registered_retirement["registered_plan"]
            retired[identity] = retirement
            continue
        source_path = plan_path
        repair: tuple[Path, str] | None = None
        if record.get("_registered_pointer"):
            source_path = registered.get(record.get("_logical_entity"))
            if source_path is None:
                raise board.BoardError(
                    f"{relative}: registered board locator changed during import"
                )
            swept = volatile.get(record.get("_logical_entity"))
            # The elected copy, and only it: authority follows the copy the
            # portfolio would render, never some other sibling that happens to
            # be durable.
            if swept is not None and durable_authority_grade(plan_path):
                source_path = plan_path
                repair = swept
        try:
            text = read_plan(source_path)
        except (BrowserError, OSError, UnicodeError) as exc:
            raise board.BoardError(f"{relative} cannot be read during board import") from exc
        plan = amp._parse(text)
        # Legacy outcome plans remain visible during migration but do not have
        # project rows for the root board to point at. Status renders them from
        # the same bounded discovery result until they adopt the current Brief.
        if not plan["brief"].get("Project") or not plan["brief"].get("Mode"):
            continue
        unclean = amp.unclean_note(plan)
        if unclean:
            raise board.BoardError(f"{relative} cannot enter the computer board: {unclean}")
        try:
            priority = _priority(plan)
        except board.BoardError as exc:
            raise board.BoardError(f"{relative}: {exc}") from exc
        content = text.encode("utf-8")
        seed = {
            "identity": identity,
            "plan": str(source_path),
            "project": plan["brief"]["Project"],
            "priority": priority,
            "candidates": amp._candidate_ids(plan),
            "rows": [
                row["id"]
                for milestone in plan["milestones"]
                for row in milestone["rows"]
            ],
            "expected_size": len(content),
            "expected_sha256": hashlib.sha256(content).hexdigest(),
            # A live result is still a comparison verdict: every same-identity
            # copy read while deciding that no newer demotion stands must stay
            # frozen until the board transaction commits.
            "witnesses": record.get("_live_witnesses") or [],
        }
        if repair is not None:
            repair_from, repair_state = repair
            seed["repair_from"] = str(repair_from)
            seed["repair_state"] = repair_state
        elif record.get("_registered_pointer"):
            seed["registered_plan"] = str(source_path)
        elif identity in registered_retired:
            retirement = registered_retired[identity]
            seed["repair_from"] = retirement["registered_plan"]
            seed["repair_state"] = retirement["expected_state"]
        elif identity in repairable:
            repair_from, repair_state = repairable[identity]
            seed["repair_from"] = str(repair_from)
            seed["repair_state"] = repair_state
        seeds.append(seed)

        latest: dict[str, tuple[str, str]] = {}
        for match in THROWN.finditer(text):
            owner = OWNER.search(match.group("tail"))
            latest[match.group("row")] = (
                match.group("stamp"),
                owner.group("owner").strip() if owner else "another seat",
            )
        live = {
            row["id"]
            for milestone in plan["milestones"]
            for row in milestone["rows"]
            if row["state"] == "in_progress"
        }
        historical.extend(
            {
                "plan": str(source_path),
                "row": row,
                "owner": owner,
                "claimed_at": stamp,
            }
            for row, (stamp, owner) in latest.items()
            if row in live
        )
    for identity, retirement in registered_retired.items():
        if identity not in observed_identities:
            retired[identity] = retirement
    return board.reconcile(
        seeds,
        historical,
        retired_entities=sorted(retired),
        retired_sources=list(retired.values()),
        home=home,
    )


def suppression_receipts(
    root: Path,
    amp: ModuleType,
    *,
    home: Path | None = None,
) -> list[SuppressionReceipt]:
    """Bounded, public reasons discovery withheld a plan from authority."""
    from browser.server import (
        BrowserError,
        _archive_veto_text,
        declared_plan_globs,
        discover_plans,
        operator_brief,
    )

    registered, registered_retired, repairable, _ = _registered_state(
        amp,
        home=home,
        archive_veto_text=_archive_veto_text,
        declared_globs=declared_plan_globs,
        operator_brief=operator_brief,
        browser_error=BrowserError,
    )

    try:
        records = discover_plans(
            root,
            include_shadowed=True,
            fail_on_skipped=True,
            registered_plans=registered,
            repairable_plans={
                identity: pointer
                for identity, (pointer, _) in repairable.items()
            },
            retired_registered=set(registered_retired),
            capture_tokens=True,
        )
    except BrowserError as exc:
        raise board.BoardError(f"portfolio inspection refused: {exc}") from exc
    receipts: list[SuppressionReceipt] = []
    archived_identities: set[str] = set()
    observed_identities: set[str] = set()
    for record in records:
        identity = record.get("_logical_entity")
        if identity:
            observed_identities.add(identity)
        if record.get("shadowed_by"):
            receipts.append(SuppressionReceipt(
                path=board.public_copy_locator(identity, record["path"]),
                shadowed_by=board.public_entity_locator(identity),
                reason="same logical entity as the elected portfolio checkout",
            ))
        elif record.get("archived"):
            if identity:
                archived_identities.add(identity)
            receipts.append(SuppressionReceipt(
                path=board.public_copy_locator(identity, record["path"]),
                shadowed_by=None,
                reason="demoted by its own non-executable archive shell banner",
            ))
        elif record.get("_registered_pointer"):
            if identity not in registered:
                continue
            receipts.append(SuppressionReceipt(
                path=board.public_copy_locator(identity, record["path"]),
                shadowed_by=board.public_entity_locator(identity),
                reason=(
                    "historical archive explicitly superseded by the current "
                    "committed plan"
                    if record.get("_archive_superseded")
                    else "same logical entity already has one healthy registered "
                    "computer-board locator"
                ),
            ))
    for identity in sorted(
        set(registered_retired).difference(archived_identities, observed_identities)
    ):
        receipts.append(SuppressionReceipt(
            path=board.public_entity_locator(identity),
            shadowed_by=None,
            reason="demoted by its own non-executable archive shell banner",
        ))
    return receipts
