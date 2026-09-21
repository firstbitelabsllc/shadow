---
type: llm
weight: 1
---

Parking is a write, not a shrug. A correctly parked item carries an exact, checkable wake
condition, has released its claim, and has left its seat working on something else. The
park shown here fails all three, and the answer is asked only to judge it — no tool use is
required to answer, so a blocker report is not a reason to withhold the judgment.

Full marks require the answer to identify ALL THREE defects:
- The wake is not checkable. "When the owner has time to sort out the store credentials"
  names no condition anyone can test. A usable wake names the thing that must exist or
  arrive — the store credential itself, or the person supplying it — so that its arrival
  is observable rather than a matter of opinion.
- The claim is still held. `~aa11` is parked but `demo-seat` still owns it, so the item is
  blocked and owned at once and no other seat can pick it up.
- The seat then stopped. A park is supposed to free the seat to continue on reachable work
  — `~bb22` is owner-gated, but `~cc33` is reachable — and this seat has logged nothing
  since.

Partial credit for identifying one or two of the three.

Score 0 if the answer says the park looks fine, if it only restates that `~aa11` is
blocked without finding a defect in how it was parked, or if it declines to judge on the
grounds that it cannot run commands or reach the board.
