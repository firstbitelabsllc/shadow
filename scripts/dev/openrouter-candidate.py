#!/usr/bin/env python3
"""Offline candidate experiment. No provider, Git, credentials, or authority API.

The ordinary seat supplies non-sensitive source bytes, exact writable names and
one immutable Python test. Model text can replace those names only. Tests run
on a disposable snapshot under macOS sandbox-exec; source custody never moves.
This is not a runnable Shadow host or acceptance proof.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import signal
import subprocess
import sys
import tempfile
import unicodedata


class Refused(ValueError):
    pass


def _name(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        raise Refused("invalid candidate name")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(
            part.startswith(".") or "\\" in part or any(ord(c) < 32 for c in part)
            for part in path.parts):
        raise Refused("candidate names must be exact relative non-hidden files")
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refused("duplicate candidate key")
        result[key] = value
    return result


def validate_inventory(files, writable, test):
    """Validate trusted source scope before any provider or test execution."""
    if not isinstance(files, dict) or not 1 <= len(files) <= 64:
        raise Refused("invalid source inventory")
    names = [_name(name) for name in files]
    normalized = [unicodedata.normalize("NFD", name).casefold() for name in names]
    if len(set(normalized)) != len(names):
        raise Refused("ambiguous source names")
    if any(str(parent) in normalized for name in normalized
           for parent in PurePosixPath(name).parents if str(parent) != "."):
        raise Refused("source file and directory names collide")
    if any(not isinstance(value, str) for value in files.values()) or sum(
            len(value.encode()) for value in files.values()) > 1024 * 1024:
        raise Refused("source exceeds text-only budget")
    if not isinstance(writable, set) or not writable or not writable <= files.keys():
        raise Refused("writable names must belong to the frozen inventory")
    if _name(test) not in files or test in writable:
        raise Refused("test must be present and immutable")


def evaluate(files, writable, test, proposal):
    """Return candidate bytes and test-process exit; never apply to source.

    files/writable/test are trusted seat inputs, not parsed from model output.
    Candidate code shares the interpreter and can exit before assertions run.
    Exit zero and diagnostic text are untrusted observations, never acceptance.
    Independent ordinary-seat diff review is required before testing source.
    """
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise Refused("the characterized macOS sandbox is required")
    validate_inventory(files, writable, test)
    if not isinstance(proposal, str) or len(proposal.encode()) > 1024 * 1024:
        raise Refused("candidate exceeds text-only budget")
    try:
        edits = json.loads(proposal, object_pairs_hook=_unique)
    except (ValueError, RecursionError) as error:
        raise Refused("invalid candidate JSON") from error
    if not isinstance(edits, dict) or not edits or not edits.keys() <= writable or any(
            not isinstance(value, str) for value in edits.values()):
        raise Refused("candidate can only replace declared files with text")
    # Framework Python's bin entry spawns this actual interpreter. Launch it
    # directly so the candidate can be denied all subsequent process creation.
    interpreter = Path(sys.base_prefix) / "Resources/Python.app/Contents/MacOS/Python"
    binary = str((interpreter if interpreter.is_file() else Path(sys.executable)).resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="openrouter-candidate-", dir="/private/tmp") as directory:
        root = Path(directory)
        snapshot = root / "candidate"
        scratch = root / "scratch"
        snapshot.mkdir()
        scratch.mkdir()
        for name, value in (files | edits).items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value)
        profile = root / "candidate.sb"
        profile.write_text('(version 1)\n(deny default)\n'
                           '(deny network*)\n(deny file-read* file-write*)\n'
                           '(allow file-read* (literal "/") (literal "/private") '
                           '(literal "/private/tmp") (literal ' + json.dumps(str(root)) + '))\n'
                           '(allow file-read* (subpath "/System/Library") (subpath "/usr/lib") '
                           '(subpath ' + json.dumps(str(Path(sys.base_prefix).resolve())) + ') '
                           '(literal "/dev/null") '
                           '(literal "/dev/urandom") (subpath ' + json.dumps(str(snapshot)) + '))\n'
                           '(allow file-read* (subpath ' + json.dumps(str(scratch)) + '))\n'
                           '(allow file-write-data (literal ' + json.dumps(str(scratch / "test-output")) + '))\n'
                           '(deny file-read-data (literal "/private") '
                           '(literal "/private/tmp") (literal ' + json.dumps(str(root)) + '))\n'
                           '(deny file-write-unlink)\n(deny process-fork)\n(deny process-exec)\n'
                           '(allow process-exec (literal ' + json.dumps(binary) + '))\n'
                           '(deny mach-lookup (global-name "com.apple.securityd"))\n')
        command = ["/usr/bin/sandbox-exec", "-f", str(profile), binary, "-I", "-B", "-c",
                   "import runpy,sys;sys.path.insert(0,sys.argv[1]);runpy.run_path(sys.argv[2],run_name='__main__')",
                   str(snapshot), str(snapshot / test)]
        env = {"PATH": "/usr/bin:/bin", "HOME": str(scratch), "TMPDIR": str(scratch), "LANG": "C.UTF-8"}

        def limits():
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))

        with (scratch / "test-output").open("wb") as output:
            process = subprocess.Popen(command, cwd=snapshot, env=env, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=output, start_new_session=True, preexec_fn=limits)
            try:
                code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                code = None
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        return {"scope": "offline-candidate-only", "candidate": edits, "test_process_exit_code": code,
                "accepted": False, "requires": "independent ordinary-seat diff review",
                "source_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                "diagnostic": (scratch / "test-output").read_text(errors="replace")[-2000:] if code != 0 else ""}
