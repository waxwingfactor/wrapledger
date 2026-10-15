# WrapLedger 1.0.0 verification

Release date: **2026-10-15**. This record describes software-release checks with synthetic data. It does not claim customer deployment, adoption, interviews, measured savings, physical-stock verification or a security certification.

## Source and required checks

- [Public repository](https://github.com/waxwingfactor/wrapledger) and [installable release](https://github.com/waxwingfactor/wrapledger/releases/tag/v1.0.0).
- Exact release revision: [`39c60510f7fea3d7883cadbe3573f779b7f14587`](https://github.com/waxwingfactor/wrapledger/commit/39c60510f7fea3d7883cadbe3573f779b7f14587).
- Source tree: `0b70ede0d3a193546875ad8f197feead003ef24e`, identical to the tested PR head's tree.
- [Implementation PR #2](https://github.com/waxwingfactor/wrapledger/pull/2) merged through protected main after the [required PR CI](https://github.com/waxwingfactor/wrapledger/actions/runs/38794023886) passed. The single-maintainer PR gate requires CI and conversation resolution, with admin enforcement; it does not pretend that the author can provide an independent human approval.
- The [exact merged release revision CI](https://github.com/waxwingfactor/wrapledger/actions/runs/38794243852) also passed all jobs.
- 31 acceptance tests run on Linux, macOS and Windows with Python 3.11, 3.12, 3.13 and 3.14: all 12 matrix jobs passed. The real POSIX broken-pipe regression is skipped on Windows. Packaging CI separately builds and installs the wheel/source archive in fresh environments and checks source-archive contents.
- [Separate AI-agent review record](reviews.md): independent acceptance tests and code review found and repaired input/output defects and a real Windows backup handle leak. A retained-connection regression detects the leak on POSIX as well. All identified source-review findings were resolved and independently rechecked.

## Published artifact identities

These files were built from the clean merged revision using Python 3.12.14 on macOS arm64, build 1.6.1 and setuptools 84.0.0. Wheel Python source bytes were checked against the Git source. The release's `provenance.json` and `SHA256SUMS` connect the revision, tree and file hashes. They are unsigned maintainer records, not cryptographic attestations.

| Installable artifact | SHA-256 |
| --- | --- |
| `wrapledger-1.0.0-py3-none-any.whl` | `d0b8dbf3595a3539a2870882dea4a9e9a6736dd489d8a4edd5645cc45abbea21` |
| `wrapledger-1.0.0.tar.gz` | `6c9025782ccb889fd3e2423ecf0eb98bb7216c35d9505d6bad34eb592abc3c73` |

Prepublication checks installed each built file into a fresh temporary environment outside the checkout, asserted package location under that environment, exercised the lifecycle and negative cases with runtime sockets disabled, verified receipt hashes, then relocated a backup and re-exported after deleting the original database and input files. The source archive built/installed and included tests, examples and documentation. These local checks are attached as `prepublication-verification.json`; they are distinct from the public-download verification below.

## Actual public-download verification

A separate AI-agent verifier downloaded the actual public wheel, source archive, checksum file, provenance and prepublication report anonymously into a fresh temporary area outside the checkout. All five GitHub API asset digests and every SHA256SUMS entry matched. The public tag resolved to the exact revision above. All four wheel Python files and 18 tracked source-archive files matched the public exact-commit source byte for byte.

Each installable artifact was installed independently into a new non-editable environment using Python 3.12.14 on macOS arm64. The wheel installed with `--no-index --no-deps`; source was built/installed separately with declared build tooling. Package locations were confirmed inside each environment's site-packages, with no PYTHONPATH or source-directory import leakage. The downloaded source archive's **31 acceptance tests passed against each installed package**, for 62 test executions.

An independently written **17-command CLI scenario passed for each artifact**. It checked persisted exit-3 discrepancies, wrong-size differences that cannot cancel, blocked unbalanced closeout, atomic rejection of an incomplete count, corrected revision 2, stale close rejection, close-once/recount locking, export, backup and verification. After deleting original inputs and the working database, a relocated backup still verified and re-exported the same receipt ID. Receipt payload checksums matched. Socket-blocked API checks passed; this was not an OS-level airgap or firewall test.

Anonymous HTTP checks also returned 200 for the repository and release page. [Machine-readable public verification](https://github.com/waxwingfactor/wrapledger/releases/download/v1.0.0/public-verification.json) records environments, artifact identities and observed checks. Its SHA-256 is `89f8341a3d8332e7a7fd27389906c5d13dc2ba3fb3d6a70f933cd24f6db2728f`. Published installable assets were not replaced. The source archive retains its prepublication documentation snapshot; this page and the public verification report were completed afterward without rewriting those artifacts.

## Practical limits

The wheel has no runtime dependencies or network calls. Building the source requires setuptools 77 or newer; build tooling may need a package index. This is an offline local event ledger with one authoritative database, not hosted inventory software. Count reconciliation cannot prove physical counts or prevent duplicate manual posting in another system. Backup/report destinations can be incomplete after interruption and must be verified. No new donations, mixed-item bundles, partial closeouts, authenticated operators, mergeable ledgers or malicious-tamper resistance are supported. [Full contract](contract.md) and [recovery instructions](operations.md).
