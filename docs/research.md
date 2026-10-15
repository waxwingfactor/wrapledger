# WrapLedger: evidence, alternatives, and positioning

Research date: **2026-10-15**. This is a bounded desk-research record, not a claim of universal uniqueness or a market survey. No customer interviews, customer adoption, production deployments, or measured time savings are claimed. Public pages and repositories can change after this date.

## Decision and evidence boundary

The selected audience is a diaper-bank operations lead who sends an exclusively counted quantity of disposable diapers to an offsite volunteer wrapping session, receives the resulting bundles and remaining material back, and wants one reviewable record of that session. The lead or a supporting technical volunteer must be comfortable installing a Python command-line tool and preparing CSV files. Volunteers can use the printed count sheet; they do not need accounts or a running server.

Offsite wrapping is documented. Utah Diaper Bank describes supervisors collecting packaged diapers, overseeing wrapping into 25-count packs, and bringing 20–60 boxes back. CNY Diaper Bank supplies offsite kits with wrap, labels, and instructions. These sources establish a physical dispatch, transformation, and return workflow. They do **not** establish that the organizations lack software or suffer frequent reconciliation errors. [Utah volunteer roles](https://www.utahdiaperbank.org/volunteer), [CNY volunteer options](https://www.cnydiaperbank.org/volunteer).

Sweet Cheeks publishes an offsite-event guide with a volunteer/event-size table and a 25-diaper wrapping convention. St. Louis Area Diaper Bank brings materials to mobile events, while HappyBottoms describes wrapping at a host's location. These are examples of the operating pattern, not reference customers for WrapLedger. Their staffing, fees, throughput estimates, and wrapping rules are not defaults or promises made by this product. [Sweet Cheeks mobile guide](https://sweetcheeksdiaperbank.org/diaper-drive-toolkit/Mobile-Wrapping-Document-web.pdf), [St. Louis volunteer programs](https://stldiaperbank.org/volunteer/), [HappyBottoms mobile program](https://happybottoms.org/volunteer/mobile/).

The documented operational burden includes checking delivery counts, maintaining inventory by size, training volunteers in wrapping, and filling orders accurately. A bank's current operations roles also include final accuracy checks and resolving distribution discrepancies. Charleston's volunteer signs additionally require counts by size, logging before storage, and separating unrecorded donations. [Charleston operational signs](https://www.jlcharleston.org/wp-content/uploads/Diaper-Bank-QR-code-Signs.pdf). These primary responsibilities establish why count accuracy matters; they do not demonstrate an offsite miscount rate or dissatisfaction with existing software. [Athens operations role (2021 document)](https://www.athensareadiaperbank.com/uploads/1/2/4/8/124844864/aadb_operations_manager_job_description_2021.pdf), [Diaper Bank of North Carolina roles](https://www.ncdiaperbank.org/job-openings).

The product hypothesis is narrower: some coordinators may prefer a portable session packet that freezes dispatched counts and bundle sizes, separates planned yield from observed returns, retains count revisions, and refuses closeout until every item is accounted for. Demand for that adjunct, its advantage over a careful spreadsheet, and willingness to use a CLI are **inferences requiring future user validation**. Search-result absence is not evidence that competitors or internal tools do not exist.

## Three passes through alternatives

The research used separate discovery and adversarial review work, then feature-level primary documentation. Representative searches included diaper-bank inventory/repackaging software, offsite/mobile wrapping, repair-café queue software, tool-library maintenance/kits, and subcontracting raw-material returns. The passes answer different questions; they are not three independent confirmations that an unserved market exists.

| Pass | What was checked | Evidence and decision |
| --- | --- | --- |
| 1 — native tools and initial opportunities | Whether generic nonprofit intake, packing, picking, and lending operations were already efficient | Human Essentials already totals requested products and prints request picklists. Its kit feature allocates or deallocates component stock and checks component sufficiency. The initial generic diaper demand-to-repack/picklist idea was rejected as insufficiently distinct. [Requests](https://rubyforgood.github.io/human-essentials/user_guide/bank/essentials_requests.html), [kit documentation source](https://raw.githubusercontent.com/rubyforgood/human-essentials/main/docs/user_guide/bank/inventory_kits.md). |
| 2 — open-source and adjacent community products | Whether changing audience or interface would merely repeat a complete existing workflow | Circularity Repair Cafe Hub already has QR intake, a live repair board, skill categories, repairers, and reports; a smaller repair-café Kanban tool also exports CSV. Lend Engine documents scheduled and after-loan maintenance, assignment, lending blocks, and costs. Repair-café queue management and tool-library maintenance were rejected. [Circularity](https://github.com/Zesty0wl/circularity-repair-cafe-hub), [repair-cafe-kanban](https://git.autonomic.zone/trav/repair-cafe-kanban), [Lend Engine maintenance](https://www.lend-engine.com/features/maintenance-and-servicing). |
| 3 — complete substitute workflows | Whether the selected dispatch/return accounting was already possible in an incumbent or general system | Human Essentials transfers plus kits can represent moving and transforming stock; its audits and adjustments reconcile counts. ERPNext and Odoo support external processing with supplied components and subsequent receipts. A spreadsheet can calculate the same conservation equation. The selected scope is a small offline custody/count workflow, not a novel accounting method or an assertion that alternatives cannot do the job. [Human Essentials transfers](https://rubyforgood.github.io/human-essentials/user_guide/bank/inventory_transfers.html), [audits](https://rubyforgood.github.io/human-essentials/user_guide/bank/inventory_audits.html), [ERPNext subcontracting](https://docs.frappe.io/erpnext/subcontracting), [Odoo resupply subcontracting](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/manufacturing/subcontracting/subcontracting_resupply.html). |

A repair-data conversion or migration-audit candidate around the Open Repair Data Standard was also rejected. ORDS is a legitimate shared approach for combining community electronics-repair records, but a migration/audit product would be too close in workflow shape to the previously commissioned IIIF Migration Audit. A different standard or sector would not supply sufficient differentiation. [Open Repair Alliance's standard description](https://openrepair.org/open-data/open-standard/).

## Alternatives worth choosing

**Human Essentials is the credible product alternative for a diaper bank's wider operation.** It is free, open source, and designed for essentials banks. Its documentation covers partner requests, printable picklists, kits, transfers, audits, and corrections. The homepage includes a Sweet Cheeks testimonial about resolving fragmented inventory tracking; the existence of Sweet Cheeks' mobile program therefore cannot be used to imply it lacks useful software. WrapLedger does not replace that system of record, integrate with it, or claim its public documentation describes every available feature. [Human Essentials](https://humanessentials.app/), [project source](https://github.com/rubyforgood/human-essentials).

The reviewed Human Essentials documentation did not describe a single session record linking a frozen offsite manifest, complete revisions of actual returns, a per-item closeout gate, and a portable receipt packet. This is a documentation-level observation, not proof of feature absence. The advantage being tested is having those steps connected within a deliberately smaller local tool.

**A spreadsheet and paper count sheet are the immediate market alternative.** They are familiar, flexible, usable offline, and sufficient for many small sessions. The arithmetic is simple enough to implement in a sheet. A carefully controlled workbook can also preserve versions and lock formulas. WrapLedger is worth considering only when its enforced input contracts, retained revisions, explicit closeout, and consistent export are preferable to maintaining those controls manually; there is no measured evidence here that it is faster.

**ERPNext or Odoo is preferable when integrated inventory/manufacturing is the actual requirement.** ERPNext documents sending materials to a subcontractor and receiving finished goods and scrap, including consumed quantities. Odoo documents a resupply subcontracting workflow using a vendor, bill of materials, component routes, and receipts. These are capable complete alternatives, with broader setup and operating concepts than a one-session count ledger. WrapLedger's small scope is a tradeoff, not evidence of missing ERP capability. [ERPNext](https://docs.frappe.io/erpnext/subcontracting), [Odoo](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/manufacturing/subcontracting/subcontracting_resupply.html).

## Inventory effect and supported whole product

Human Essentials explains that banks need individual-item quantities even when partners request packs, and that pack sizes may vary. Wrapping the same diapers into bundles does not create additional diapers. A balanced session with no damage or loss has **zero effect on the bank's total individual-diaper inventory**. Never add the returned bundle contents to a raw count that already includes them. [Human Essentials custom units](https://rubyforgood.github.io/human-essentials/user_guide/bank/special_custom_units.html).

WrapLedger produces custody/count evidence only. It performs no inventory posting, availability check, reservation, automatic adjustment, or import into another product. Bank staff decide how verified physical observations affect their existing records and policies. Transfers between locations and any deliberately configured raw-to-kit accounting belong in that existing system.

The supported whole workflow is defined in [the v1 contract](contract.md): create an event from exclusively counted stock; generate a manifest, blank actual-return CSV, and readable count sheet; record complete count revisions; inspect discrepancies; close against the latest balanced revision; export a receipt, reconciliation, count history, and checksums. Verification and consistent backup support retaining that local record. Planned bundle yield never fills actual counts automatically.

For each distinct item, the closeout equation is:

```text
units dispatched = returned bundles × frozen units per bundle
                   + returned loose units + observed damaged units
                   + explicitly declared lost units
```

Differences remain visible and block closeout; a surplus in one size cannot offset another size's shortage. Damage and declared loss require an observation note. Operators must not relabel unexplained variance just to make the equation balance. The receipt records what the operator entered; it does not establish physical truth, product suitability, or protection against an attacker who can rewrite the database and its hashes.

The scope is a Python 3.11–3.14 standard-library CLI and local SQLite database, with bounded CSV inputs. There is one authoritative database, not mergeable copies carried by multiple teams. There is no authentication, hosted service, volunteer scheduling, donor/recipient information, shipping system, warehouse stock management, or event-time donation intake. New donations are handled separately in the existing inventory process. These boundaries make the supported workflow small enough to complete and review; they also exclude many banks' broader needs.

## Constructed usage scenarios

These are invented acceptance scenarios, not observations of customers or estimates of savings.

1. **Ordinary return:** A coordinator dispatches 102 size-4 diapers with a frozen bundle size of 25. The packet plans four bundles and two loose units. On return, the operator independently counts four bundles and two loose units, records a balanced revision, and closes it. Total diapers remain 102.
2. **Recount after a discrepancy:** The first return count records three bundles and 24 loose units, leaving three units unexplained. The ledger retains that discrepancy and refuses closeout. A physical recount finds three damaged units; the operator records a new complete revision and an observation note, then reviews the balanced result before closing. Merely inventing a loss entry to remove the discrepancy is outside the intended procedure.
3. **Cancelled wrapping session:** All 102 diapers return loose. Zero bundles and 102 loose units reconcile, despite producing none of the planned bundles. A complete custody record does not require achieving the production plan.

## Applying Crossing the Chasm selectively

Geoffrey Moore's own positioning page emphasizes a narrowly defined beachhead, the whole product, and comparison with alternatives. Those concepts guide this product's scope and explanation. They do not establish demand or justify invented reference customers, distribution channels, revenue models, or market-share projections. [Geoffrey Moore: Positioning](https://geoffreyamoore.com/positioning/).

The beachhead is the operations lead for a bank already running counted offsite wrapping sessions, with Python/CSV help available and a separate inventory system retained. The compelling reason to try it is a reviewable dispatch-to-return record with an explicit per-item closeout decision. Installation, strict contracts, printable materials, correction history, backup, verification, examples, and release validation are whole-product requirements for that limited job; they are not an expansion into general nonprofit management.

### Original two-sentence positioning statement

For diaper-bank operations leads who send counted stock to offsite volunteer wrapping sessions and are dissatisfied with manually connecting dispatch sheets, revised return counts, and closeout decisions, WrapLedger is an offline session ledger that turns those counts into a reviewed per-item reconciliation and portable receipt. Unlike using Human Essentials alone as the wider inventory system, WrapLedger provides a dedicated local dispatch-and-return workflow with frozen bundle sizes, blank actual-count forms, retained revisions, a balanced-closeout gate, backups, and verifiable exports while leaving inventory decisions with the bank.

This statement expresses intended fit and an inferred dissatisfaction; it is not a claim that Human Essentials lacks every corresponding capability or that its users report that dissatisfaction. Reconsider the product hypothesis if coordinators prefer an existing sheet, native feature, or integrated inventory workflow.
