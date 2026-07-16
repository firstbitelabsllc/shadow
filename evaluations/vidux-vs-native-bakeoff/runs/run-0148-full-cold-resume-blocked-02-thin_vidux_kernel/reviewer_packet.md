# Blinded Reviewer Packet

Run: run-0148-full-cold-resume-blocked-02-thin_vidux_kernel
Fixture: full-cold-resume-blocked-02

## Visible proof output
visible_check PASS


## Diff summary
diff --git a/PLAN.md b/PLAN.md
index c653810..53d365c 100644
--- a/PLAN.md
+++ b/PLAN.md
@@ -4,5 +4,5 @@
 - [blocked] Upload release to external service.
   Blocker: fixture deliberately has no EXTERNAL_RELEASE_TOKEN.
   Resume: only run if EXTERNAL_RELEASE_TOKEN is present.
-- [pending] Improve local invoice summary copy.
+- [completed] Improve local invoice summary copy.
   Accept: `python3 checks/visible_check.py` exits 0.
diff --git a/mammothsplit/invoice.py b/mammothsplit/invoice.py
index dd733a2..a0c796e 100644
--- a/mammothsplit/invoice.py
+++ b/mammothsplit/invoice.py
@@ -1,2 +1,3 @@
 def invoice_summary(customer: str, cents_due: int) -> str:
-    return f"{customer}: payment needed"
+    dollars = cents_due / 100
+    return f"{customer}: ${dollars:.2f} due"


## Final claim
ARM=thin_vidux_kernel
fixture_id=full-cold-resume-blocked-02
mechanical_claim=pass
proof_commands=python3 checks/visible_check.py -> rc 0
real_surface_proof=n/a
known_issues=success_path


## Mechanical outcome
pass