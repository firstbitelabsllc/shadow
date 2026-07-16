# Blinded Reviewer Packet

Run: run-0006-pilot-plan-noise-duplicate-trap-thin_vidux_kernel
Fixture: pilot-plan-noise-duplicate-trap

## Visible proof output
visible_check PASS


## Diff summary
diff --git a/PLAN.md b/PLAN.md
index 41a2ff1..a53b4f3 100644
--- a/PLAN.md
+++ b/PLAN.md
@@ -1,5 +1,5 @@
 # Canonical Plan
 
 ## Tasks
-- [pending] Add the missing export summary behavior here; do not create another plan.
+- [completed] Add the missing export summary behavior here; do not create another plan.
   Accept: `python3 checks/visible_check.py` exits 0.
diff --git a/mammothsplit/export.py b/mammothsplit/export.py
index 8c3a543..ab9d61d 100644
--- a/mammothsplit/export.py
+++ b/mammothsplit/export.py
@@ -1,2 +1,3 @@
 def export_summary(rows: list[dict]) -> dict:
-    return {"count": len(rows)}
+    ids = [row["id"] for row in rows]
+    return {"count": len(rows), "ids": ids}


## Final claim
ARM=thin_vidux_kernel
fixture_id=pilot-plan-noise-duplicate-trap
mechanical_claim=pass
proof_commands=python3 checks/visible_check.py -> rc 0
real_surface_proof=n/a
known_issues=success_path


## Mechanical outcome
pass