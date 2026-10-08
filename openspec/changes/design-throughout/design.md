## D1. Tokens
Take the token values already in report.html (they came from the design) as the single source. Both pages
inline tokens.css; no other hex values in either page outside it.

## D2. Table component
`.dtable`: card border and radius from the design, uppercase small header like the design's group labels,
14px rows, mono for code/sha/paths, status cells use the same pill as checks. Below 640px each row becomes a
small card of label/value pairs. More than 20 rows: show 20 and a "Show all N" button.

## D3. Index grouping
Group key from the model: verdict plus who acts first (view.todo.now_role). Order: Ready for a committer,
Waiting on reviewers, Waiting on the contributor, Cannot tell, Drafts. Within a group, newest update first.
Review effort words: "Small" / "Medium" / "Large" from triage, plus "N lines in M files".

## D4. No new data
Everything shown is already in the model; anything missing (e.g. "already commenting on the ticket") stays out.
