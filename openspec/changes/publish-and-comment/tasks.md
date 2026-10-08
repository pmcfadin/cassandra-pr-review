## 1. Comment

- [ ] 1.1 `cpr/comment.py`: build body from a report model (tests: content and length cap; dry run makes no write)
- [ ] 1.2 Find own comment by marker and author; create or edit; unchanged → no write; record comment.json (tests with a fake gh runner: first post, edit on new head, unchanged)
- [ ] 1.3 Guards: current head via gh, Pages model head via HTTP, confirmation (tests: stale local, Pages behind, no TTY without --yes)
- [ ] 1.4 `cpr comment <N> [--post] [--yes]` in cli.py; docs/report/about.md section on the comment

## 2. Ship

- [ ] 2.1 Dry run on 5201 and show the owner; first live post only after the owner confirms
