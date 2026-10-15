# Independent AI-agent review record

Date: 2026-10-15. These are separate AI-agent reviews, not human GitHub approvals, customer tests, or security certification. All agents shared the local source directory; their roles and conclusions are recorded honestly. The maintainer remains responsible for the changes.

## Opportunity challenge

An independent research agent compared Human Essentials requests, custom units, kits, transfers and audits; OpenRefine/Frictionless and repair-data tools for a rejected candidate; tool-library systems; and ERPNext/Odoo subcontracting. The generic demand-to-packing candidate was rejected. Offsite count/custody reconciliation was selected as an adjunct with inferred demand, not as evidence that banks lack inventory software. [Evidence and positioning](research.md).

## Acceptance testing

A separate testing agent wrote black-box acceptance scenarios from [the contract](contract.md), covering lifecycle, per-item conservation, recipe immutability, complete revision replacement, malformed input rollback, exceptions, cancellation, concurrent close, upper input boundaries, offline relocation, backup, export hashes and corruption checks. The initial tests caught plain-text operational errors where JSON was promised. This was corrected, while help/version and syntax errors were explicitly documented as conventional text.

## Code review and repairs

A third agent reviewed transaction boundaries, report output, validation, receipt identity and recovery. It found:

- Existing empty files could be initialized inadvertently. Initialization now requires this process to create the file exclusively; existing files must already be a supported ledger.
- C1 Unicode controls passed validation. Text now rejects Unicode control, format and surrogate categories.
- ASCII output encoding could cause a traceback for ordinary Unicode labels. CLI JSON uses ASCII escapes while preserving Unicode values on parsing.
- A closed stdout pipe could trigger a second flush at interpreter shutdown. The handler now neutralizes the failed descriptor and returns exit 2. A command may already have committed before output fails; operators must inspect state before retrying.

Cross-platform CI then caught a Windows backup handle leak: a SQLite connection context commits a transaction but does not close the file. Backup now explicitly closes its destination in a finally block; test-only SQLite connections are also closed explicitly so Windows can relocate and remove databases.

Review also identified that interrupted file exports/backups can be partial. [Recovery instructions](operations.md) state this explicitly; database mutations remain transactional. No malicious-editor protection, authenticated operator identities, inventory integration, or physical-count truth guarantee is claimed.

Final repair re-review and public artifact verification are recorded in [release verification](verification.md).
