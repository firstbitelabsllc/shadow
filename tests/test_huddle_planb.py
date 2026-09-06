"""Plan-B contacts and delivery: closed registration, bounded envelopes,
exact-target adapters. The confined-child paths are Darwin Seatbelt proofs;
unsupported-host refusal and the pure model surfaces are tested everywhere.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shadow_contacts as contacts
import shadow_delivery as delivery
import shadow_huddle_event as event_api
from tests.test_huddle_event import EVENT, HuddleEventTests

SOURCE = Path(event_api.__file__).resolve().parent.parent
DIST = SOURCE / "distribution" / "huddle-delivery"
NOW = datetime.now(timezone.utc).replace(microsecond=0)
SEAT = "A"


class PlanBDeliveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()

    def runtime(self):
        """Reuse the shipped event-suite fixture verbatim (board, runtime, contact)."""
        return HuddleEventTests.runtime(SimpleNamespace(home=self.home,
                                                        addCleanup=self.addCleanup))

    def install_real_entrypoint(self, extension, name):
        target = extension / name
        target.write_bytes((DIST / name).read_bytes())
        target.chmod(0o600)
        return target

    def request(self, claim, *, nonce="123e4567-e89b-12d3-a456-426614174005"):
        return {"schema": contacts.CONTACT_SCHEMA, "instance_nonce": nonce,
                "provider": "cmux", "capability": "cmux.surface-send.v1",
                "endpoint": {"surface_uuid": "123e4567-e89b-12d3-a456-426614174002"},
                "claim_keys": [{key: claim[key]
                                for key in ("entity", "row", "claim_revision", "owner")}]}

    def compile_helper(self, name, *, exit_code=0, sleeper=False):
        body = "#include <stdlib.h>\n#include <unistd.h>\nint main(void) {\n"
        if sleeper:
            body += "    sleep(5);\n"
        body += f"    return {exit_code};\n}}\n"
        source = self.home / f"{name}.c"
        source.write_text(body)
        binary = self.home / name
        compiled = subprocess.run(["/usr/bin/clang", str(source), "-o", str(binary)],
                                  capture_output=True, timeout=30)
        self.assertEqual(compiled.returncode, 0, compiled.stderr.decode(errors="replace"))
        binary.chmod(0o700)
        return binary

    # -- pure model surfaces (host-agnostic) --------------------------------

    def test_registration_lease_is_closed_and_canonical(self):
        stored = contacts.stored_registration(self.request(
            {"entity": "a" * 64, "row": "~aa11", "claim_revision": 1, "owner": SEAT}),
            seat=SEAT, now=NOW)
        self.assertEqual(set(stored), contacts.STORED_FIELDS)
        self.assertEqual(stored["registered_at"], stored["refreshed_at"])
        self.assertEqual(contacts.parse_canonical_utc(stored["expires_at"])
                         - contacts.parse_canonical_utc(stored["refreshed_at"]),
                         timedelta(minutes=10))
        for bad in ("2026-09-06 08:00:00Z", "2026-09-06T08:00:00.5Z", "nonsense"):
            with self.subTest(stamp=bad), self.assertRaises(contacts.ContactRefused):
                contacts.parse_canonical_utc(bad)

    def test_capability_pair_requires_exactly_one_armed_entry(self):
        entry = {"provider": "cmux", "capability": "c.v1", "transport": "exec",
                 "target": "/x"}
        self.assertEqual(contacts.capability_pair("cmux", "c.v1", [entry]), entry)
        for entries in ([], [entry, dict(entry)]):
            with self.subTest(entries=entries), self.assertRaises(contacts.ContactRefused):
                contacts.capability_pair("cmux", "c.v1", entries)

    def test_write_contact_is_exclusive_bounded_and_canonical(self):
        request = self.request({"entity": "a" * 64, "row": "~aa11",
                                "claim_revision": 1, "owner": SEAT})
        stored = contacts.stored_registration(request, seat=SEAT, now=NOW)
        fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        name = contacts.write_contact(fd, stored, now=NOW)
        self.assertEqual(name, stored["instance_nonce"] + ".json")
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        self.assertTrue(stat.S_ISREG(info.st_mode))
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            contacts.write_contact(fd, stored, now=NOW)
        oversized = dict(stored, endpoint={"surface_uuid": "0" * 9000})
        with self.assertRaises(contacts.ContactRefused):
            contacts.write_contact(fd, oversized, now=NOW)
        expired = dict(stored, expires_at="2020-01-01T00:00:00Z")
        with self.assertRaises(contacts.ContactRefused):
            contacts.write_contact(fd, expired, now=NOW)

    def test_child_validator_agrees_with_parent_validator(self):
        claim = {"entity": "a" * 64, "row": "~aa11", "claim_revision": 1, "owner": SEAT}
        current = {tuple(claim[k] for k in ("entity", "row", "claim_revision", "owner")): {}}
        valid_cmux = self.request(claim)
        cases = [
            (valid_cmux, True),
            (dict(valid_cmux, provider="codex",
                  endpoint={"thread_id": "t1", "turn_id": "u2"}), True),
            (dict(valid_cmux, schema="shadow.other.v1"), False),
            (valid_cmux | {"extra": 1}, False),
            (dict(valid_cmux, instance_nonce="not-a-uuid"), False),
            (dict(valid_cmux, provider="smtp"), False),
            (dict(valid_cmux, capability="bad space"), False),
            (dict(valid_cmux, endpoint={"surface_uuid": "123"}), False),
            (dict(valid_cmux, endpoint={"thread_id": "t1"}), False),
            (dict(valid_cmux, endpoint={"surface_uuid": ""}), False),
            (dict(valid_cmux, endpoint={"surface_uuid": "x" * 600}), False),
            (dict(valid_cmux, endpoint={"surface_uuid": "line\nbreak"}), False),
            (dict(valid_cmux, endpoint={"surface_uuid": "sk-antnottoken12345"}), False),
            (dict(valid_cmux, provider="grok",
                  endpoint={"endpoint_uri": "https://x.invalid"}), False),
            (dict(valid_cmux, claim_keys="nope"), False),
            (dict(valid_cmux, claim_keys=[dict(claim, claim_revision=index + 1)
                                          for index in range(65)]), False),
            (dict(valid_cmux, claim_keys=[dict(claim, owner="B")]), False),
            (dict(valid_cmux, claim_keys=[dict(claim, claim_revision=-1)]), False),
            (dict(valid_cmux, claim_keys=[claim, claim]), False),
        ]
        for index, (request, expected) in enumerate(cases):
            with self.subTest(case=index):
                try:
                    contacts.validate_registration(request, seat=SEAT)
                    child_ok = True
                except contacts.ContactRefused:
                    child_ok = False
                try:
                    event_api._contact(request, seat=SEAT, current=current,
                                       stored=False, now=NOW)
                    parent_ok = True
                except event_api.RunnerRefused:
                    parent_ok = False
                self.assertEqual(child_ok, parent_ok)
                self.assertEqual(child_ok, expected)

    def test_child_capability_reader_agrees_with_parent_validator(self):
        # Structural drift guard: the parent resolves and identity-binds
        # targets (the confined child must not re-open paths), so agreement
        # is asserted on everything except target resolution — structure,
        # TTL, duplicates — plus the child-only digest binding.
        client = str(self.home / "drift-client")
        client_bytes = b"\xcf\xfa\xed\xfe" + b"\0" * 64
        Path(client).write_bytes(client_bytes)
        Path(client).chmod(0o700)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
        def descriptor(entries, generated=None):
            return json.dumps({"schema": "shadow.huddle-provider-capabilities.v1",
                               "generated_at": generated or stamp(now),
                               "expires_at": stamp(now + timedelta(minutes=10)),
                               "entries": entries}).encode()
        good = [{"provider": "cmux", "capability": "cmux.surface-send.v1",
                 "transport": "exec", "target": client}]
        digests = [hashlib.sha256(delivery.canonical_bytes(entry)).hexdigest()
                   for entry in good]
        # Both validators refuse: structural / TTL violations.
        for index, (raw, case_digests) in enumerate([
                (descriptor(good + good[:1]), digests),
                (descriptor([dict(good[0], transport="network",
                                  target="https://x.invalid")]), digests),
                (descriptor([dict(good[0], capability="bad space")]), digests),
                (descriptor([dict(good[0], provider="smtp")]), digests),
                (descriptor(good, generated=stamp(now + timedelta(minutes=1))), digests),
                (descriptor(good, generated=stamp(now - timedelta(minutes=30))), digests)]):
            with self.subTest(both_refuse=index):
                with self.assertRaises(contacts.ContactRefused):
                    delivery.read_armed_entries(raw, case_digests, now=now)
                with self.assertRaises(event_api.RunnerRefused):
                    event_api.validate_capabilities(raw, now=now)
        # Child-only refusals: digest binding is the parent's arming record;
        # the parent validator legitimately accepts an unbound descriptor.
        with self.subTest(child_only="not-armed"):
            with self.assertRaises(contacts.ContactRefused):
                delivery.read_armed_entries(descriptor(good), [], now=now)
            event_api.validate_capabilities(descriptor(good), now=now)

    def test_idempotency_key_matches_pinned_golden_vector(self):
        # The receipt key material is pinned: any change to which fields feed
        # the key must fail here, not silently re-key every receipt.
        self.assertEqual(
            delivery.idempotency_key(
                provider="cmux", capability="cmux.surface-send.v1",
                instance_nonce="123e4567-e89b-12d3-a456-426614174003",
                huddle_id="hdl_1234abcd", generation=3, event="huddle_changed",
                endpoint={"surface_uuid": "123e4567-e89b-12d3-a456-426614174002"}),
            "a7a75916bf131283d44a74ff1ee2b8ab40296463bb3d5f05dba4a0ef08356747")

    def test_mismatched_nonce_filename_is_skipped_by_delivery(self):
        # A record swapped at a selected path whose content claims a different
        # nonce is skipped by the child's filename/nonce coherence guard.
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        huddle = board["huddles"][0]
        event = EVENT | {"huddle_id": huddle["id"], "generation": huddle["generation"]}
        entries = event_api.validate_capabilities(json.dumps(caps).encode())
        fd = os.open(contacts_dir, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        swapped = dict(stored, instance_nonce="123e4567-e89b-12d3-a456-426614174007")
        (contacts_dir / (stored["instance_nonce"] + ".json")).write_text(
            json.dumps(swapped))
        receipts = delivery.deliver(
            event=event, huddle=huddle,
            current_claims=event_api._current_claims(board),
            capability_entries=entries, contacts_dir_fd=fd,
            now=datetime.now(timezone.utc), deadline_seconds=1.0)
        self.assertEqual(receipts, [])

    def test_contact_directory_beyond_selection_bound_is_refused(self):
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        huddle = board["huddles"][0]
        event = EVENT | {"huddle_id": huddle["id"], "generation": huddle["generation"]}
        entries = event_api.validate_capabilities(json.dumps(caps).encode())
        fd = os.open(contacts_dir, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        for index in range(257):
            name = "%08d-1111-4222-8333-444444444444.json" % index
            (contacts_dir / name).write_text("{}")
        with self.assertRaises(contacts.ContactRefused):
            delivery.deliver(
                event=event, huddle=huddle,
                current_claims=event_api._current_claims(board),
                capability_entries=entries, contacts_dir_fd=fd,
                now=datetime.now(timezone.utc), deadline_seconds=1.0)

    def test_handoff_successor_is_eligible_like_the_parent(self):
        claim = {"entity": "a" * 64, "row": "~aa11", "claim_revision": 1,
                 "owner": "A", "claimed_at": "2026-09-06T00:00:00Z"}
        successor = dict(claim, owner="B")
        huddle = {"id": "hdl_1234abcd", "generation": 3, "claims": [claim],
                  "replacements": [],
                  "resolution": {"handoff": {"successor_claim": successor}}}
        import shadow_board_schema as board_schema
        expected = board_schema._claim_key(
            board_schema._terminal_ref(huddle, successor))
        self.assertIn(expected, delivery.eligible_claim_keys(huddle))

    def test_install_script_refuses_symlinked_runtime(self):
        (self.home / "elsewhere").mkdir()
        (self.home / "runtime").mkdir()
        (self.home / "runtime" / "huddle-delivery").symlink_to(self.home / "elsewhere")
        env = dict(os.environ, SHADOW_HOME=str(self.home))
        result = subprocess.run(["/bin/sh", str(DIST / "install-runtime.sh")],
                                env=env, capture_output=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr.decode(errors="replace"))

    def test_envelope_is_closed_bounded_deterministic_and_private(self):
        endpoint = {"surface_uuid": str(uuid.uuid4())}
        envelope = delivery.build_envelope(
            event=EVENT, provider="cmux", capability="cmux.surface-send.v1",
            instance_nonce=str(uuid.uuid4()), endpoint=endpoint, now=NOW)
        self.assertEqual(set(envelope), delivery.ENVELOPE_FIELDS)
        raw = delivery.canonical_bytes(envelope)
        self.assertLessEqual(len(raw), delivery.MAX_ENVELOPE_BYTES)
        for private in (b"board", b"claim", b"PLAN", SEAT.encode(), b"/Users"):
            self.assertNotIn(private, raw)
        self.assertIn(endpoint["surface_uuid"].encode(), raw)
        key = delivery.idempotency_key(
            provider="cmux", capability="c", instance_nonce="n",
            huddle_id="hdl_00000001", generation=1, event="huddle_changed",
            endpoint=endpoint)
        self.assertRegex(key, r"[0-9a-f]{64}")
        again = delivery.idempotency_key(
            provider="cmux", capability="c", instance_nonce="n",
            huddle_id="hdl_00000001", generation=1, event="huddle_changed",
            endpoint=endpoint)
        self.assertEqual(key, again)
        changed = delivery.idempotency_key(
            provider="cmux", capability="c", instance_nonce="n",
            huddle_id="hdl_00000001", generation=1, event="huddle_changed",
            endpoint={"surface_uuid": str(uuid.uuid4())})
        self.assertNotEqual(key, changed)

    def test_attempt_classifies_the_documented_exit_protocol(self):
        def script(body, name="probe.sh"):
            path = self.home / name
            path.write_text("#!/bin/sh\n" + body)
            path.chmod(0o700)
            return str(path)
        self.assertEqual(delivery.attempt(script("exit 0", "a.sh"), {}, deadline_seconds=1), "accepted")
        self.assertEqual(delivery.attempt(script("exit 1", "b.sh"), {}, deadline_seconds=1), "refused")
        self.assertEqual(delivery.attempt(script("exit 2", "c.sh"), {}, deadline_seconds=1), "unsupported")
        self.assertEqual(delivery.attempt(script("exit 3", "d.sh"), {}, deadline_seconds=1), "unhealthy")
        self.assertEqual(delivery.attempt(script("exit 7", "e.sh"), {}, deadline_seconds=1), "unhealthy")
        self.assertEqual(delivery.attempt(script("sleep 5", "f.sh"), {}, deadline_seconds=0.1), "unhealthy")
        self.assertEqual(delivery.attempt(str(self.home / "missing-binary"), {}, deadline_seconds=1), "unhealthy")

    def test_install_script_installs_bounded_runtime_entries(self):
        env = dict(os.environ, SHADOW_HOME=str(self.home))
        for attempt_index in range(2):
            result = subprocess.run(["/bin/sh", str(DIST / "install-runtime.sh")],
                                    env=env, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        runtime = self.home / "runtime" / "huddle-delivery"
        self.assertTrue(runtime.is_dir())
        self.assertEqual(stat.S_IMODE(runtime.stat().st_mode), 0o700)
        for name in ("shadow-huddle-deliver-event.py", "shadow-contact-register.py"):
            path = runtime / name
            info = path.stat()
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
            self.assertEqual(info.st_nlink, 1)
            self.assertLess(info.st_size, 256 * 1024)
        self.assertEqual(stat.S_IMODE((self.home / "contacts").stat().st_mode), 0o700)

    # -- confined child proofs (Darwin Seatbelt) ---------------------------

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof")
    def test_real_registration_stores_closed_expiring_contact(self):
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        self.install_real_entrypoint(extension, "shadow-contact-register.py")
        claim = board["claims"][0]
        request = self.request(claim)
        result = event_api.run_confined_contact_register(
            seat=SEAT, stdin=json.dumps(request).encode(),
            repo_root=SOURCE, home=self.home)
        self.assertEqual(result, {"available": True, "registered": True,
                                  "provider": request["provider"],
                                  "capability": request["capability"],
                                  "instance_nonce": request["instance_nonce"]})
        path = contacts_dir / (request["instance_nonce"] + ".json")
        payload = json.loads(path.read_bytes())
        self.assertEqual(set(payload), contacts.STORED_FIELDS)
        self.assertEqual(payload["seat"], SEAT)
        registered = contacts.parse_canonical_utc(payload["registered_at"])
        refreshed = contacts.parse_canonical_utc(payload["refreshed_at"])
        expires = contacts.parse_canonical_utc(payload["expires_at"])
        self.assertEqual(registered, refreshed)
        self.assertEqual(expires - refreshed, timedelta(minutes=10))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof")
    def test_duplicate_registration_refuses_and_preserves_the_first(self):
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        self.install_real_entrypoint(extension, "shadow-contact-register.py")
        claim = board["claims"][0]
        request = self.request(claim)
        first = event_api.run_confined_contact_register(
            seat=SEAT, stdin=json.dumps(request).encode(),
            repo_root=SOURCE, home=self.home)
        self.assertTrue(first["available"])
        path = contacts_dir / (request["instance_nonce"] + ".json")
        before = path.read_bytes()
        second = event_api.run_confined_contact_register(
            seat=SEAT, stdin=json.dumps(request).encode(),
            repo_root=SOURCE, home=self.home)
        self.assertEqual(second, {"available": False, "reason": "runner_refused"})
        self.assertEqual(path.read_bytes(), before)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof")
    def test_registration_without_an_armed_pair_is_absent(self):
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        request = self.request(board["claims"][0],
                               nonce="123e4567-e89b-12d3-a456-426614174006")
        request["capability"] = "cmux.other-send.v9"
        result = event_api.run_confined_contact_register(
            seat=SEAT, stdin=json.dumps(request).encode(),
            repo_root=SOURCE, home=self.home)
        self.assertEqual(result, {"available": False,
                                  "reason": "optional delivery adapter absent"})
        self.assertEqual([entry.name for entry in os.scandir(contacts_dir)],
                         [stored["instance_nonce"] + ".json"])

    def run_real_delivery(self, board, extension):
        """Install the real event entrypoint, prepare, and run under the seatbelt."""
        self.install_real_entrypoint(extension, "shadow-huddle-deliver-event.py")
        huddle = board["huddles"][0]
        event = EVENT | {"huddle_id": huddle["id"], "generation": huddle["generation"]}
        invocation = event_api.prepare_delivery_invocation(
            event, operation="event", seat=None, contact_input=None,
            repo_root=SOURCE, home=self.home)
        self.assertIsNotNone(invocation)
        self.addCleanup(invocation.close)
        result = event_api._run_seatbelt(invocation, timeout_seconds=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertFalse(result.timed_out)
        return json.loads(result.stdout), event

    def deliver_via_seatbelt(self):
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        receipts, event = self.run_real_delivery(board, extension)
        return receipts, stored, event, caps, client

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof")
    def test_real_delivery_accepts_with_deterministic_idempotency(self):
        receipts, stored, event, caps, client = self.deliver_via_seatbelt()
        expected_key = delivery.idempotency_key(
            provider=stored["provider"], capability=stored["capability"],
            instance_nonce=stored["instance_nonce"], huddle_id=event["huddle_id"],
            generation=event["generation"], event=event["event"],
            endpoint=stored["endpoint"])
        self.assertEqual(len(receipts), 1)
        receipt = receipts[0]
        self.assertEqual(receipt["adapter"], "cmux")
        self.assertEqual(receipt["huddle_id"], event["huddle_id"])
        self.assertEqual(receipt["idempotency_key"], expected_key)
        self.assertEqual(receipt["contact_nonce"], stored["instance_nonce"])
        self.assertRegex(receipt["attempted_at"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        self.assertEqual(receipt["outcome"], "accepted")

    def test_delivery_skips_expired_or_foreign_contacts_in_process(self):
        # The confined parent refuses an expired or stale contact before the
        # child runs (shipped prepare behavior); the child-side skip is the
        # second line of defense and is exercised directly here.
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        huddle = board["huddles"][0]
        event = EVENT | {"huddle_id": huddle["id"], "generation": huddle["generation"]}
        entries = event_api.validate_capabilities(json.dumps(caps).encode())
        fd = os.open(contacts_dir, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        now = datetime.now(timezone.utc)
        path = contacts_dir / (stored["instance_nonce"] + ".json")
        expired = dict(stored, expires_at="2020-01-01T00:00:00Z")
        path.write_text(json.dumps(expired))
        path.chmod(0o600)
        receipts = delivery.deliver(
            event=event, huddle=huddle,
            current_claims=event_api._current_claims(board),
            capability_entries=entries, contacts_dir_fd=fd,
            now=now, deadline_seconds=1.0)
        self.assertEqual(receipts, [])
        # A second valid, current contact IS attempted (selection breadth is
        # the parent's kernel-enforced preselection); but a contact whose
        # claim keys are no longer current on the child's own board re-read
        # must be skipped by the child's currency guard.
        stale_claim = dict(stored["claim_keys"][0], claim_revision=99)
        second = dict(stored, instance_nonce="123e4567-e89b-12d3-a456-426614174009",
                      claim_keys=[stale_claim])
        second_path = contacts_dir / (second["instance_nonce"] + ".json")
        second_path.write_text(json.dumps(second))
        second_path.chmod(0o600)
        receipts = delivery.deliver(
            event=event, huddle=huddle,
            current_claims=event_api._current_claims(board),
            capability_entries=entries, contacts_dir_fd=fd,
            now=now, deadline_seconds=1.0)
        self.assertEqual([r["contact_nonce"] for r in receipts], [])

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof")
    def test_delivery_classifies_real_target_exits(self):
        # Exit codes 1/2/3 are classified from real compiled targets. The
        # slow-target timeout outcome is asserted in-process by
        # test_attempt_classifies_the_documented_exit_protocol: a target that
        # burns its whole attempt budget leaves no headroom inside the
        # parent's two-second runner window, so the confined path ends as an
        # honest runner_timeout rather than a classified receipt.
        for exit_code, expected in ((1, "refused"), (2, "unsupported"), (3, "unhealthy")):
            with self.subTest(exit_code=exit_code):
                board, extension, contacts_dir, client, caps, stored = self.runtime()
                binary = self.compile_helper(f"helper-{exit_code}", exit_code=exit_code)
                caps["entries"][0]["target"] = str(binary)
                caps_path = extension / "shadow-huddle-provider-capabilities.json"
                caps_path.write_text(json.dumps(caps))
                caps_path.chmod(0o600)
                receipts, _ = self.run_real_delivery(board, extension)
                self.assertEqual([r["outcome"] for r in receipts], [expected])

    @unittest.skipUnless(sys.platform == "darwin", "Darwin Seatbelt proof")
    def test_in_process_delivery_rechecks_currency_and_lease(self):
        board, extension, contacts_dir, client, caps, stored = self.runtime()
        huddle = board["huddles"][0]
        event = EVENT | {"huddle_id": huddle["id"], "generation": huddle["generation"]}
        entries = event_api.validate_capabilities(json.dumps(caps).encode())
        fd = os.open(contacts_dir, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        receipts = delivery.deliver(
            event=event, huddle=huddle,
            current_claims=event_api._current_claims(board),
            capability_entries=entries, contacts_dir_fd=fd,
            now=datetime.now(timezone.utc), deadline_seconds=1.0)
        self.assertEqual([r["outcome"] for r in receipts], ["accepted"])
        stale_board = json.loads(json.dumps(board))
        for claim in stale_board["claims"]:
            claim["claim_revision"] += 1
        receipts = delivery.deliver(
            event=event, huddle=huddle,
            current_claims=event_api._current_claims(stale_board),
            capability_entries=entries, contacts_dir_fd=fd,
            now=datetime.now(timezone.utc), deadline_seconds=1.0)
        self.assertEqual(receipts, [])


if __name__ == "__main__":
    unittest.main()
