#!/usr/bin/env python3
"""Offline candidate experiment. No provider, Git, credentials, or authority API.

The ordinary seat supplies non-sensitive source bytes, exact writable names and
one immutable Python test. Model text can replace those names only. Tests run
on a disposable read-only snapshot in the existing Docker Desktop Linux VM;
source custody never moves. The runner never starts a VM or pulls an image.
This is not a runnable Shadow host or acceptance proof.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid


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



# The installed, characterized arm64 image; never pull an image implicitly.
IMAGE = "sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
WALL_SECONDS = 15
OUTPUT_BYTES = 1024 * 1024
BOOTSTRAP = r'''import ctypes
import errno
import os
from pathlib import Path
import resource
import runpy
import sys

if os.uname().machine != 'aarch64':
    raise SystemExit('uncharacterized candidate architecture')
LIMIT = 64 * 1024 * 1024
controllers = {}
for line in Path('/proc/self/cgroup').read_text().splitlines():
    _, names, path = line.split(':', 2)
    controllers.update({name: path for name in names.split(',')})
assert controllers.get('memory') == '/' and controllers.get('pids') == '/'
assert Path('/sys/fs/cgroup/memory/memory.failcnt').read_text().strip() == '0'
for name in ('memory.limit_in_bytes', 'memory.memsw.limit_in_bytes'):
    assert int((Path('/sys/fs/cgroup/memory') / name).read_text()) == LIMIT
assert Path('/sys/fs/cgroup/pids/pids.max').read_text().strip() == '1'
resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))
resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))

class Arg(ctypes.Structure):
    _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_uint),
                ('datum_a', ctypes.c_uint64), ('datum_b', ctypes.c_uint64)]

lib = ctypes.CDLL('libseccomp.so.2', use_errno=True)
lib.seccomp_init.argtypes = [ctypes.c_uint32]
lib.seccomp_init.restype = ctypes.c_void_p
lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                      ctypes.c_uint, ctypes.POINTER(Arg)]
lib.seccomp_rule_add_array.restype = ctypes.c_int
lib.seccomp_load.argtypes = [ctypes.c_void_p]
lib.seccomp_load.restype = ctypes.c_int
ctx = lib.seccomp_init(0x50000 | errno.EPERM)
assert ctx

def allow(name, *args):
    number = lib.seccomp_syscall_resolve_name(name.encode())
    assert number >= 0, name
    filters = (Arg * len(args))(*args)
    assert lib.seccomp_rule_add_array(ctx, 0x7fff0000, number, len(args), filters) == 0, name

for name in ('read', 'close', 'lseek', 'fstat', 'newfstatat', 'getdents64',
             'readlinkat', 'getcwd', 'mmap', 'munmap', 'mprotect', 'brk',
             'mremap', 'madvise', 'rt_sigaction', 'rt_sigprocmask', 'rt_sigreturn',
             'sigaltstack', 'futex', 'getrandom', 'clock_gettime', 'getpid', 'gettid',
             'getuid', 'geteuid', 'getgid', 'getegid', 'exit', 'exit_group'):
    allow(name)
write_flags = os.O_ACCMODE | os.O_CREAT | os.O_TRUNC | os.O_APPEND
allow('openat', Arg(2, 7, write_flags, 0))
allow('write', Arg(0, 4, 1, 0))
allow('write', Arg(0, 4, 2, 0))
assert lib.seccomp_load(ctx) == 0

os.write(1, b'OPENROUTER_CANDIDATE_READY\n')
sys.path.insert(0, '/candidate')
runpy.run_path(sys.argv[1], run_name='__main__')
'''


def evaluate(files, writable, test, proposal):
    """Return candidate bytes and test-process exit; never apply to source.

    files/writable/test are trusted seat inputs, not parsed from model output.
    Candidate code shares the interpreter and can exit before assertions run.
    Exit zero and diagnostic text are untrusted observations, never acceptance.
    Independent ordinary-seat diff review is required before testing source.
    """
    if sys.platform != "darwin":
        raise Refused("the characterized local Docker Desktop runtime is required")
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
    docker = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    socket = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".docker/run/docker.sock"
    if not docker.is_file() or not socket.is_socket():
        raise Refused("the existing local Docker Desktop runtime is unavailable")
    with tempfile.TemporaryDirectory(prefix="openrouter-candidate-", dir="/private/tmp") as directory:
        root = Path(directory)
        snapshot = root / "candidate"
        snapshot.mkdir(mode=0o755)
        snapshot.chmod(0o755)
        for name, value in (files | edits).items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value)
            target.chmod(0o444)
        for path in snapshot.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
        bootstrap = root / "bootstrap.py"
        bootstrap.write_text(BOOTSTRAP)
        bootstrap.chmod(0o444)
        cidfile = root / "container-id"
        log = root / "test-output"
        env = {"PATH": "/usr/bin:/bin", "HOME": str(root), "DOCKER_CONFIG": str(root / "config"),
               "LANG": "C.UTF-8"}
        cli = [str(docker), "--host", "unix://" + str(socket)]
        run_label = "org.shadow.openrouter-candidate=" + uuid.uuid4().hex
        create = cli + ["create", "--pull=never", "--platform=linux/arm64", "--cidfile", str(cidfile),
                        "--label", run_label, "--network=none", "--read-only", "--ipc=none",
                        "--cgroupns=private",
                        "--log-driver=none", "--no-healthcheck", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                        "--pids-limit=1", "--memory=64m", "--memory-swap=64m", "--user=65534:65534",
                        "--workdir=/candidate", "--env=HOME=/nonexistent",
                        "--mount", f"type=bind,source={snapshot},target=/candidate,readonly,bind-recursive=disabled",
                        "--mount", f"type=bind,source={bootstrap},target=/bootstrap.py,readonly,bind-recursive=disabled",
                        "--entrypoint=/usr/local/bin/python3", IMAGE, "-I", "-B", "/bootstrap.py", "/candidate/" + test]
        cid = None
        try:
            created = subprocess.run(create, env=env, stdin=subprocess.DEVNULL,
                                     capture_output=True, text=True, timeout=10)
            if cidfile.is_file():
                cid = cidfile.read_text().strip()
                if not re.fullmatch(r"[0-9a-f]{64}", cid):
                    raise Refused("invalid owned container identity")
            if created.returncode or cid is None:
                raise Refused("candidate container creation failed")
            inspected = subprocess.run(cli + ["inspect", cid], env=env, capture_output=True,
                                       text=True, timeout=10, check=True)
            spec = json.loads(inspected.stdout)[0]
            config = spec["HostConfig"]
            expected = {"Memory": 64 * 1024 * 1024, "MemorySwap": 64 * 1024 * 1024,
                        "PidsLimit": 1, "ReadonlyRootfs": True, "NetworkMode": "none",
                        "IpcMode": "none", "PidMode": "", "CgroupnsMode": "private"}
            expected_mounts = {("bind", str(snapshot), "/candidate", False),
                               ("bind", str(bootstrap), "/bootstrap.py", False)}
            actual_mounts = {(mount["Type"], mount["Source"], mount["Destination"], mount["RW"])
                             for mount in spec["Mounts"]}
            if any(config.get(key) != value for key, value in expected.items()) or \
                    config.get("LogConfig", {}).get("Type") != "none" or \
                    config.get("CapDrop") != ["ALL"] or \
                    config.get("SecurityOpt") != ["no-new-privileges"] or \
                    spec["Image"] != IMAGE or spec["Config"]["User"] != "65534:65534" or \
                    spec["Config"].get("Healthcheck", {}).get("Test") != ["NONE"] or \
                    len(spec["Mounts"]) != 2 or actual_mounts != expected_mounts or \
                    len(config.get("Mounts", [])) != 2 or any(
                        not mount.get("BindOptions", {}).get("NonRecursive") for mount in config["Mounts"]):
                raise Refused("candidate container controls differ from the frozen contract")

            # Bound attached output in the parent. preexec_fn could deadlock
            # in a threaded caller before the cleanup path becomes reachable.
            observed = bytearray()
            process = subprocess.Popen(cli + ["start", "--attach", cid], env=env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            code = None
            deadline = time.monotonic() + WALL_SECONDS
            with log.open("wb") as output:
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ)
                        while len(observed) < OUTPUT_BYTES:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            if not selector.select(timeout=remaining):
                                break
                            chunk = os.read(process.stdout.fileno(), min(65536, OUTPUT_BYTES - len(observed)))
                            if not chunk:
                                try:
                                    code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
                                except subprocess.TimeoutExpired:
                                    pass
                                break
                            observed.extend(chunk)
                            output.write(chunk)
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                    process.stdout.close()
        finally:
            # The cidfile is written only by our create invocation, outside the
            # candidate mounts. Never target another container, name or daemon.
            if cid is None and cidfile.is_file():
                cid = cidfile.read_text().strip()
            if cid is None or not re.fullmatch(r"[0-9a-f]{64}", cid):
                # A create response can be lost after daemon-side creation.
                # Recover only this invocation's unpredictable exact label.
                try:
                    recovery = subprocess.run(cli + ["container", "ls", "--all", "--quiet", "--no-trunc",
                                                     "--filter", "label=" + run_label], env=env,
                                              capture_output=True, text=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise Refused("candidate create recovery unconfirmed: " + run_label) from error
                matches = recovery.stdout.splitlines()
                if recovery.returncode or len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{64}", matches[0]):
                    # Even an empty readback cannot prove a timed-out create
                    # won't finish later. Keep the exact recovery handle.
                    raise Refused("candidate create recovery unconfirmed: " + run_label)
                cid = matches[0]
            if cid is not None and re.fullmatch(r"[0-9a-f]{64}", cid):
                removed = False
                for _ in range(2):
                    try:
                        subprocess.run(cli + ["rm", "--force", cid], env=env, stdin=subprocess.DEVNULL,
                                       capture_output=True, timeout=10)
                        remaining = subprocess.run(cli + ["container", "ls", "--all", "--quiet", "--no-trunc",
                                                          "--filter", "id=" + cid], env=env,
                                                   capture_output=True, timeout=10)
                        if remaining.returncode == 0 and not remaining.stdout.strip():
                            removed = True
                            break
                    except (OSError, subprocess.TimeoutExpired):
                        continue
                if not removed:
                    raise Refused("owned candidate cleanup unconfirmed: " + cid)
        observed = log.read_bytes()
        if not observed.startswith(b"OPENROUTER_CANDIDATE_READY\n"):
            raise Refused("candidate resource and syscall admission did not complete")
        return {"scope": "offline-candidate-only", "candidate": edits, "test_process_exit_code": code,
                "accepted": False, "requires": "independent ordinary-seat diff review",
                "source_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                "diagnostic": observed.decode(errors="replace")[-2000:] if code != 0 else ""}
