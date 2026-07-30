# Design influences

Vidux combines a few durable software-work patterns:

- repository-owned plans instead of chat-owned state;
- read, assess, act, verify, checkpoint as a resumable loop;
- evidence near the decision it supports;
- bounded delegation with one reviewing owner; and
- git revision plus mechanical gates as proof identity.

These are design influences, not bundled dependencies or claims of invention.
Vidux deliberately leaves model routing, scheduling, authentication, durable
workflow execution, and provider operations to the coding host.

The project should absorb a new pattern only when it makes interrupted work
easier to understand or makes a release claim more mechanically truthful.
