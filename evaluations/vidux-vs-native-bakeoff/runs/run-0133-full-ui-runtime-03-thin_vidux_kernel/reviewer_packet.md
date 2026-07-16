# Blinded Reviewer Packet

Run: run-0133-full-ui-runtime-03-thin_vidux_kernel
Fixture: full-ui-runtime-03

## Visible proof output
visible_check PASS


## Diff summary
diff --git a/PLAN.md b/PLAN.md
index 2e0939b..25d1da7 100644
--- a/PLAN.md
+++ b/PLAN.md
@@ -1,5 +1,5 @@
 # Runtime UI Proof
 
 ## Tasks
-- [pending] Make the settlement summary render exact paid/unpaid counts and an empty state.
+- [completed] Make the settlement summary render exact paid/unpaid counts and an empty state.
   Accept: `python3 checks/visible_check.py` exits 0 and save a rendered proof artifact.
diff --git a/mammothsplit/ui.py b/mammothsplit/ui.py
index b49e632..81a7400 100644
--- a/mammothsplit/ui.py
+++ b/mammothsplit/ui.py
@@ -1,5 +1,9 @@
 def render_summary(participants: list[dict]) -> str:
     if not participants:
-        return "<section><h1>Settlement</h1></section>"
+        return "<section><h1>Settlement</h1><p>No participants yet — empty state</p></section>"
     paid = sum(1 for p in participants if p.get("paid"))
-    return f"<section><h1>Settlement</h1><p>{paid} paid</p></section>"
+    unpaid = len(participants) - paid
+    return (
+        f"<section><h1>Settlement</h1>"
+        f"<p>{paid} paid</p><p>{unpaid} unpaid</p></section>"
+    )


## Final claim
ARM=thin_vidux_kernel
fixture_id=full-ui-runtime-03
mechanical_claim=pass
proof_commands=python3 checks/visible_check.py -> rc 0
real_surface_proof=artifacts/runtime-proof.html
known_issues=success_path


## Mechanical outcome
pass