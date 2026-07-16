# Blinded Reviewer Packet

Run: run-0030-full-cold-resume-blocked-02-cursor_native
Fixture: full-cold-resume-blocked-02

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
fixture_id=full-cold-resume-blocked-02
mechanical_claim=fail
proof_commands=python3 checks/visible_check.py -> rc 0
real_surface_proof=n/a
known_issues=failure_path:blocked_stall


## Mechanical outcome
fail