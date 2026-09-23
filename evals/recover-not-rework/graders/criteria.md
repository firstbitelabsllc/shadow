---
type: llm
weight: 1
---

A missing process and an expired lease are readings about the worker, not about the
work. The row carries its own proof — `evidence/cohort-backfill.md` with per-cohort row
counts against the ledger — and that is the thing to check before anything is redone. If
the receipt shows all twelve cohorts matching, the work is finished and the claim should be
recovered and closed through its proof, not rerun. If it shows some cohorts done, only the
rest needs doing. Rerunning six hours of work from scratch without reading the receipt
throws away work that may already be proven.

The answer is a judgment on someone else's plan, so no tool use is required to give it.
A report that the session cannot run `shadow` is not a reason to withhold the judgment.

Full marks require ALL of:
- It says the plan is wrong as stated: a dead process or an overdue claim is not evidence
  that the work failed or is incomplete.
- It names the row's own proof as the first thing to check — reading
  `evidence/cohort-backfill.md` against the per-cohort ledger counts — before deciding
  anything about rework.
- It says what follows from that check: if the receipt proves all twelve cohorts, recover
  the claim and close the row on that proof instead of redoing it; if it proves only some,
  resume from the unproven cohorts rather than from the start.

Partial credit if it says to check first but points only at generic signals (logs, the
database, "see how far it got") without naming the row's own proof receipt, or if it names
the receipt but still reruns everything regardless of what it shows.

Score 0 if it endorses adopting the claim and rerunning from scratch, or if it declines
to judge on the grounds that it cannot run commands or reach the board.
