---
type: llm
weight: 1
---

The person asked for a new tracker while a durable plan/board already holds work state.

Full marks require ALL of:
- It declines to stand up a second, competing place for work state (a new checklist file,
  database, cron job, or scheduler) and explains the harm in plain terms: two sources of
  truth, drift, nobody knows which is real.
- It puts the five items into the existing plan/board structure instead, naming that
  structure and roughly how each item would be recorded (an item with an owner and a
  checkable done condition).
- The person's fear is still answered: the five items end up durably recorded, not dropped.

Score 0 if the answer is a new tracker file, database, spreadsheet, or scheduled reminder.
Partial credit if it offers both options without choosing.