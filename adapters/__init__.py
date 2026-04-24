"""vidux inbox-source adapter plugins.

Adapters implement AdapterBase from `base.py` and self-register via
the @register decorator. Concrete adapters live in this package
(gh_projects.py, linear.py, asana.py, jira.py, trello.py). Importing
this package imports every registered adapter so the registry is
populated for the sync script.
"""

from adapters.base import (
    AdapterBase,
    ExternalItem,
    PlanTask,
    VidxStatus,
    get_adapter,
    register,
    registered_adapters,
)

# Import side effects register each adapter into the registry.
from adapters import gh_projects  # noqa: F401

__all__ = [
    "AdapterBase",
    "ExternalItem",
    "PlanTask",
    "VidxStatus",
    "get_adapter",
    "register",
    "registered_adapters",
]
