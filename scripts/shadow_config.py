"""Read Shadow's deliberately small, machine-local repository configuration.

This is intentionally *not* a general YAML parser.  Shadow needs one tiny,
reviewable configuration surface, so unsupported YAML is refused with an exact
source line instead of being interpreted approximately.  In particular, this
module has no provider, host, credential, environment, or persistent state.
The schema/consumer layer decides which parsed keys are meaningful.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import Any, Final


ConfigValue = str | int | bool | None | list["ConfigValue"] | dict[str, "ConfigValue"]

LOCAL_CONFIG: Final = Path(".shadow/local.yaml")
MACHINE_CONFIG: Final = Path(".shadow/machine.yaml")
RECOMMENDED_TEMPLATE: Final = Path("shadow.example.yaml")
MACHINE_TEMPLATE: Final = Path("shadow.machine.example.yaml")

# These are the behavior-equivalent defaults.  ``load_config`` always returns
# a fresh deep copy, so a caller can never turn a read into process state by
# mutating its result.
DEFAULT_CONFIG: Final[dict[str, ConfigValue]] = {
    "version": 1,
    "computer": {"expected_board_root": None},
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

MACHINE_DEFAULT_CONFIG: Final[dict[str, ConfigValue]] = {
    "version": 1,
    "board": {"root": None},
    "directives": {
        "source": None,
        "targets": {},
        "projections": {},
    },
}

_KEY_RE: Final = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_INTEGER_RE: Final = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_FORBIDDEN_SCALAR_PREFIXES: Final = ("[", "{", "&", "*", "!", "|", ">", "@", "`")
# A configuration file may state reviewed method preferences, never choose a
# native runtime or carry the material needed to authenticate one.  Normalize
# punctuation and case before matching so ``api-key``, ``api_key``, and
# ``APIKey`` cannot create three accidental escape hatches.
_REFUSED_KEY_FRAGMENTS: Final = (
    "provider",
    "model",
    "account",
    "credential",
    "token",
    "secret",
    "password",
    "passphrase",
    "apikey",
    "accesskey",
    "privatekey",
    "route",
    "host",
    "selector",
    "profile",
    "seat",
    "executor",
    "runtime",
    "binary",
)


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


def _refused_key(key: str) -> bool:
    """Whether ``key`` could select/authenticate a native host or secret."""
    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    return any(fragment in normalized for fragment in _REFUSED_KEY_FRAGMENTS)


def _refuse_selector_or_secret_keys(text: str, path: Path) -> None:
    """Fail closed for forbidden keys at every mapping depth.

    The syntax parser intentionally returns a generic AST so the config
    schema can evolve without a second parser.  This safety boundary is kept
    beside loading instead: every actual local-config load performs it,
    while a caller that only parses source can still inspect unsupported-key
    candidates in a test or future schema diagnostic.
    """
    for source in _source_lines(text, path):
        if source.content == "-" or source.content.startswith("- "):
            continue
        key, _ = _mapping_entry(source, path)
        if _refused_key(key):
            raise ConfigError(
                path,
                source.number,
                f"configuration key '{key}' is refused: provider, model, account, "
                "credential, selector, and secret bindings belong to native hosts",
            )


def _mapping_line_numbers(text: str, path: Path) -> dict[tuple[str, ...], int]:
    """Map each mapping path to its source line for schema diagnostics."""
    stack: list[tuple[int, str]] = []
    result: dict[tuple[str, ...], int] = {}
    for source in _source_lines(text, path):
        if source.content == "-" or source.content.startswith("- "):
            continue
        key, _ = _mapping_entry(source, path)
        while stack and stack[-1][0] >= source.indent:
            stack.pop()
        current = tuple(item[1] for item in stack) + (key,)
        result[current] = source.number
        stack.append((source.indent, key))
    return result


def _validate_config(parsed: dict[str, ConfigValue], text: str, path: Path) -> None:
    """Validate the complete v1 schema so no reviewed key is silently ignored."""
    lines = _mapping_line_numbers(text, path)

    def fail(parts: tuple[str, ...], detail: str) -> None:
        raise ConfigError(path, lines.get(parts, 1), detail)

    allowed_top = {
        "version",
        "board",
        "computer",
        "directives",
        "leads",
        "method",
        "buckets",
        "durability",
    }
    for key in parsed:
        if key not in allowed_top:
            fail((key,), f"unknown configuration key '{key}'")
    version = parsed.get("version", 1)
    if isinstance(version, bool) or version != 1:
        fail(("version",), "version must be the integer 1")

    def declared_path(parts: tuple[str, ...], value: ConfigValue) -> None:
        if value is None:
            return
        if not isinstance(value, str) or not value:
            fail(parts, f"{'.'.join(parts)} must be null or a nonempty path string")
        if not (value.startswith("/") or value.startswith("~/")):
            fail(parts, f"{'.'.join(parts)} must be absolute or home-relative")
        if ".." in Path(value.removeprefix("~/")).parts:
            fail(parts, f"{'.'.join(parts)} must not contain '..'")

    board = parsed.get("board", {})
    if not isinstance(board, dict):
        fail(("board",), "board must be a mapping")
    for key in board:
        if key != "root":
            fail(("board", key), f"unknown board key '{key}'")
    declared_path(("board", "root"), board.get("root"))

    computer = parsed.get("computer", {})
    if not isinstance(computer, dict):
        fail(("computer",), "computer must be a mapping")
    for key in computer:
        if key != "expected_board_root":
            fail(("computer", key), f"unknown computer assertion '{key}'")
    declared_path(("computer", "expected_board_root"), computer.get("expected_board_root"))

    directives = parsed.get("directives", {})
    if not isinstance(directives, dict):
        fail(("directives",), "directives must be a mapping")
    for key in directives:
        if key not in {"source", "targets", "projections"}:
            fail(("directives", key), f"unknown directives key '{key}'")
    source = directives.get("source")
    declared_path(("directives", "source"), source)
    targets = directives.get("targets", {})
    if not isinstance(targets, dict):
        fail(("directives", "targets"), "directives.targets must be a mapping")
    for name, value in targets.items():
        if name not in {"claude", "codex"}:
            fail(("directives", "targets", name), f"unknown directive target '{name}'")
        declared_path(("directives", "targets", name), value)
    projections = directives.get("projections", {})
    if not isinstance(projections, dict):
        fail(("directives", "projections"), "directives.projections must be a mapping")
    for name, value in projections.items():
        if name != "cursor":
            fail(("directives", "projections", name), f"unknown directive projection '{name}'")
        if value != "user_rules":
            fail(
                ("directives", "projections", name),
                "directives.projections.cursor must be 'user_rules'",
            )
    if source is None and (targets or projections):
        fail(("directives",), "directive targets and projections require directives.source")
    if source is not None and set(targets) != {"claude", "codex"}:
        fail(
            ("directives", "targets"),
            "directives.source requires exactly claude and codex targets",
        )

    method = parsed.get("method", {})
    if not isinstance(method, dict):
        fail(("method",), "method must be a mapping")
    for key in method:
        if key != "adversarial_lenses":
            fail(("method", key), f"unknown method key '{key}'")
    lenses = method.get("adversarial_lenses", DEFAULT_CONFIG["method"]["adversarial_lenses"])
    if not isinstance(lenses, list) or not lenses or not all(isinstance(item, str) and item for item in lenses):
        fail(("method", "adversarial_lenses"), "method.adversarial_lenses must be a nonempty string list")

    durability = parsed.get("durability", {})
    if not isinstance(durability, dict):
        fail(("durability",), "durability must be a mapping")
    for key in durability:
        if key != "claim_return_minutes":
            fail(("durability", key), f"unknown durability key '{key}'")
    minutes = durability.get("claim_return_minutes", DEFAULT_CONFIG["durability"]["claim_return_minutes"])
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes not in range(1, 10_081):
        fail(("durability", "claim_return_minutes"), "durability.claim_return_minutes must be an integer from 1 to 10080")

    buckets = parsed.get("buckets", {})
    if not isinstance(buckets, dict):
        fail(("buckets",), "buckets must be a mapping")
    for name, binding in buckets.items():
        if not isinstance(binding, str) or not binding:
            fail(("buckets", name), f"buckets.{name} must be a nonempty string")

    leads = parsed.get("leads", {})
    if not isinstance(leads, dict):
        fail(("leads",), "leads must be a mapping")
    allowed_lead = {"display_name", "default_lenses"}
    for owner, preference in leads.items():
        if not isinstance(preference, dict):
            fail(("leads", owner), f"leads.{owner} must be a mapping")
        for key in preference:
            if key not in allowed_lead:
                fail(("leads", owner, key), f"unknown lead preference '{key}'")
        display_name = preference.get("display_name")
        if display_name is not None and (
            not isinstance(display_name, str) or not display_name
        ):
            fail(
                ("leads", owner, "display_name"),
                f"leads.{owner}.display_name must be a nonempty string",
            )
        lead_lenses = preference.get("default_lenses", [])
        if not isinstance(lead_lenses, list) or not all(
            isinstance(item, str) and item for item in lead_lenses
        ):
            fail(("leads", owner, "default_lenses"), f"leads.{owner}.default_lenses must be a string list")


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


def parse_config(text: str, path: Path | str = LOCAL_CONFIG) -> dict[str, ConfigValue]:
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


def config_paths(start: Path) -> tuple[Path, Path, Path]:
    """Return the repository root, effective local path, and reviewed template."""
    root = _repo_root(Path(start))
    if root is None:
        candidate = Path(start).resolve()
        if candidate.is_file():
            candidate = candidate.parent
        root = candidate
    return root, root / LOCAL_CONFIG, root / RECOMMENDED_TEMPLATE


def find_config(start: Path, *, scope: str = "entity") -> Path | None:
    """Find exactly the selected ignored configuration surface, if any."""
    root, entity_config, _ = config_paths(start)
    config = entity_config if scope == "entity" else root / MACHINE_CONFIG
    return config if config.is_file() else None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _require_local_contract(
    root: Path,
    config: Path,
    relative: Path = LOCAL_CONFIG,
    *,
    init_action: str = "--init-local",
) -> None:
    """Refuse an effective config Git could publish or one already tracked."""
    relative_name = relative.as_posix()
    if _git(root, "ls-files", "--error-unmatch", "--", relative_name).returncode == 0:
        raise ConfigError(config, 1, "effective configuration must not be tracked by Git")
    ignored = _git(root, "check-ignore", "--quiet", "--no-index", "--", relative_name)
    if ignored.returncode != 0:
        raise ConfigError(
            config,
            1,
            f"effective configuration is not locally ignored; run 'shadow config {init_action}'",
        )


def _exclude_path(root: Path, effective: Path = LOCAL_CONFIG) -> Path:
    result = _git(root, "rev-parse", "--git-path", "info/exclude")
    if result.returncode:
        raise ConfigError(root / effective, 1, "repository Git exclusion path is unavailable")
    path = Path(result.stdout.strip())
    if not path.is_absolute():
        path = root / path
    return path


def _write_atomic(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _create_atomic(path: Path, text: str, mode: int) -> None:
    """Publish a complete new file without ever replacing an existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ConfigError(path, 1, "effective configuration already exists; it was not overwritten") from exc
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _install_local_exclude(root: Path, effective: Path = LOCAL_CONFIG) -> tuple[Path, bool, str, str, int, bool]:
    exclude = _exclude_path(root, effective)
    try:
        if exclude.is_symlink():
            raise ConfigError(root / effective, 1, "repository Git exclude file must not be a symlink")
        existed = exclude.exists()
        current = exclude.read_text(encoding="utf-8") if existed else ""
        mode = stat.S_IMODE(exclude.stat().st_mode) if existed else 0o600
    except (OSError, UnicodeError) as exc:
        raise ConfigError(root / effective, 1, f"cannot read repository Git exclude: {exc}") from exc
    rule = f"/{effective.as_posix()}"
    changed = rule not in current.splitlines()
    updated = current
    if changed:
        if updated and not updated.endswith("\n"):
            updated += "\n"
        updated += rule + "\n"
        try:
            _write_atomic(exclude, updated, mode)
        except OSError as exc:
            raise ConfigError(
                root / effective,
                1,
                f"cannot update repository Git exclude: {exc}",
            ) from exc
    return exclude, existed, current, updated, mode, changed


def _rollback_local_exclude(receipt: tuple[Path, bool, str, str, int, bool]) -> None:
    """Undo only our exact exclusion write; never overwrite a concurrent edit."""
    exclude, existed, original, installed, mode, changed = receipt
    if not changed:
        return
    try:
        if not exclude.is_file() or exclude.is_symlink():
            return
        if exclude.read_text(encoding="utf-8") != installed:
            return
        if existed:
            _write_atomic(exclude, original, mode)
        else:
            exclude.unlink()
            directory = os.open(exclude.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except (OSError, UnicodeError):
        # A failed initialization must not turn rollback into permission to
        # clobber a Git file whose state can no longer be proven unchanged.
        return


def _validate_scope(
    parsed: dict[str, ConfigValue],
    text: str,
    path: Path,
    *,
    scope: str,
) -> None:
    refused = (
        ("board", "directives")
        if scope == "entity"
        else ("computer", "leads", "method", "buckets", "durability")
    )
    label = "an entity config" if scope == "entity" else "machine bootstrap"
    lines = _mapping_line_numbers(text, path)
    for key in refused:
        if key in parsed:
            raise ConfigError(
                path,
                lines.get((key,), 1),
                f"{key} is {'machine bootstrap configuration' if scope == 'entity' else 'entity configuration'} "
                f"and is refused in {label}",
            )


def _initialize_config(
    start: Path,
    *,
    template_name: Path,
    scope: str,
    action: str,
    allow_shipped_fallback: bool,
    effective_name: Path,
) -> tuple[Path, Path, bool]:
    """Create one ignored scoped config through the shared no-overwrite path."""
    root = _repo_root(Path(start))
    if root is None:
        raise ConfigError(
            Path(start).resolve() / effective_name,
            1,
            f"{action} requires a Git repository",
        )
    config = root / effective_name
    repository_template = root / template_name
    shipped_template = Path(__file__).resolve().parent.parent / template_name
    if repository_template.exists() or repository_template.is_symlink():
        if _git(root, "ls-files", "--error-unmatch", "--", template_name.as_posix()).returncode:
            raise ConfigError(
                repository_template,
                1,
                "recommended template must be tracked by Git",
            )
        if (
            _git(root, "cat-file", "-e", f"HEAD:{template_name.as_posix()}").returncode
            or _git(root, "diff", "--quiet", "--", template_name.as_posix()).returncode
            or _git(root, "diff", "--cached", "--quiet", "--", template_name.as_posix()).returncode
        ):
            raise ConfigError(
                repository_template,
                1,
                "recommended template must match its committed HEAD bytes",
            )
        template = repository_template
    elif allow_shipped_fallback:
        template = shipped_template
    else:
        raise ConfigError(repository_template, 1, "recommended machine template is missing")
    try:
        metadata = template.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ConfigError(template, 1, "recommended template must be a regular file")
        text = template.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(template, 1, "recommended template is missing") from exc
    except (OSError, UnicodeError) as exc:
        raise ConfigError(template, 1, f"cannot read recommended template: {exc}") from exc
    parsed = parse_config(text, template)
    _refuse_selector_or_secret_keys(text, template)
    _validate_config(parsed, text, template)
    _validate_scope(parsed, text, template, scope=scope)

    if config.is_symlink():
        raise ConfigError(config, 1, "effective configuration must not be a symlink")
    if config.parent.is_symlink():
        raise ConfigError(config, 1, "effective configuration parent must not be a symlink")
    if config.parent.exists() and not config.parent.is_dir():
        raise ConfigError(config, 1, "effective configuration parent must be a directory")
    if config.exists() and not config.is_file():
        raise ConfigError(config, 1, "effective configuration must be a regular file")
    if _git(root, "ls-files", "--error-unmatch", "--", effective_name.as_posix()).returncode == 0:
        raise ConfigError(config, 1, "effective configuration must not be tracked by Git")
    if config.exists():
        try:
            existing_text = config.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ConfigError(config, 1, f"cannot read effective configuration: {exc}") from exc
        existing = parse_config(existing_text, config)
        _refuse_selector_or_secret_keys(existing_text, config)
        _validate_config(existing, existing_text, config)
        _validate_scope(existing, existing_text, config, scope=scope)

    ignore_probe = _git(
        root,
        "check-ignore",
        "--verbose",
        "--no-index",
        "--",
        effective_name.as_posix(),
    )
    if ignore_probe.returncode and ignore_probe.stdout.strip():
        raise ConfigError(
            config,
            1,
            "repository ignore rules expose the effective configuration; remove the negation",
        )
    receipt = _install_local_exclude(root, effective_name)
    try:
        if _git(
            root,
            "check-ignore",
            "--quiet",
            "--no-index",
            "--",
            effective_name.as_posix(),
        ).returncode:
            raise ConfigError(
                config,
                1,
                "repository ignore rules expose the effective configuration; remove the negation",
            )
        created = not config.exists()
        if created:
            try:
                _create_atomic(config, text, 0o600)
            except ConfigError:
                raise
            except OSError as exc:
                raise ConfigError(config, 1, f"cannot create effective configuration: {exc}") from exc
        _require_local_contract(root, config, effective_name, init_action=action)
    except Exception:
        _rollback_local_exclude(receipt)
        raise
    return config, template, created


def initialize_local_config(start: Path) -> tuple[Path, Path, bool]:
    """Create an ignored entity config from its reviewed repository template."""
    return _initialize_config(
        start,
        template_name=RECOMMENDED_TEMPLATE,
        scope="entity",
        action="--init-local",
        allow_shipped_fallback=True,
        effective_name=LOCAL_CONFIG,
    )


def initialize_machine_config(root: Path | None = None) -> tuple[Path, Path, bool]:
    """Create the installed checkout's ignored machine-bootstrap config."""
    installed = root or Path(os.environ.get("SHADOW_ROOT", Path(__file__).resolve().parent.parent))
    return _initialize_config(
        installed,
        template_name=MACHINE_TEMPLATE,
        scope="machine",
        action="--init-machine",
        allow_shipped_fallback=False,
        effective_name=MACHINE_CONFIG,
    )


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


def load_config(start: Path, *, scope: str = "entity") -> dict[str, ConfigValue]:
    """Load the current repo's config, or a fresh behavior-equivalent default."""
    if scope not in {"entity", "machine"}:
        raise ValueError("configuration scope must be 'entity' or 'machine'")
    root, entity_path, _ = config_paths(start)
    relative_path = LOCAL_CONFIG if scope == "entity" else MACHINE_CONFIG
    local_path = entity_path if scope == "entity" else root / MACHINE_CONFIG
    if _git(root, "ls-files", "--error-unmatch", "--", relative_path.as_posix()).returncode == 0:
        raise ConfigError(local_path, 1, "effective configuration must not be tracked by Git")
    if local_path.is_symlink():
        raise ConfigError(local_path, 1, "effective configuration must not be a symlink")
    if local_path.exists() and not local_path.is_file():
        raise ConfigError(local_path, 1, "effective configuration must be a regular file")
    config = find_config(start, scope=scope)
    defaults = DEFAULT_CONFIG if scope == "entity" else MACHINE_DEFAULT_CONFIG
    if config is None:
        return deepcopy(defaults)
    if config.is_symlink():
        raise ConfigError(config, 1, "effective configuration must not be a symlink")
    _require_local_contract(
        root,
        local_path,
        relative_path,
        init_action="--init-local" if scope == "entity" else "--init-machine",
    )
    try:
        text = config.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(config, 1, f"cannot read configuration: {exc.strerror or exc}") from exc
    parsed = parse_config(text, config)
    _refuse_selector_or_secret_keys(text, config)
    _validate_config(parsed, text, config)
    if scope == "entity":
        for key in ("board", "directives"):
            if key in parsed:
                lines = _mapping_line_numbers(text, config)
                raise ConfigError(
                    config,
                    lines.get((key,), 1),
                    f"{key} is machine bootstrap configuration and is refused in an entity config",
                )
    else:
        for key in ("computer", "leads", "method", "buckets", "durability"):
            if key in parsed:
                lines = _mapping_line_numbers(text, config)
                raise ConfigError(
                    config,
                    lines.get((key,), 1),
                    f"{key} is entity configuration and is refused in machine bootstrap",
                )
    return _merge(defaults, parsed)


def load_machine_config(root: Path | None = None) -> dict[str, ConfigValue]:
    """Load the installed checkout's one machine-bootstrap declaration."""
    installed = root or Path(os.environ.get("SHADOW_ROOT", Path(__file__).resolve().parent.parent))
    return load_config(installed, scope="machine")


def expand_declared_path(value: str, *, home: Path | None = None) -> Path:
    """Resolve one already-validated absolute or home-relative declaration."""
    if value.startswith("~/"):
        return (home or Path.home()).resolve() / value[2:]
    return Path(value)


def machine_board_root(
    installed_root: Path | None = None,
    *,
    home: Path | None = None,
) -> Path:
    """Resolve the installed Shadow checkout's one board-root declaration.

    The caller may pass ``home`` only to make ``~/`` and the historical
    ``~/.shadow`` default deterministic in tests.  Repository configuration
    never selects this path.
    """
    config = load_machine_config(installed_root)
    board = config.get("board", {})
    if not isinstance(board, dict):
        raise ConfigError(
            (installed_root or Path(os.environ.get("SHADOW_ROOT", "."))) / MACHINE_CONFIG,
            1,
            "board must be a mapping",
        )
    declared = board.get("root")
    if declared is None:
        return (home or Path.home()).resolve() / ".shadow"
    if not isinstance(declared, str):
        raise ConfigError(
            (installed_root or Path(os.environ.get("SHADOW_ROOT", "."))) / MACHINE_CONFIG,
            1,
            "board.root must be null or a nonempty path string",
        )
    # Preserve the declared component chain until the board safety boundary
    # has checked every existing parent for symlinks.
    return expand_declared_path(declared, home=home)


def assert_expected_board_root(
    entity_start: Path,
    actual_root: Path,
    *,
    home: Path | None = None,
) -> None:
    """Fail when an entity's local assertion names a different machine board."""
    config = load_config(entity_start, scope="entity")
    computer = config.get("computer", {})
    if not isinstance(computer, dict):
        raise ConfigError(Path(entity_start) / LOCAL_CONFIG, 1, "computer must be a mapping")
    declared = computer.get("expected_board_root")
    if declared is None:
        return
    if not isinstance(declared, str):
        raise ConfigError(
            Path(entity_start) / LOCAL_CONFIG,
            1,
            "computer.expected_board_root must be null or a nonempty path string",
        )
    expected = expand_declared_path(declared, home=home).resolve()
    if expected != Path(actual_root).resolve():
        raise ConfigError(
            Path(entity_start) / LOCAL_CONFIG,
            1,
            "computer.expected_board_root does not match this computer's configured board root",
        )
