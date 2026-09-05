"""The optional notification process cannot become board authority."""
from __future__ import annotations

import os
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import shadow_huddle_event as event_api

EVENT = {"schema": "shadow.huddle-delivery-event.v1", "event": "huddle_changed",
         "huddle_id": "hdl_00000001", "generation": 1}


class HuddleEventTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()

    def test_event_schema_has_only_frozen_fields(self):
        self.assertEqual(event_api.validate_event(EVENT), EVENT)
        for changes in ({"summary": "private"}, {"generation": True},
                        {"generation": 0}, {"huddle_id": "../board"},
                        {"event": "claim"}, {"schema": "other"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                event_api.validate_event(EVENT | changes)
        with self.assertRaises(ValueError):
            event_api.validate_event({k: v for k, v in EVENT.items() if k != "event"})

    def test_noop_emits_nothing_and_changed_mutation_is_preserved(self):
        noop = SimpleNamespace(payload={}, changed=False, event=None)
        changed = SimpleNamespace(payload={"sentinel": "unchanged"}, changed=True, event=EVENT)
        with mock.patch.object(event_api, "emit_post_commit") as emit:
            self.assertIs(event_api.post_commit_mutation(noop, repo_root=self.home), noop)
            emit.assert_not_called()
            self.assertIs(event_api.post_commit_mutation(changed, repo_root=self.home), changed)
            emit.assert_called_once_with(EVENT, repo_root=self.home)
        with mock.patch.object(event_api, "emit_post_commit", side_effect=OSError("transport")):
            self.assertIs(event_api.post_commit_mutation(changed, repo_root=self.home), changed)

    def test_absent_adapter_never_creates_runtime_or_launches_child(self):
        before = tuple(self.home.iterdir())
        with mock.patch.object(event_api, "_launch_prepared_runner") as launch:
            result = event_api.run_confined_event_runner(EVENT, repo_root=self.home, home=self.home)
            self.assertFalse(result["available"])
            launch.assert_not_called()
        self.assertEqual(tuple(self.home.iterdir()), before)
        event_api.emit_post_commit(None, repo_root=self.home)

    def test_explicit_board_home_is_preserved_through_notification(self):
        mutation = SimpleNamespace(payload={}, changed=True, event=EVENT)
        source = Path(__file__).resolve().parent.parent
        with mock.patch.object(event_api, "run_confined_event_runner") as runner:
            event_api.post_commit_mutation(mutation, repo_root=source, home=self.home)
            runner.assert_called_once_with(EVENT, repo_root=source, home=self.home)

    def test_committed_mutation_notification_observes_an_unlocked_board(self):
        import fcntl
        from tests.test_huddle import HuddleBidTests, board_api
        fixture = HuddleBidTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        observed = []
        def inspect(event, *, repo_root):
            with (fixture.home / ".shadow" / board_api.LOCK_NAME).open("rb") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                snapshot = board_api.snapshot(home=fixture.home)
                self.assertEqual(snapshot["huddles"][0]["generation"], event["generation"])
                observed.append(snapshot)
        # Negative control proves the callback detects a still-held lock.
        with board_api._transaction(fixture.home):
            with self.assertRaises(BlockingIOError):
                inspect(EVENT, repo_root=self.home)
        mutation = fixture.submit()
        with mock.patch.object(event_api, "emit_post_commit", side_effect=inspect):
            self.assertIs(event_api.post_commit_mutation(mutation, repo_root=self.home), mutation)
            replay = fixture.submit()
            self.assertFalse(replay.changed)
            event_api.post_commit_mutation(replay, repo_root=self.home)
        self.assertEqual(observed, [mutation.payload])

    def test_unsupported_host_never_launches_child(self):
        with mock.patch.object(event_api, "confinement_backend", return_value=None), \
             mock.patch.object(event_api, "_launch_prepared_runner") as launch:
            result = event_api.run_confined_event_runner(EVENT, repo_root=self.home, home=self.home)
            self.assertEqual(result, {"available": False, "reason": "unsupported_confinement"})
            launch.assert_not_called()

    def test_actual_host_confinement_admission_or_explicit_unsupported_refusal(self):
        if sys.platform == "darwin":
            self.assertEqual(event_api.confinement_backend(), "darwin-seatbelt")
            return
        before = tuple(self.home.iterdir())
        with mock.patch.object(event_api, "_launch_prepared_runner") as launch:
            result = event_api.run_confined_event_runner(EVENT, repo_root=self.home, home=self.home)
        self.assertEqual(result, {"available": False, "reason": "unsupported_confinement"})
        launch.assert_not_called()
        self.assertEqual(tuple(self.home.iterdir()), before)

    def test_board_unknown_or_writable_readonly_descriptor_is_refused(self):
        target = self.home / "sentinel"
        target.write_bytes(b"unchanged")
        fd = os.open(target, os.O_RDWR)
        self.addCleanup(os.close, fd)
        for role in ("board_fd", "board_directory", "sentinel", "capabilities"):
            with self.subTest(role=role), self.assertRaises(event_api.RunnerRefused):
                event_api.validate_runner_fds({role: fd})

    def test_absent_contact_registration_is_bounded_and_readonly(self):
        with mock.patch.object(event_api, "_launch_prepared_runner") as launch:
            result = event_api.contact_register_unavailable(
                seat="Codex", stdin=b"{}", repo_root=self.home)
            self.assertEqual(result, {"available": False, "reason": "optional delivery adapter absent"})
            for seat, body in (("bad\nseat", b"{}"), ("Codex", b"x" * 16385)):
                with self.subTest(seat=seat), self.assertRaises(event_api.RunnerRefused):
                    event_api.contact_register_unavailable(seat=seat, stdin=body, repo_root=self.home)
            launch.assert_not_called()
        self.assertEqual(tuple(self.home.iterdir()), ())

    def runtime(self):
        from tests.test_huddle import HuddleSchemaTests
        seed = HuddleSchemaTests()
        seed.home = self.home
        board = seed.fixture("open_round_1")
        extension = self.home / ".shadow" / "runtime" / "huddle-delivery"
        contacts = extension.parent / "contacts"
        for path in (extension.parent.parent, extension.parent, extension, contacts):
            path.mkdir(mode=0o700, exist_ok=True)
        board_path = extension.parent.parent / "board.json"
        board_path.write_text(json.dumps(board))
        board_path.chmod(0o600)
        for name in ("shadow-huddle-deliver-event.py", "shadow-contact-register.py"):
            path = extension / name
            path.write_text("import json,sys; json.load(sys.stdin); print('{}')\n")
            path.chmod(0o600)
        client = self.home / "native-client"
        if sys.platform == "darwin":
            shutil.copyfile("/usr/bin/true", client)
        else:
            # Pure descriptor/recipient selection only; this is never run.
            client.write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 64)
        client.chmod(0o700)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
        caps = {"schema": "shadow.huddle-provider-capabilities.v1",
                "generated_at": stamp(now), "expires_at": stamp(now + timedelta(minutes=10)),
                "entries": [{"provider": "cmux", "capability": "cmux.surface-send.v1",
                             "transport": "exec", "target": str(client)}]}
        capability_path = extension / "shadow-huddle-provider-capabilities.json"
        capability_path.write_text(json.dumps(caps))
        capability_path.chmod(0o600)
        claim = board["claims"][0]
        contact = {"schema": "shadow.huddle-contact.v1", "seat": claim["owner"],
                   "instance_nonce": "123e4567-e89b-12d3-a456-426614174003",
                   "provider": "cmux", "capability": "cmux.surface-send.v1",
                   "endpoint": {"surface_uuid": "123e4567-e89b-12d3-a456-426614174002"},
                   "claim_keys": [{key: claim[key] for key in ("entity", "row", "claim_revision", "owner")}],
                   "registered_at": stamp(now), "refreshed_at": stamp(now), "expires_at": stamp(now + timedelta(minutes=10))}
        contact_path = contacts / (contact["instance_nonce"] + ".json")
        contact_path.write_text(json.dumps(contact))
        contact_path.chmod(0o600)
        return board, extension, contacts, client, caps, contact

    def test_preselection_binds_current_recipient_and_retained_readonly_fds(self):
        board, extension, contacts, client, caps, contact = self.runtime()
        invocation = event_api.prepare_delivery_invocation(
            EVENT | {"huddle_id": board["huddles"][0]["id"], "generation": board["huddles"][0]["generation"]}, operation="event",
            seat=None, contact_input=None, repo_root=Path(__file__).resolve().parent.parent, home=self.home)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        self.assertEqual(invocation.allowed_targets, tuple(caps["entries"]))
        self.assertEqual(invocation.writable_fds, ())
        self.assertEqual(set(invocation.fd_roles), {"entrypoint", "contacts_dir", "capabilities"})
        self.assertEqual(invocation.env["SHADOW_HUDDLE_BOARD_PATH"], str(extension.parent.parent / "board.json"))
        self.assertNotIn("PATH", invocation.env)
        self.assertEqual(invocation.argv[1:3], ("-I", "-B"))
        self.assertTrue(invocation.argv[3].startswith("/dev/fd/"))

    def test_stale_contact_and_symlink_parent_never_prepare_child(self):
        board, extension, contacts, client, caps, contact = self.runtime()
        contact["claim_keys"][0]["claim_revision"] += 1
        (contacts / (contact["instance_nonce"] + ".json")).write_text(json.dumps(contact))
        request = dict(event=EVENT | {"huddle_id": board["huddles"][0]["id"], "generation": board["huddles"][0]["generation"]}, operation="event",
                       seat=None, contact_input=None, repo_root=Path(__file__).resolve().parent.parent, home=self.home)
        self.assertIsNone(event_api.prepare_delivery_invocation(**request))
        original = extension.parent / "preserved-extension"
        extension.rename(original)
        extension.symlink_to(original, target_is_directory=True)
        self.assertIsNone(event_api.prepare_delivery_invocation(**request))

    def test_capability_duplicates_and_noncanonical_timestamps_are_refused(self):
        _, _, _, _, caps, _ = self.runtime()
        data = json.dumps(caps).replace('"entries":', '"entries": [], "entries":', 1).encode()
        with self.assertRaises(event_api.RunnerRefused):
            event_api.validate_capabilities(data)
        for stamp in ("2026-09-05 08:00:00Z", "20260905T080000Z"):
            with self.assertRaises(event_api.RunnerRefused):
                event_api._utc(stamp)

    def invocation(self, code):
        board, extension, contacts, client, caps, contact = self.runtime()
        entry = extension / "shadow-huddle-deliver-event.py"
        entry.write_text(code)
        event = EVENT | {"huddle_id": board["huddles"][0]["id"],
                         "generation": board["huddles"][0]["generation"]}
        invocation = event_api.prepare_delivery_invocation(
            event, operation="event", seat=None, contact_input=None,
            repo_root=Path(__file__).resolve().parent.parent, home=self.home)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        return invocation

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_seatbelt_profile_compiles_and_denies_escape(self):
        code = '''import os,sys,json
sys.path.insert(0, CORE_SCRIPTS)
import shadow_huddle_event as core
event = json.load(sys.stdin)
snapshot = core.read_huddle_snapshot(event["huddle_id"], event["generation"])
assert snapshot["generation"] == event["generation"]
try:
    open("/etc/passwd", "rb").read()
except PermissionError:
    print("[]")
else:
    raise AssertionError("sandbox allowed forbidden read")
'''
        invocation = self.invocation(code.replace("CORE_SCRIPTS", repr(str(Path(event_api.__file__).resolve().parent))))
        result = event_api._run_seatbelt(invocation, timeout_seconds=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertFalse(result.timed_out)
        self.assertEqual(json.loads(result.stdout), [])

    def run_probe(self, code):
        invocation = self.invocation(code)
        result = event_api._run_seatbelt(invocation, timeout_seconds=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertFalse(result.timed_out)
        self.assertFalse(result.output_limited)
        return invocation, result

    def test_profile_escaping_rejects_quote_backslash_newline_and_nul(self):
        for bad in ('/x"y', '/x\\y', '/x\ny', '/x\x00y', '/x*y', '/x?y', '/x[y]'):
            with self.subTest(path=bad), self.assertRaises(event_api.RunnerRefused):
                event_api._path_literal(bad)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_child_cannot_read_secret_env_or_sentinel_fd(self):
        path = self.home / "sentinel"
        path.write_bytes(b"private sentinel content")
        fd = os.open(path, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        os.set_inheritable(fd, True)
        code = '''import os,json,sys
assert sys.flags.isolated and sys.dont_write_bytecode
assert not any(k in os.environ for k in ("SECRET_TEST_KEY", "PYTHONPATH", "DYLD_INSERT_LIBRARIES", "HTTPS_PROXY", "PATH"))
try:
    os.fstat(SENTINEL_FD)
except OSError:
    print("[]")
else:
    raise AssertionError("inherited sentinel")
'''.replace("SENTINEL_FD", str(fd))
        with mock.patch.dict(os.environ, {"SECRET_TEST_KEY": "test-only-secret", "PYTHONPATH": str(self.home),
                                         "HTTPS_PROXY": "https://invalid.test"}):
            self.run_probe(code)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_child_cannot_write_board_journal_plan_or_repository(self):
        targets = [self.home / "journal", self.home / "PLAN.md", self.home / "repository-file"]
        for target in targets:
            target.write_bytes(b"unchanged")
        code = '''import os,json
targets = TARGETS + [os.environ["SHADOW_HUDDLE_BOARD_PATH"]]
for path in targets:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC)
    except PermissionError:
        continue
    else:
        os.close(fd)
        raise AssertionError("forbidden write")
print("[]")
'''.replace("TARGETS", repr(list(map(str, targets))))
        invocation = self.invocation(code)
        targets.append(Path(invocation.env["SHADOW_HUDDLE_BOARD_PATH"]))
        before = {path: path.read_bytes() for path in targets}
        result = event_api._run_seatbelt(invocation, timeout_seconds=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(before, {path: path.read_bytes() for path in targets})

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_child_cannot_import_mutation_modules_or_execute_arbitrary_binary(self):
        code = '''import sys,subprocess
sys.path.insert(0, CORE_SCRIPTS)
for name in ("shadow_root_board", "shadow_remote_claim", "shadow_plan_store"):
    try:
        __import__(name)
    except (ImportError, PermissionError):
        pass
    else:
        raise AssertionError("mutation module admitted")
for command in (("/bin/sh", "-c", "exit 0"), (SHADOW_BIN, "throw"), (SHADOW_BIN, "accept"), (SHADOW_BIN, "return")):
    try:
        subprocess.run(command, check=True)
    except (PermissionError, subprocess.CalledProcessError):
        pass
    else:
        raise AssertionError("unselected executable admitted")
print("[]")
'''.replace("CORE_SCRIPTS", repr(str(Path(event_api.__file__).resolve().parent)))
        code = code.replace("SHADOW_BIN", repr(str(Path(event_api.__file__).resolve().parent.parent / "bin/shadow")))
        self.run_probe(code)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_child_cannot_reach_unselected_executable_or_socket(self):
        import socket
        socket_path = str(self.home / "not-selected.sock")
        listener = socket.socket(socket.AF_UNIX)
        self.addCleanup(listener.close)
        listener.bind(socket_path)
        listener.listen(1)
        other = self.home / "other-native"
        shutil.copyfile("/usr/bin/true", other)
        other.chmod(0o700)
        code = '''import os,json,subprocess,socket
cap_fd = int(os.environ["SHADOW_HUDDLE_CAPABILITIES_FD"])
caps = json.loads(os.read(cap_fd, 16384))
subprocess.run([caps["entries"][0]["target"]], check=True)
try:
    subprocess.run([OTHER], check=True)
except PermissionError:
    pass
else:
    raise AssertionError("unselected executable")
sock = socket.socket(socket.AF_UNIX)
try:
    sock.connect(SOCKET_PATH)
except PermissionError:
    pass
else:
    raise AssertionError("unselected socket")
finally:
    sock.close()
print("[]")
'''.replace("OTHER", repr(str(other))).replace("SOCKET_PATH", repr(socket_path))
        invocation = self.invocation(code)
        caps_path = invocation.entry_path.parent / "shadow-huddle-provider-capabilities.json"
        caps = json.loads(caps_path.read_bytes())
        caps["entries"].append({"provider": "codex", "capability": "codex.app-server.turn-steer.v2",
                                "transport": "exec", "target": str(other)})
        caps_path.write_text(json.dumps(caps))
        invocation.close()
        invocation = event_api.prepare_delivery_invocation(json.loads(invocation.stdin),
            operation="event", seat=None, contact_input=None, repo_root=Path(event_api.__file__).resolve().parent.parent, home=self.home)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        self.assertEqual(len(invocation.allowed_targets), 1)
        result = event_api._run_seatbelt(invocation, timeout_seconds=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_generic_network_target_is_unsupported_before_launch(self):
        _, extension, _, _, caps, _ = self.runtime()
        caps["entries"][0].update(transport="network", target="https://example.invalid")
        with self.assertRaises(event_api.RunnerRefused):
            event_api.validate_capabilities(json.dumps(caps).encode())

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_event_cannot_read_unrelated_same_provider_contact(self):
        board, extension, contacts, client, caps, selected = self.runtime()
        unrelated_claim = dict(board["claims"][0], row="~cc33", owner="C",
                               claim_revision=4, write_scope=["b"])
        board["claims"].append(unrelated_claim)
        (extension.parent.parent / "board.json").write_text(json.dumps(board))
        unrelated = copy.deepcopy(selected)
        unrelated.update(seat="C", instance_nonce="123e4567-e89b-12d3-a456-426614174004",
            claim_keys=[{k: unrelated_claim[k] for k in ("entity", "row", "claim_revision", "owner")}])
        path = contacts / (unrelated["instance_nonce"] + ".json")
        path.write_text(json.dumps(unrelated))
        path.chmod(0o600)
        code = '''import os,json
directory = int(os.environ["SHADOW_HUDDLE_CONTACTS_DIR_FD"])
fd = os.open(SELECTED, os.O_RDONLY, dir_fd=directory)
assert json.loads(os.read(fd, 8192))["seat"] == "A"
os.close(fd)
for filename in (UNRELATED, ABSOLUTE):
    try:
        fd = os.open(filename, os.O_RDONLY, dir_fd=directory)
    except PermissionError:
        continue
    os.close(fd)
    raise AssertionError("unrelated same-provider contact was readable")
print("[]")
'''.replace("SELECTED", repr(selected["instance_nonce"] + ".json")).replace(
            "UNRELATED", repr(path.name)).replace("ABSOLUTE", repr(str(path)))
        (extension / "shadow-huddle-deliver-event.py").write_text(code)
        event = EVENT | {"huddle_id": board["huddles"][0]["id"], "generation": board["huddles"][0]["generation"]}
        invocation = event_api.prepare_delivery_invocation(event, operation="event", seat=None,
            contact_input=None, repo_root=Path(event_api.__file__).resolve().parent.parent, home=self.home)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        result = event_api._run_seatbelt(invocation, timeout_seconds=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_stdout_stderr_and_stdin_caps_refuse(self):
        for stream in (1, 2):
            with self.subTest(stream=stream):
                invocation = self.invocation(f'import os; os.write({stream}, b"x" * 16385)\n')
                result = event_api._launch_prepared_runner(invocation, timeout_seconds=2)
                self.assertEqual(result, {"available": False, "reason": "runner_refused"})
                invocation.close()
        with mock.patch.object(event_api, "_launch_prepared_runner") as launch:
            result = event_api.run_confined_contact_register(seat="A", stdin=b"x" * 16385,
                repo_root=Path(event_api.__file__).resolve().parent.parent, home=self.home)
            self.assertFalse(result["available"])
            launch.assert_not_called()

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_timeout_terminates_and_reaps_descendant_group(self):
        invocation = self.invocation('''import os,time
pid = os.fork()
if pid:
    print(os.getpid(), pid, flush=True)
time.sleep(10)
''')
        started = time.monotonic()
        result = event_api._run_seatbelt(invocation, timeout_seconds=0.2)
        self.assertTrue(result.timed_out, result.stderr.decode(errors="replace"))
        self.assertLess(time.monotonic() - started, 1.5)
        pids = tuple(map(int, result.stdout.split()))
        self.assertEqual(len(pids), 2)
        for pid in pids:
            for _ in range(30):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
            else:
                self.fail(f"owned descendant {pid} was not reaped")

    def test_contact_register_runner_binds_seat_bounded_stdin_and_operation_fds(self):
        _, _, _, _, _, stored = self.runtime()
        request = {key: value for key, value in stored.items()
                   if key not in {"seat", "registered_at", "refreshed_at", "expires_at"}}
        invocation = event_api.prepare_delivery_invocation(None, operation="contact_register", seat=stored["seat"],
            contact_input=json.dumps(request).encode(), repo_root=Path(event_api.__file__).resolve().parent.parent, home=self.home)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        self.assertEqual(invocation.argv[-2:], ("--seat", stored["seat"]))
        self.assertEqual(invocation.writable_fds, (invocation.fd_roles["contacts_dir"],))
        self.assertEqual(set(invocation.read_only_fds), {invocation.fd_roles["entrypoint"], invocation.fd_roles["capabilities"]})
        self.assertEqual(json.loads(invocation.stdin), request)
        self.assertNotIn("board", invocation.fd_roles)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_session_escape_is_denied_in_descendants_before_group_reaping(self):
        code = event_api._PROCESS_BOUNDARY_PROBE.replace('print("session-boundary-enforced")', '')
        code += '''
child = os.fork()
if not child:
    grandchild = os.fork()
    if not grandchild:
        try:
            os.setsid()
        except PermissionError:
            os._exit(0)
        os._exit(1)
    os._exit(0 if os.waitpid(grandchild, 0)[1] == 0 else 1)
assert os.waitpid(child, 0)[1] == 0
print("[]")
'''
        self.run_probe(code)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_unenforced_session_rule_refuses_before_optional_code_runs(self):
        invocation = self.invocation('raise AssertionError("optional code must not run")\n')
        original = event_api._seatbelt_profile
        with mock.patch.object(event_api, "_seatbelt_profile",
                               side_effect=lambda value: original(value).replace(event_api._SESSION_RULE, "")), \
             self.assertRaisesRegex(event_api.RunnerRefused, "process containment"):
            event_api._run_seatbelt(invocation, timeout_seconds=2)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_descriptor_close_is_idempotent_and_cannot_close_a_reused_fd(self):
        invocation = self.invocation('print("[]")\n')
        invocation.close()
        fd = os.open(self.home / "native-client", os.O_RDONLY)
        self.addCleanup(os.close, fd)
        invocation.close()
        os.fstat(fd)
        with self.assertRaisesRegex(event_api.RunnerRefused, "already closed"):
            event_api._run_seatbelt(invocation, timeout_seconds=2)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_selected_native_nonleader_inherits_session_denial(self):
        invocation = self.invocation('''import os,json,subprocess
cap = json.loads(os.read(int(os.environ["SHADOW_HUDDLE_CAPABILITIES_FD"]), 16384))
subprocess.run([cap["entries"][0]["target"]], check=True)
print("[]")
''')
        source = self.home / "session-probe.c"
        source.write_text('''#include <unistd.h>
#include <errno.h>
int main(void) {
    if (getpid() == getpgrp()) return 9;
    errno = 0;
    if (setsid() != -1 || errno != EPERM) return 10;
    errno = 0;
    if (setpgid(0, 0) != -1 || errno != EPERM) return 11;
    return 0;
}
''')
        target = Path(invocation.allowed_targets[0]["target"])
        invocation.close()
        compiled = subprocess.run(["/usr/bin/clang", str(source), "-o", str(target)],
                                  capture_output=True, timeout=30)
        self.assertEqual(compiled.returncode, 0, compiled.stderr.decode(errors="replace"))
        target.chmod(0o700)
        invocation = event_api.prepare_delivery_invocation(json.loads(invocation.stdin), operation="event", seat=None,
            contact_input=None, repo_root=Path(event_api.__file__).resolve().parent.parent, home=self.home)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        result = event_api._run_seatbelt(invocation, timeout_seconds=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        # A real negative control: without only the session rule, this same
        # nonleader native executable can setsid and returns 10 immediately.
        profile = event_api._seatbelt_profile(invocation).replace(event_api._SESSION_RULE, "")
        for role in ("entrypoint", "capabilities"):
            os.lseek(invocation.fd_roles[role], 0, os.SEEK_SET)
        with tempfile.NamedTemporaryFile(mode="w") as stream:
            stream.write(profile)
            stream.flush()
            escaped = event_api.run_bounded_pipes(("/usr/bin/sandbox-exec", "-f", stream.name, *invocation.argv),
                cwd=invocation.cwd, env=invocation.env, stdin=invocation.stdin,
                pass_fds=invocation.read_only_fds, timeout=2)
        self.assertNotEqual(escaped.returncode, 0)
        self.assertIn(b"exit status 10", escaped.stderr)

    def test_runner_rereads_atomic_board_replacement_and_exact_generation(self):
        board, extension, _, _, _, _ = self.runtime()
        path = extension.parent.parent / "board.json"
        old_inode = path.stat().st_ino
        old_event = EVENT | {"huddle_id": board["huddles"][0]["id"],
                             "generation": board["huddles"][0]["generation"]}
        board["revision"] += 1
        board["huddles"][0]["generation"] += 1
        replacement = path.with_suffix(".replacement")
        replacement.write_text(json.dumps(board))
        replacement.chmod(0o600)
        replacement.replace(path)
        self.assertNotEqual(path.stat().st_ino, old_inode)
        options = dict(operation="event", seat=None, contact_input=None,
                       repo_root=Path(event_api.__file__).resolve().parent.parent, home=self.home)
        self.assertIsNone(event_api.prepare_delivery_invocation(old_event, **options))
        current_event = old_event | {"generation": board["huddles"][0]["generation"]}
        invocation = event_api.prepare_delivery_invocation(current_event, **options)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        with mock.patch.dict(os.environ, {"SHADOW_HUDDLE_BOARD_PATH": str(path)}):
            self.assertEqual(event_api.read_huddle_snapshot(current_event["huddle_id"], current_event["generation"]),
                             board["huddles"][0])
            self.assertEqual(len(event_api.read_current_claims()), len(board["claims"]))

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof; unsupported host refusal is tested separately")
    def test_real_registration_can_write_only_contacts_and_reports_closed_receipt(self):
        board, extension, contacts, _, _, stored = self.runtime()
        code = '''import json,sys,os
request = json.load(sys.stdin)
directory = int(os.environ["SHADOW_HUDDLE_CONTACTS_DIR_FD"])
fd = os.open("runner-probe.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
os.write(fd, b"{}")
os.close(fd)
try:
    os.open(os.environ["SHADOW_HUDDLE_BOARD_PATH"], os.O_WRONLY | os.O_TRUNC)
except PermissionError:
    pass
else:
    raise AssertionError("registration gained board write")
print(json.dumps({"registered": True, **{key: request[key] for key in ("provider", "capability", "instance_nonce")}}))
'''
        (extension / "shadow-contact-register.py").write_text(code)
        request = {key: value for key, value in stored.items()
                   if key not in {"seat", "registered_at", "refreshed_at", "expires_at"}}
        path = extension.parent.parent / "board.json"
        before = path.read_bytes()
        result = event_api.run_confined_contact_register(seat=stored["seat"], stdin=json.dumps(request).encode(),
            repo_root=Path(event_api.__file__).resolve().parent.parent, home=self.home)
        self.assertEqual(result, {"available": True, "registered": True,
                                  **{key: request[key] for key in ("provider", "capability", "instance_nonce")}})
        self.assertEqual((contacts / "runner-probe.json").read_bytes(), b"{}")
        self.assertEqual(path.read_bytes(), before)
