# Codex setup

Vidux requires no Codex-specific database, background service, or automation
installer.

1. Clone Vidux and run `vidux doctor`.
2. Let Codex read the root `SKILL.md`.
3. Run `vidux init --here` in a repository that does not yet have a plan.
4. Use Codex's supported UI and current official documentation for any task or
   automation setup.

Never edit Codex's private database or application files as part of Vidux
setup. Host internals are not a stable public API, and Vidux ships no helper for
mutating them.
