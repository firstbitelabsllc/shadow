# A/B/C decisions

A plan in `needs_input` state declares one question and exactly three bounded
options. Each option has an ID, label, and consequence. The browser sends only:

```json
{"plan":"project/PLAN.md","option_id":"cold-review","revision":7}
```

The server compares that revision with current authority. A current choice is
`received`; a stale choice is `superseded`; a mismatched choice is
`not_delivered`. Receipt does not mean the coding host applied the choice.
