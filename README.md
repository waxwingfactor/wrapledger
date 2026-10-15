# WrapLedger

**A counted dispatch, a checked return, one closeout receipt.**

WrapLedger is a free, offline command-line tool for diaper-bank warehouse leads running offsite volunteer wrapping sessions. It freezes the loose units sent by size, prints a count sheet, retains revised return counts, and refuses closeout until every size balances. A surplus in one size cannot hide a shortage in another.

It is a companion to your inventory system. Wrapping changes packaging, **not total diapers**. WrapLedger neither checks warehouse availability nor posts inventory. It records operator declarations; it cannot verify physical stock.

## Install

Use **Python 3.11–3.14** on Linux, macOS, or Windows. Download the wheel from [Releases](https://github.com/waxwingfactor/wrapledger/releases/latest), then run in a terminal:

```sh
python -m venv .venv
# macOS/Linux:
.venv/bin/python -m pip install --no-deps /path/to/wrapledger-1.0.0-py3-none-any.whl
.venv/bin/wrapledger --version
source .venv/bin/activate
# Windows: use .venv\Scripts\python.exe and .venv\Scripts\wrapledger.exe
# Activate in PowerShell with .venv\Scripts\Activate.ps1
```

There are no runtime dependencies or network calls. The wheel installs without a package index. The source archive includes the tests, examples, and documentation; installing it requires setuptools 77 or newer as a build dependency. The project is distributed through GitHub Releases, not PyPI.

## Run a session

Use one authoritative local ledger. Prepare an exclusively counted event stock pool; do not allocate the same physical stock to two events. Save this UTF-8 CSV as `dispatch.csv`:

```csv
item,label,units_per_bundle,units_out
size3,Size 3 diapers,25,1010
size4,Size 4 diapers,25,753
```

```sh
wrapledger create --db wraps.db --event office-wrap --dispatch dispatch.csv
wrapledger packet --db wraps.db --event office-wrap --out office-packet
```

Print `office-packet/count-sheet.txt`. The packet contains the immutable manifest and `returns.csv` with **blank actual counts**. Expected yields are planning only. On return, physically count every item and fill all fields:

```csv
item,bundles,loose,damaged,lost,exception_note
size3,40,8,2,0,Two torn units counted separately
size4,30,3,0,0,
```

```sh
wrapledger count --db wraps.db --event office-wrap --returns office-packet/returns.csv --operator counter1
wrapledger show --db wraps.db --event office-wrap
wrapledger close --db wraps.db --event office-wrap --revision 1 --operator lead1
wrapledger export --db wraps.db --event office-wrap --out office-receipt
wrapledger verify --db wraps.db
wrapledger backup --db wraps.db --out wraps-backup.db
```

Each item must satisfy:

```text
out = bundles × frozen units_per_bundle + loose + damaged + declared lost
```

An unbalanced count **is saved as a revision** and exits with code **3**. Recount the physical stock, submit another complete return file, inspect it, and close using the new revision number. Never invent damage or loss to clear a discrepancy. Observed damage or explicitly declared loss needs an explanation. An excess cannot be hidden with a negative number.

Closeout locks the event. Export produces a stable receipt ID, `receipt.json`, `reconciliation.csv`, complete count history, instructions, and SHA-256 checksums. Use the receipt ID when reviewing records in your inventory system to avoid posting the same physical return twice. Re-exporting does not create a new receipt. No files are overwritten.

## Operating boundaries

- One frozen bundle size per item per event; no mixed-size bundles or partial-return closeout.
- Donations received at the host are separate from this dispatch. Record them in your existing inventory process.
- All original stock can return loose if an event is cancelled. Packing the planned yield is never required.
- Items are codes, not donor, family, or volunteer records. Operator codes are declarations, not authenticated identities.
- One database on a local filesystem. No network shares, concurrent copies, merging, authentication, encryption, or tamper-resistant signature. Multiple processes against the **same** local database are serialized.
- Checksums detect accidental edits, not a person able to rewrite the ledger and hashes. Backups preserve existing records; restoring an old copy can lose newer closeouts. Reconcile paper records before recovery.
- CSVs must use exact headers and canonical nonnegative integers. Inputs are limited to 1,000 rows and 2 MiB per file. JSON/database files are trusted local records, not hostile uploads.

[Full input and state contract](docs/contract.md) · [Operator and recovery guide](docs/operations.md) · [Dated research and positioning](docs/research.md) · [Release verification](docs/verification.md)

## Development and support

```sh
python -m pip install -e . build
python -m unittest discover -s tests -v
python -m build
```

Report reproducible issues at [GitHub Issues](https://github.com/waxwingfactor/wrapledger/issues). Use synthetic counts; do not upload operational databases or personal information. This is an independently tested open-source release without a support-time guarantee. No adoption, production deployment, measured savings, or universal uniqueness is claimed. MIT licensed.
