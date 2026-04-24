"""Adapter base contract for vidux inbox-source plugins.

Adapters translate between vidux PLAN.md tasks and external kanban boards
(GitHub Projects, Linear, Asana, Jira, Trello). Core vidux never imports
from specific adapters; the sync script dispatches via the registry.

Pure stdlib. No third-party deps.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar


class VidxStatus(str, Enum):
    """vidux 5-state FSM — `in_review` added by vidux-kanban-ext.

    FSM:  pending -> in_progress -> in_review -> completed
                       |               |
                       +-> blocked <---+   (orthogonal — a tag, not a column)
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class PlanTask:
    """A task parsed from a PLAN.md Tasks section.

    Adapters receive PlanTask on push; they never write PlanTask back —
    the sync script owns PLAN.md mutations.
    """

    id: str                    # "T4" or equivalent stable handle
    title: str                 # one-line summary (no status tag, no evidence)
    status: VidxStatus
    evidence: str | None = None           # raw text of [Evidence: ...]
    investigation: str | None = None      # raw text of [Investigation: ...]
    eta_hours: float | None = None        # parsed from [ETA: Xh]
    source: str | None = None             # "PLAN.md:L<a>-L<b>" when seeded
    external_id: str | None = None        # opaque adapter handle if already synced
    blocked: bool = False                 # orthogonal to status


@dataclass
class ExternalItem:
    """An item on an external board, normalized to vidux vocabulary.

    Adapters produce ExternalItem from fetch_inbox(). The sync script
    decides whether to promote it to INBOX.md (new) or reconcile with
    an existing PLAN.md task (known external_id).
    """

    external_id: str
    title: str
    status: VidxStatus
    fields: dict[str, Any] = field(default_factory=dict)   # Evidence / Investigation / ETA / Source
    blocked: bool = False
    raw: dict[str, Any] | None = None                      # adapter-specific blob for debugging


class AdapterBase(ABC):
    """Contract every inbox adapter implements.

    Subclasses MUST declare `name` (matches the config block `adapter`
    key) and `config_schema` (a JSON-Schema-shaped dict describing the
    adapter's config block). `validate_config` performs a shallow
    required-key check; deeper validation is the adapter's job in
    __init__.
    """

    name: ClassVar[str]
    config_schema: ClassVar[dict[str, Any]]

    def __init__(self, config: dict[str, Any]) -> None:
        self.validate_config(config)
        self.config = config

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> None:
        """Shallow required-key check against cls.config_schema.

        Raises ValueError listing every missing required key. Adapters
        override for deeper checks (enum values, path existence, etc.).
        """
        required = cls.config_schema.get("required", [])
        missing = [k for k in required if k not in config]
        if missing:
            raise ValueError(
                f"{cls.name} adapter config missing required keys: {missing}"
            )

    @abstractmethod
    def fetch_inbox(self) -> list[ExternalItem]:
        """Return every item on the external board.

        Humans promote new items from INBOX.md into PLAN.md; adapters
        never mutate PLAN.md directly.
        """

    @abstractmethod
    def push_task(self, task: PlanTask) -> str:
        """Create an external item from a PLAN.md task. Return opaque external_id."""

    @abstractmethod
    def pull_status(self, external_id: str) -> VidxStatus:
        """What vidux status is this item in right now?"""

    @abstractmethod
    def push_status(self, external_id: str, status: VidxStatus) -> None:
        """Move the item to the column corresponding to the vidux status."""

    @abstractmethod
    def pull_fields(self, external_id: str) -> dict[str, Any]:
        """Return custom-field values keyed by vidux tag name (Evidence, ETA, Source, ...)."""

    @abstractmethod
    def push_fields(self, external_id: str, fields: dict[str, Any]) -> None:
        """Write custom-field values."""


# --- Registry ----------------------------------------------------------------
#
# Adapters register themselves here at import time. The sync script
# resolves `config.adapter` -> class via this dict. Stub adapters
# (linear, asana, jira, trello) register too so `adapter: linear`
# fails loudly with NotImplementedError rather than silently no-op.

_REGISTRY: dict[str, type[AdapterBase]] = {}


def register(cls: type[AdapterBase]) -> type[AdapterBase]:
    """Decorator for adapter classes to self-register at import time."""
    if not hasattr(cls, "name") or not cls.name:
        raise ValueError(f"Adapter {cls.__name__} missing `name` ClassVar")
    if cls.name in _REGISTRY:
        raise ValueError(f"Adapter name collision: {cls.name} already registered")
    _REGISTRY[cls.name] = cls
    return cls


def get_adapter(name: str) -> type[AdapterBase]:
    """Look up a registered adapter class by name. Raises KeyError if unknown."""
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown adapter '{name}'. Registered: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[name]


def registered_adapters() -> list[str]:
    """Return sorted list of registered adapter names."""
    return sorted(_REGISTRY.keys())
