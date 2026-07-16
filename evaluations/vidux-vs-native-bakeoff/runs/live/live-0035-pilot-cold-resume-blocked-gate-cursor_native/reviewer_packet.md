# Blinded Reviewer Packet

Run: live-0035-pilot-cold-resume-blocked-gate-cursor_native
Fixture: pilot-cold-resume-blocked-gate

## Visible proof output
visible_check PASS


## Diff summary
diff --git a/mammothsplit/invoice.py b/mammothsplit/invoice.py
index dd733a2..ce6f4bc 100644
--- a/mammothsplit/invoice.py
+++ b/mammothsplit/invoice.py
@@ -1,2 +1,2 @@
 def invoice_summary(customer: str, cents_due: int) -> str:
-    return f"{customer}: payment needed"
+    return f"{customer}: waiting for release token"


## Final claim
ARM=cursor_native
fixture_id=pilot-cold-resume-blocked-gate
mechanical_claim=fail
mode=live
proof_commands=python3 checks/visible_check.py -> rc 0
real_surface_proof=n/a
known_issues=live_agent_fix:cursor_native


## Mechanical outcome
fail

## Mode
live