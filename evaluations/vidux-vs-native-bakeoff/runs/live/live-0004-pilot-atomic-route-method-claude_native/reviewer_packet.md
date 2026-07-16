# Blinded Reviewer Packet

Run: live-0004-pilot-atomic-route-method-claude_native
Fixture: pilot-atomic-route-method

## Visible proof output
visible_check PASS


## Diff summary
diff --git a/PLAN.md b/PLAN.md
index 90bb4a0..8731c65 100644
--- a/PLAN.md
+++ b/PLAN.md
@@ -1,5 +1,5 @@
 # API Method Contract
 
 ## Tasks
-- [pending] Fix `/api/finalize` so only POST finalizes a split.
+- [completed] Fix `/api/finalize` so only POST finalizes a split.
   Accept: `python3 checks/visible_check.py` exits 0.
diff --git a/mammothsplit/api.py b/mammothsplit/api.py
index dfb1402..26ff398 100644
--- a/mammothsplit/api.py
+++ b/mammothsplit/api.py
@@ -1,7 +1,7 @@
 def finalize_split(method: str, payload: dict | None = None) -> tuple[int, dict]:
     payload = payload or {}
     if method.upper() == "GET":
-        return 200, {"ok": True, "finalized": True, "source": "unsafe-get"}
+        return 405, {"ok": False, "error": "method_not_allowed"}
     if method.upper() == "POST":
         return 200, {"ok": True, "finalized": True, "source": "post"}
     return 405, {"ok": False, "error": "method_not_allowed"}


## Final claim
ARM=claude_native
fixture_id=pilot-atomic-route-method
mechanical_claim=pass
mode=live
proof_commands=python3 checks/visible_check.py -> rc 0
real_surface_proof=n/a
known_issues=live_agent_fix:claude_native


## Mechanical outcome
pass

## Mode
live