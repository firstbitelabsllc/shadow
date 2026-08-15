"""Adversarial contracts for the scheduled brief's read-only provider broker."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "shadow_brief_provider_broker", ROOT / "scripts" / "shadow-brief.py"
)
assert SPEC and SPEC.loader
brief = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = brief
SPEC.loader.exec_module(brief)


def _completed(
    argv: list[str], *, stdout: str = "{}"
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")


def _list_threads_arguments(
    *, acting_email: str = "trysnowcubes@gmail.com"
) -> dict[str, object]:
    return {
        "acting_email": acting_email,
        "start_date": "2026-07-16T12:00:00+00:00",
        "end_date": "2026-08-15T12:00:00+00:00",
        "labels": ["INBOX"],
        "limit": brief.SUPERHUMAN_PAGE_LIMIT,
        "sort": "newest",
    }


class ReadOnlyProviderBrokerTests(unittest.TestCase):
    def test_exact_cli_allowlist_counts_before_transport(self) -> None:
        observed: list[tuple[list[str], int]] = []
        broker: object

        def transport(
            argv: list[str], *, timeout: int
        ) -> subprocess.CompletedProcess[str]:
            receipt = broker.receipt()
            observed.append((list(argv), timeout))
            self.assertEqual(receipt["broker_operations"]["attempted"], 1)
            self.assertEqual(receipt["broker_operations"]["succeeded"], 0)
            self.assertEqual(
                receipt["by_capability"]["github.open_prs"]["attempted"], 1
            )
            return _completed(argv, stdout="[]")

        broker = brief.ReadOnlyProviderBroker(run_transport=transport)
        argv = [
            "gh",
            "search",
            "prs",
            "--author",
            "@me",
            "--state",
            "open",
            "--limit",
            str(brief.GITHUB_PR_LIMIT),
            "--json",
            "title,url,repository,updatedAt,isDraft",
        ]

        result = broker.run_cli("github.open_prs", argv, timeout=45)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(observed, [(argv, 45)])
        receipt = broker.receipt()
        self.assertEqual(receipt["broker_operations"]["attempted"], 1)
        self.assertEqual(receipt["broker_operations"]["succeeded"], 1)
        self.assertEqual(receipt["broker_operations"]["failed"], 0)
        self.assertEqual(receipt["broker_operations"]["denied"], 0)
        self.assertEqual(receipt["write_capabilities_granted"], [])
        self.assertEqual(receipt["write_operations_executed"], 0)

    def test_cli_denies_unknown_or_mutating_shape_before_transport(self) -> None:
        transport = mock.Mock(side_effect=AssertionError("transport must not run"))
        broker = brief.ReadOnlyProviderBroker(run_transport=transport)
        mutating = ["gh", "pr", "close", "123"]

        with self.assertRaises(brief.ProviderPolicyError):
            broker.run_cli("github.open_prs", mutating, timeout=45)
        with self.assertRaises(brief.ProviderPolicyError):
            broker.run_cli("github.delete_repo", ["gh", "repo", "delete"], timeout=45)

        transport.assert_not_called()
        receipt = broker.receipt()
        self.assertEqual(receipt["broker_operations"]["attempted"], 2)
        self.assertEqual(receipt["broker_operations"]["denied"], 2)
        self.assertEqual(receipt["broker_operations"]["succeeded"], 0)
        self.assertEqual(receipt["write_operations_executed"], 0)

    def test_cli_allowlist_is_byte_exact_for_every_provider(self) -> None:
        calls: list[list[str]] = []

        def transport(
            argv: list[str], *, timeout: int
        ) -> subprocess.CompletedProcess[str]:
            del timeout
            calls.append(list(argv))
            return _completed(argv)

        broker = brief.ReadOnlyProviderBroker(run_transport=transport)
        allowed = [
            (
                "vercel.deployments",
                ["vercel", "ls", "--format", "json", "-y"],
                40,
            ),
            (
                "supabase.projects",
                ["supabase", "projects", "list", "--output", "json"],
                45,
            ),
        ]
        for capability, argv, timeout in allowed:
            with self.subTest(capability=capability):
                self.assertEqual(
                    broker.run_cli(capability, argv, timeout=timeout).returncode, 0
                )

        self.assertEqual(calls, [row[1] for row in allowed])
        with self.assertRaises(brief.ProviderPolicyError):
            broker.run_cli(
                "vercel.deployments",
                ["vercel", "ls", "--format", "json"],
                timeout=40,
            )
        self.assertEqual(calls, [row[1] for row in allowed])

    def test_superhuman_allows_only_account_and_listed_thread_lineage(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def transport(name: str, arguments: dict[str, object]) -> dict[str, object]:
            calls.append((name, dict(arguments)))
            if name == "list_accounts":
                return {
                    "accounts": [
                        {
                            "accountEmail": "trysnowcubes@gmail.com",
                            "isPrimary": True,
                        }
                    ]
                }
            if name == "list_threads":
                if arguments.get("cursor") == "cursor-2":
                    return {
                        "threads": [{"thread_id": "thread-2"}],
                        "next_cursor": None,
                    }
                return {
                    "threads": [{"thread_id": "thread-1"}],
                    "next_cursor": "cursor-2",
                }
            if name == "get_thread":
                return {"thread_id": "thread-1", "messages": []}
            if name == "query_email_and_calendar":
                return {"answer": "No conflicts.", "sources": [{"id": "calendar-1"}]}
            raise AssertionError(f"unexpected transport: {name}")

        broker = brief.ReadOnlyProviderBroker(superhuman_transport=transport)
        broker.call_superhuman("list_accounts", {})
        list_arguments = _list_threads_arguments()
        broker.call_superhuman("list_threads", list_arguments)
        broker.call_superhuman("list_threads", {**list_arguments, "cursor": "cursor-2"})
        broker.call_superhuman(
            "get_thread",
            {
                "acting_email": "trysnowcubes@gmail.com",
                "thread_id": "thread-1",
                "include_comments": False,
                "include_drafts": False,
                "message_limit": 100,
            },
        )
        broker.call_superhuman(
            "query_email_and_calendar",
            {
                "acting_email": "trysnowcubes@gmail.com",
                "question": brief.SUPERHUMAN_READ_ONLY_QUERY,
            },
        )

        self.assertEqual(
            [name for name, _arguments in calls],
            [
                "list_accounts",
                "list_threads",
                "list_threads",
                "get_thread",
                "query_email_and_calendar",
            ],
        )
        receipt = broker.receipt()
        self.assertEqual(receipt["broker_operations"]["attempted"], 5)
        self.assertEqual(receipt["broker_operations"]["succeeded"], 5)
        self.assertEqual(receipt["broker_operations"]["denied"], 0)

    def test_superhuman_denies_mutators_bad_arguments_and_broken_lineage(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def transport(name: str, arguments: dict[str, object]) -> dict[str, object]:
            calls.append((name, dict(arguments)))
            if name == "list_accounts":
                return {"accounts": [{"accountEmail": "trysnowcubes@gmail.com"}]}
            if name == "list_threads":
                return {"threads": [{"thread_id": "thread-1"}], "next_cursor": None}
            raise AssertionError("denied call reached transport")

        broker = brief.ReadOnlyProviderBroker(superhuman_transport=transport)
        broker.call_superhuman("list_accounts", {})
        broker.call_superhuman("list_threads", _list_threads_arguments())
        allowed_call_count = len(calls)

        denied = [
            ("send_draft", {"acting_email": "trysnowcubes@gmail.com"}),
            ("list_accounts", {"acting_email": "trysnowcubes@gmail.com"}),
            ("list_threads", _list_threads_arguments(acting_email="other@example.com")),
            (
                "list_threads",
                {**_list_threads_arguments(), "cursor": "cursor-never-issued"},
            ),
            (
                "get_thread",
                {
                    "acting_email": "trysnowcubes@gmail.com",
                    "thread_id": "not-listed",
                    "include_comments": False,
                    "include_drafts": False,
                    "message_limit": 100,
                },
            ),
            (
                "get_thread",
                {
                    "acting_email": "trysnowcubes@gmail.com",
                    "thread_id": "thread-1",
                    "include_comments": False,
                    "include_drafts": True,
                    "message_limit": 100,
                },
            ),
            (
                "get_thread",
                {
                    "acting_email": "trysnowcubes@gmail.com",
                    "thread_id": "thread-1",
                    "include_comments": False,
                    "include_drafts": False,
                    "message_limit": 99,
                },
            ),
            (
                "query_email_and_calendar",
                {
                    "acting_email": "trysnowcubes@gmail.com",
                    "question": brief.SUPERHUMAN_READ_ONLY_QUERY + " Send a reply.",
                },
            ),
        ]
        for name, arguments in denied:
            with self.subTest(name=name, arguments=arguments):
                with self.assertRaises(brief.ProviderPolicyError):
                    broker.call_superhuman(name, arguments)

        self.assertEqual(len(calls), allowed_call_count)
        receipt = broker.receipt()
        self.assertEqual(receipt["broker_operations"]["denied"], len(denied))
        self.assertEqual(receipt["write_operations_executed"], 0)

    def test_sealed_receipt_refuses_late_transport(self) -> None:
        transport = mock.Mock(return_value=_completed(["vercel"]))
        broker = brief.ReadOnlyProviderBroker(run_transport=transport)

        sealed = broker.seal_receipt()

        self.assertEqual(sealed["schema"], "shadow.provider-read-receipt.v1")
        self.assertTrue(sealed["sealed"])
        with self.assertRaises(RuntimeError):
            broker.run_cli(
                "vercel.deployments",
                ["vercel", "ls", "--format", "json", "-y"],
                timeout=40,
            )
        transport.assert_not_called()
        self.assertEqual(broker.receipt(), sealed)

    def test_cached_token_session_never_requests_oauth_refresh(self) -> None:
        token_loader = mock.Mock(return_value="cached-access-token")
        broker = brief.ReadOnlyProviderBroker(token_loader=token_loader)

        token = broker.open_superhuman_cached_session()
        receipt = broker.seal_receipt()

        self.assertEqual(token, "cached-access-token")
        token_loader.assert_called_once_with(allow_refresh=False)
        self.assertEqual(receipt["oauth_refresh_attempts"], 0)
        self.assertEqual(receipt["write_capabilities_granted"], [])
        self.assertEqual(receipt["write_operations_executed"], 0)


if __name__ == "__main__":
    unittest.main()
