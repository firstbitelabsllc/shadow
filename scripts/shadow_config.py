"""Read Shadow's deliberately small, repo-local ``shadow.yaml`` format.

This is intentionally *not* a general YAML parser.  Shadow needs one tiny,
reviewable configuration surface, so unsupported YAML is refused with an exact
source line instead of being interpreted approximately.  In particular, this
module has no provider, host, credential, environment, or persistent state.
The schema/consumer layer decides which parsed keys are meaningful.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Final


ConfigValue = str | int | bool | None | list["ConfigValue"] | dict[str, "ConfigValue"]

# These are the behavior-equivalent defaults.  ``load_config`` always returns
# a fresh deep copy, so a caller can never turn a read into process state by
# mutating its result.
DEFAULT_CONFIG: Final[dict[str, ConfigValue]] = {
    "version": 1,
    "leads": {},
    "method": {
        "adversarial_lenses": [
            "assumptions",
            "correctness",
            "integration",
            "crash_recovery",
            "privacy",
            "stranger_install",
        ]
    },
    "buckets": {},
    "durability": {"claim_return_minutes": 480},
}

_KEY_RE: Final = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_INTEGER_RE: Final = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_FORBIDDEN_SCALAR_PREFIXES: Final = ("[", "{", "&", "*", "!", "|", ">", "@", "`")


class ConfigError(ValueError):
    """A configuration error with a deterministic file-and-line location."""

    def __init__(self, path: Path, line: int, detail: str) -> None:
        self.path = Path(path)
        self.line = line
        self.detail = detail
        super().__init__(f"{self.path}:{line}: {detail}")


class _Line:
    """One nonblank, non-comment source line after indentation validation."""

    def __init__(self, number: int, indent: int, content: str) -> None:
        self.number = number
        self.indent = indent
        self.content = content


def _source_lines(text: str, path: Path) -> list[_Line]:
    lines: list[_Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw:
            raise ConfigError(path, number, "tabs are not supported; use two-space indentation")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise ConfigError(path, number, "indentation must use multiples of two spaces")
        lines.append(_Line(number, indent, raw[indent:]))
    return lines


def _plain_scalar(raw: str, path: Path, line: int) -> ConfigValue:
    """Parse the deliberately narrow scalar subset, never guessing YAML."""
    # YAML comments begin with a whitespace-delimited ``#``.  A literal hash
    # belongs in a quoted string, which is explicit rather than ambiguous.
    if " #" in raw:
        raw = raw.split(" #", 1)[0].rstrip()
    if not raw:
        raise ConfigError(path, line, "a mapping or list value is required")
    if raw[0] in _FORBIDDEN_SCALAR_PREFIXES or raw.startswith(("---", "...")):
        raise ConfigError(path, line, "unsupported YAML scalar syntax")
    if ": " in raw or raw.endswith(":"):
        raise ConfigError(path, line, "unsupported YAML mapping syntax inside a scalar")
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(path, line, "malformed double-quoted scalar") from exc
        if not isinstance(value, str):
            raise ConfigError(path, line, "only string double-quoted scalars are supported")
        return value
    if raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            raise ConfigError(path, line, "malformed single-quoted scalar")
        return raw[1:-1].replace("''", "'")
    if raw.startswith(("'", '"')):
        raise ConfigError(path, line, "malformed quoted scalar")
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw in {"null", "~"}:
        return None
    if _INTEGER_RE.fullmatch(raw):
        return int(raw)
    # The subset does not implement floats, dates, anchors, tags, flow
    # collections, multiline values, or implicit coercions.  A plain string is
    # deliberately left a string so schema validation remains explicit.
    return raw


def _mapping_entry(source: _Line, path: Path) -> tuple[str, str]:
    if source.content.startswith("- ") or source.content == "-":
        raise ConfigError(path, source.number, "a list item is not allowed in a mapping")
    if ":" not in source.content:
        raise ConfigError(path, source.number, "expected 'key: value' or 'key:'")
    key, value = source.content.split(":", 1)
    if not _KEY_RE.fullmatch(key):
        raise ConfigError(path, source.number, "mapping keys must be unquoted letters, digits, '_' or '-'")
    if value and not value.startswith(" "):
        raise ConfigError(path, source.number, "a colon in a mapping must be followed by a space")
    return key, value.strip()


def _parse_block(
    lines: list[_Line],
    index: int,
    indent: int,
    path: Path,
) -> tuple[dict[str, ConfigValue] | list[ConfigValue], int]:
    if index >= len(lines):
        raise ConfigError(path, 1, "configuration is empty")
    first = lines[index]
    if first.indent != indent:
        raise ConfigError(path, first.number, f"expected indentation of {indent} spaces")
    is_list = first.content == "-" or first.content.startswith("- ")
    result: dict[str, ConfigValue] | list[ConfigValue] = [] if is_list else {}

    while index < len(lines):
        source = lines[index]
        if source.indent < indent:
            break
        if source.indent > indent:
            raise ConfigError(path, source.number, f"expected indentation of {indent} spaces")
        item_is_list = source.content == "-" or source.content.startswith("- ")
        if item_is_list != is_list:
            wanted = "list item" if is_list else "mapping entry"
            raise ConfigError(path, source.number, f"expected {wanted}")

        if is_list:
            assert isinstance(result, list)
            if source.content == "-":
                raise ConfigError(path, source.number, "nested mappings in list items are not supported")
            result.append(_plain_scalar(source.content[2:], path, source.number))
            index += 1
            continue

        assert isinstance(result, dict)
        key, value = _mapping_entry(source, path)
        if key in result:
            raise ConfigError(path, source.number, f"duplicate mapping key '{key}'")
        index += 1
        if value:
            result[key] = _plain_scalar(value, path, source.number)
            continue
        if index >= len(lines) or lines[index].indent <= indent:
            raise ConfigError(path, source.number, f"mapping key '{key}' requires an indented value")
        expected = indent + 2
        if lines[index].indent != expected:
            raise ConfigError(path, lines[index].number, f"expected indentation of {expected} spaces")
        child, index = _parse_block(lines, index, expected, path)
        result[key] = child
    return result, index


def parse_config(text: str, path: Path | str = Path("shadow.yaml")) -> dict[str, ConfigValue]:
    """Parse the supported YAML subset into JSON-serializable Python values.

    A config document must be one root mapping.  Every unsupported feature
    fails closed with the exact source line, rather than producing an inferred
    binding that could redirect a workflow.
    """
    source_path = Path(path)
    lines = _source_lines(text, source_path)
    if not lines:
        raise ConfigError(source_path, 1, "configuration is empty")
    parsed, index = _parse_block(lines, 0, 0, source_path)
    if index != len(lines):  # Defensive: _parse_block currently consumes root.
        raise ConfigError(source_path, lines[index].number, "unexpected trailing content")
    if not isinstance(parsed, dict):
        raise ConfigError(source_path, lines[0].number, "configuration root must be a mapping")
    return parsed


def _repo_root(start: Path) -> Path | None:
    """Return the nearest filesystem Git root without invoking Git."""
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def find_config(start: Path) -> Path | None:
    """Find exactly the current repository's root ``shadow.yaml``, if any."""
    root = _repo_root(Path(start))
    if root is None:
        candidate = Path(start).resolve()
        if candidate.is_file():
            candidate = candidate.parent
    else:
        candidate = root
    config = candidate / "shadow.yaml"
    return config if config.is_file() else None


def _merge(defaults: dict[str, ConfigValue], supplied: dict[str, ConfigValue]) -> dict[str, ConfigValue]:
    """Recursively overlay config without retaining input references."""
    result = deepcopy(defaults)
    for key, value in supplied.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _merge(existing, value)
        else:
            result[key] = deepcopy(value)
    return result


def load_config(start: Path) -> dict[str, ConfigValue]:
    """Load the current repo's config, or a fresh behavior-equivalent default."""
    config = find_config(start)
    if config is None:
        return deepcopy(DEFAULT_CONFIG)
    try:
        text = config.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(config, 1, f"cannot read configuration: {exc.strerror or exc}") from exc
    return _merge(DEFAULT_CONFIG, parse_config(text, config))
