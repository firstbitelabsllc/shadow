# A/B/C decisions

A plan in `needs_input` state declares one question and exactly three bounded
options. Each option has an ID, label, and consequence. The browser sends only:

```json
{"entity":"<entity-id>","root_board_revision":42,"option_id":"cold-review","revision":7}
```

`root_board_revision` must match the current computer board or the server
refuses the write and asks for a reload. Past that guard, the server compares
`revision` with the entity plan's current authority. A current choice is
`received`; a stale choice is `superseded`; a mismatched choice is
`not_delivered`. Receipt does not mean the coding host applied the choice.
