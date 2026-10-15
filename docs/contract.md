# WrapLedger v1 supported contract

Python 3.11–3.14 stdlib CLI, local SQLite single-authoritative database. No network, warehouse availability, scheduling, inventory integrations, authentication or recipient data. Physical stock must be exclusively counted for the event before creation. Do not fork/copy the live database into parallel authorities. Backup is a consistent read snapshot, not a mergeable ledger.

Commands (successful operation output is JSON; operational errors are JSON on stderr; help, version and argument syntax errors use conventional text):
- `wrapledger create --db PATH --event SLUG --dispatch CSV`
- `wrapledger packet --db PATH --event SLUG --out NEW_DIRECTORY`
- `wrapledger count --db PATH --event SLUG --returns CSV --operator SLUG`
- `wrapledger show --db PATH --event SLUG`
- `wrapledger close --db PATH --event SLUG --revision INTEGER --operator SLUG`
- `wrapledger export --db PATH --event SLUG --out NEW_DIRECTORY`
- `wrapledger events --db PATH`
- `wrapledger verify --db PATH`
- `wrapledger backup --db PATH --out NEW_FILE`

Create freezes exact rows; event ID cannot be reused. Packet has manifest.csv, returns.csv (blank counts, never planned counts), readable count-sheet.txt. Expected whole-bundle yield plus loose remainder is planning only. Count is a complete replacement revision, all event items exactly once, with prior revisions retained. Count succeeds persistently with exit 3 if any discrepancy; exit 0 if balanced. All normal errors exit 2 without traceback. Close requires latest revision and balanced equation for EVERY item; a second close fails. Closed events cannot accept new counts. Export only after close; includes receipt.json, reconciliation.csv, count-history.json, README.txt and SHA256SUMS; no executable files or paths from input. No overwrites. Reports are count/custody evidence; no automatic inventory changes. Re-export uses same receipt ID. Verify checks SQLite integrity, application identity/version, dispatch and revision hashes, shapes, closed revision and receipt; hashes detect accidental edits, not an attacker able to rewrite DB and hashes.

Dispatch CSV exact header: `item,label,units_per_bundle,units_out`
Return CSV exact header: `item,bundles,loose,damaged,lost,exception_note`

UTF-8 (optional BOM), comma delimiter, exact headers/order, LF or CRLF. No duplicate/unknown/missing items, extra columns, blank rows, control characters, formulas or implicit numeric coercions. IDs use ASCII letter/digit first then letter/digit/dash/underscore, max64. Label max120, exception_note max240; no leading spreadsheet formula chars (=+-@), controls or surrounding whitespace. Integers canonical decimal, zero or nonzero without leading zero; quantities 0..1,000,000,000; bundle size 1..1,000,000; units_out strictly positive. Max1000 rows and 2MiB input. All arithmetic uses integer units. Distinct items are never netted. Good returned = bundles * frozen units_per_bundle + loose. Accounted = good returned + damaged + lost. Difference = units_out - accounted (positive missing, negative excess). Damage or declared loss requires a nonempty exception_note explaining the physical observation. Loss is explicitly declared by operator; do not relabel unexplained variance as damage/loss just to close. Received donations/new items are outside this manifest; handle separately in existing inventory then create another event if needed. A cancelled session can return all units loose and close with zero bundles.

Public Python API in `wrapledger.core` uses keyword-compatible functions:
`create(db, event, dispatch)`, `packet(db,event,out)`, `count(db,event,returns,operator)`, `show(db,event)`, `close(db,event,revision,operator)`, `events(db)`, `verify(db)`, `backup(db,out)`.
Paths accept str/Path. Return dicts. Operational error is `LedgerError`. `show` returns event, status (open/counted/discrepancy/closed), revision (0 initially), dispatch list, counts list or null, reconciliation list (item,units_out,units_per_bundle,bundles,loose,damaged,lost,good_returned,accounted,difference,exception_note) or null, receipt_id (null before close). Count returns same shape. Close returns same shape with receipt_id. API `export(db,event,out)` generates closed packet; returns {'out':str,'receipt_id':str}. `create`/count/close/packet/export/backup must preserve committed ledger state if file/report output fails; packet/export don't mutate. Create/count/close have no file outputs beyond DB. All mutations use transactions with a lock (BEGIN IMMEDIATE); no partially counted session.
