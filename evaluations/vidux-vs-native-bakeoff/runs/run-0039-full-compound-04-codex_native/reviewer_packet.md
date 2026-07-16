# Blinded Reviewer Packet

Run: run-0039-full-compound-04-codex_native
Fixture: full-compound-04

## Visible proof output
visible_check PASS


## Diff summary
diff --git a/PLAN.md b/PLAN.md
index 2b124cf..13d3598 100644
--- a/PLAN.md
+++ b/PLAN.md
@@ -1,5 +1,5 @@
 # Receipt Reconciliation
 
 ## Tasks
-- [pending] Reconcile subtotal, tax, tip, and service charge without losing remainder cents.
+- [completed] Reconcile subtotal, tax, tip, and service charge without losing remainder cents.
   Accept: `python3 checks/visible_check.py` exits 0.
diff --git a/mammothsplit/money.py b/mammothsplit/money.py
index 2119f86..71e9cbe 100644
--- a/mammothsplit/money.py
+++ b/mammothsplit/money.py
@@ -4,5 +4,10 @@ def cents(amount: str) -> int:
     return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
 
 def allocate(total_cents: int, weights: list[int]) -> list[int]:
+    if not weights:
+        return []
     base = [int(total_cents * weight / sum(weights)) for weight in weights]
+    remainder = total_cents - sum(base)
+    for idx in range(remainder):
+        base[idx % len(base)] += 1
     return base


## Final claim
ARM=codex_native
fixture_id=full-compound-04
mechanical_claim=pass
proof_commands=python3 checks/visible_check.py -> rc 0
real_surface_proof=n/a
known_issues=success_path


## Mechanical outcome
pass