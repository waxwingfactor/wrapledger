# Operator and recovery guide

## One authority, physical counts first

Keep the database on a local filesystem and back it up with `wrapledger backup`. The ledger stores event-specific counts, not warehouse availability. Count and set aside stock before creating an event; coordinate exclusive use in your existing inventory system. Create freezes both units sent and units per bundle. It does not reserve warehouse stock or independently verify dispatch.

Use an event code printed on each box and packet. Do not put personal information in labels or notes. Separate each item/size and separate damage. A partially wrapped return is normal; all unwrapped stock returns as loose units. A cancelled wrapping session returns all stock loose.

The manifest cannot be edited once created. If a clerical error is found before physical dispatch, close that event by recording all original units as returned loose, use an event code indicating cancellation, and create a new event for the corrected manifest. This is a record of cancellation, not a physical inventory receipt. Keep explanatory paper records. If the error is discovered after dispatch, retain the event and its discrepancy; reconcile the original count with the physical dispatch records. There is no silent manifest correction. Do not fabricate loss to repair a clerical error. An event can remain unresolved indefinitely.

## Return and revision

Fill the generated `returns.csv` with actual counts for every item. Blank counts are not zero. All returned quantities are nonnegative integers. You may have more than one bundle's worth of loose units; the program does not assume further wrapping occurred. Surpluses from a new donation are outside the manifest and must be separated.

`count` saves a complete revision. Exit 0 means balanced; exit 3 means saved but unresolved. The `difference` is outgoing minus accounted units: positive means missing, negative means excess. For each item, damage and declared loss need an explanation. These entries describe operator observations or declarations. Neither they nor operator codes prove physical truth or authorization under your bank's policy.

When a recount changes the result, submit the whole corrected file again. Earlier revisions remain in history. `close --revision N` requires the latest revision, checks every item, and locks the count. If another operator records a new revision while you are reviewing, close fails and you must inspect the new one.

A closed event cannot be reopened or counted again. Retain later corrections in your existing system and associated paper records; do not edit the SQLite database. WrapLedger is a bounded event closeout ledger, not a general accounting journal with reversals.

## Inventory review

The exported receipt is evidence for review, not an import into Human Essentials or another system. Wrapping alone creates zero additional individual diapers. Never add returned bundle contents to quantities already included in inventory. Your system may represent offsite custody as a location transfer, and your bank's policy determines how damage/loss is recorded. Separate raw/wrapped SKU or kit configurations are outside this product.

The stable receipt ID lets a reviewer recognize a re-export. It cannot prevent a person manually posting twice in another system. Record that ID in the other system or a controlled posting checklist. Keep the receipt with the signed physical count sheet.

## Backups, errors and recovery

All state mutations are transactional. Invalid inputs do not create count revisions. Commands do not print success before a database commit. A report failure never undoes an already committed count; generate the packet/export again with a new destination. Ordinary operational errors are JSON on stderr and exit 2. Help, version and argument syntax errors use argparse's conventional text. An unbalanced count is the special exit 3 and is already saved. If stdout fails after mutation, the change may have committed: inspect `show`/`events` before retrying.

`backup --out NEW_FILE` uses SQLite's consistent backup API, checks the copied ledger, and refuses existing output. After a disk-full, lock, or interruption, run `verify` and inspect `show`/`events` before retrying. `verify` detects SQLite damage, wrong application/schema, altered stored checksums, invalid count shapes, invalid revision ordering, and unbalanced closed events. It does not prove completeness against deleted entire events or defend against a malicious editor capable of changing hashes.

Do not copy a database in active use using file-manager copies. Stop all commands or use backup. The backup is a snapshot, never a concurrent working branch. To relocate: finish commands, create and verify a backup, move the backup to a new local folder/computer, verify it there, inspect current events, designate it as the sole authority, and retire the original working copy. The software stores no absolute input paths and works offline.

If verification fails, preserve the damaged file, recover a known-good backup, and compare its events/receipts against paper records and any later inventory postings. Restoring an older snapshot may omit a closed event; do not blindly repeat closeout or posting. There is no automatic merge, repair, or recovery guarantee. File exports and backups are not crash-atomic: an interrupted destination may be incomplete. Preserve it for inspection and export/backup to a new path; verify the backup and every receipt checksum before relying on it.
