#!/usr/bin/env python3
"""Bounded native process ownership for Shadow verification harnesses."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import math
import signal
import subprocess
import time
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    timed_out: bool
    session_id: int


@dataclass(frozen=True)
class PipeProcessResult:
    """A process result whose three pipes were bounded while they were read."""
    returncode: int
    timed_out: bool
    output_limited: bool
    stdout: bytes
    stderr: bytes
    session_id: int


def _drain_group(process: subprocess.Popen[bytes]) -> None:
    """Terminate helpers a host left in its fresh process group on every exit."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    time.sleep(0.2)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_bounded(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout: int,
) -> ProcessResult:
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            list(command),
            cwd=str(cwd),
            env=dict(env),
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        timed_out = False
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = 124
        finally:
            _drain_group(process)
            if process.poll() is None:
                process.wait()
        return ProcessResult(
            returncode=returncode,
            timed_out=timed_out,
            session_id=process.pid,
        )


def run_bounded_pipes(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    stdin: bytes,
    pass_fds: tuple[int, ...] = (),
    timeout: float = 2,
    max_output_bytes: int = 16 * 1024,
) -> PipeProcessResult:
    """Run one no-shell child with bounded live pipes and a reaped process group.

    Pipe caps apply while reading rather than after ``communicate`` has already
    accumulated arbitrary child output.  The group is drained even after a
    normal direct-child exit because descendants may still hold a pipe open.
    """
    if (not command or any(not isinstance(arg, str) or not arg for arg in command)
            or type(stdin) is not bytes
            or type(timeout) not in (int, float) or isinstance(timeout, bool) or not math.isfinite(timeout)
            or timeout <= 0 or timeout > 2
            or type(max_output_bytes) is not int or max_output_bytes <= 0 or max_output_bytes > 16 * 1024):
        raise ValueError("invalid bounded process limits")
    if len(stdin) > max_output_bytes:
        raise ValueError("stdin exceeds bounded process limit")
    if any(type(fd) is not int or fd < 0 for fd in pass_fds) or len(set(pass_fds)) != len(pass_fds):
        raise ValueError("invalid explicit descriptors")
    process = subprocess.Popen(
        list(command), cwd=str(cwd), env=dict(env), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        close_fds=True, pass_fds=pass_fds,
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    streams = {process.stdout: bytearray(), process.stderr: bytearray()}
    for pipe in streams:
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ)
    os.set_blocking(process.stdin.fileno(), False)
    sent = 0
    if stdin:
        selector.register(process.stdin, selectors.EVENT_WRITE)
    else:
        process.stdin.close()
    deadline = time.monotonic() + timeout
    timed_out = False
    output_limited = False
    group_drained = False
    try:
        while selector.get_map():
            # Once the direct child has exited, its group is immediately
            # drained, but registered pipes are still read through EOF.  That
            # retains output already written by a fast-exit child and detects
            # the cap+one byte instead of silently truncating it.
            if process.poll() is not None and not group_drained:
                _drain_group(process)
                group_drained = True
            # Group drain controls descendants in the original session, but it
            # cannot authorize an escaped ``setsid`` child to retain pipes
            # indefinitely.  The invocation deadline stays absolute.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            wait = min(0.05, remaining) if group_drained else remaining
            events = selector.select(wait)
            for key, mask in events:
                pipe = key.fileobj
                if pipe is process.stdin:
                    try:
                        written = os.write(pipe.fileno(), stdin[sent:])
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        written = len(stdin) - sent
                    sent += written
                    if sent >= len(stdin):
                        selector.unregister(pipe)
                        pipe.close()
                    continue
                try:
                    data = os.read(pipe.fileno(), max_output_bytes - len(streams[pipe]) + 1)
                except BlockingIOError:
                    continue
                if not data:
                    selector.unregister(pipe)
                    continue
                remaining = max_output_bytes - len(streams[pipe])
                streams[pipe].extend(data[:max(0, remaining)])
                if len(data) > remaining:
                    output_limited = True
                    break
            if output_limited:
                break
    finally:
        selector.close()
        if not group_drained:
            _drain_group(process)
        if process.poll() is None:
            process.wait()
        for pipe in (process.stdin, process.stdout, process.stderr):
            try:
                pipe.close()
            except OSError:
                pass
    return PipeProcessResult(
        returncode=124 if timed_out else process.returncode,
        timed_out=timed_out,
        output_limited=output_limited,
        stdout=bytes(streams[process.stdout]),
        stderr=bytes(streams[process.stderr]),
        session_id=process.pid,
    )
