"""Independent acceptance scenarios derived from docs/contract.md.

These tests deliberately use real files, independent ledger connections and the
installed command. They do not replace core functions with mocks or infer stock
from a planned yield. All people, quantities and labels below are constructed.
"""

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

from wrapledger import core


DISPATCH_HEADER = ["item", "label", "units_per_bundle", "units_out"]
RETURNS_HEADER = ["item", "bundles", "loose", "damaged", "lost", "exception_note"]
DISPATCH = [
    ["newborn", "Newborn size", "18", "198"],
    ["size-6", "Size six", "24", "250"],
]
BALANCED = [
    ["newborn", "11", "0", "0", "0", ""],
    ["size-6", "10", "10", "0", "0", ""],
]


class WrapLedgerAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wrapledger-acceptance-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / "custody.sqlite3"
        self.dispatch = self.write_csv("dispatch.csv", DISPATCH_HEADER, DISPATCH)
        self.returns = self.write_csv("returns.csv", RETURNS_HEADER, BALANCED)

    def write_csv(self, filename, header, rows, *, encoding="utf-8", newline="\n"):
        target = self.root / filename
        with target.open("w", encoding=encoding, newline="") as stream:
            writer = csv.writer(stream, lineterminator=newline)
            writer.writerow(header)
            writer.writerows(rows)
        return target

    def create(self):
        return core.create(db=self.db, event="autumn-wrap", dispatch=self.dispatch)

    def count(self, returns=None, operator="counter-a"):
        return core.count(
            db=self.db,
            event="autumn-wrap",
            returns=returns or self.returns,
            operator=operator,
        )

    def show(self):
        return core.show(db=self.db, event="autumn-wrap")

    def close(self, revision=1, operator="receiver-a"):
        return core.close(
            db=self.db, event="autumn-wrap", revision=revision, operator=operator
        )

    def rows_by_item(self, state):
        return {row["item"]: row for row in state["reconciliation"]}

    def assert_rejected_without_change(self, operation):
        before = self.show()
        with self.assertRaises(core.LedgerError):
            operation()
        self.assertEqual(self.show(), before)

    def ready_closed(self):
        self.create()
        self.count()
        return self.close()

    def test_complete_custody_lifecycle_and_exact_integer_accounting(self):
        created = self.create()
        self.assertEqual(created["event"], "autumn-wrap")
        self.assertEqual(created["status"], "open")
        self.assertEqual(created["revision"], 0)
        self.assertIsNone(created["counts"])
        self.assertIsNone(created["reconciliation"])
        self.assertIsNone(created["receipt_id"])

        # Two physically damaged and two declared lost units explain this size.
        returns = self.write_csv(
            "observed.csv",
            RETURNS_HEADER,
            [
                ["newborn", "10", "14", "2", "2", "Two torn; two lost in transit"],
                ["size-6", "10", "10", "0", "0", ""],
            ],
        )
        counted = self.count(returns)
        self.assertEqual(counted["status"], "counted")
        self.assertEqual(counted["revision"], 1)
        newborn = self.rows_by_item(counted)["newborn"]
        for key, expected in {
            "units_out": 198,
            "units_per_bundle": 18,
            "bundles": 10,
            "loose": 14,
            "damaged": 2,
            "lost": 2,
            "good_returned": 194,
            "accounted": 198,
            "difference": 0,
        }.items():
            self.assertEqual(newborn[key], expected, key)
            self.assertIs(type(newborn[key]), int, key)
        closed = self.close()
        self.assertEqual(closed["status"], "closed")
        self.assertTrue(closed["receipt_id"])
        self.assertEqual(self.show(), closed)
        self.assertIsInstance(core.verify(db=self.db), dict)
        self.assertIsInstance(core.events(db=self.db), dict)

    def test_packet_counts_are_blank_and_planning_cannot_close_event(self):
        self.create()
        before = self.show()
        destination = self.root / "outbound-packet"
        core.packet(db=self.db, event="autumn-wrap", out=destination)
        self.assertEqual(self.show(), before)
        self.assertTrue((destination / "manifest.csv").is_file())
        self.assertTrue((destination / "count-sheet.txt").read_text(encoding="utf-8"))
        with (destination / "returns.csv").open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, RETURNS_HEADER)
            rows = list(reader)
        self.assertEqual({row["item"] for row in rows}, {"newborn", "size-6"})
        for row in rows:
            for field in RETURNS_HEADER[1:]:
                self.assertEqual(row[field], "", field)
        self.assert_rejected_without_change(lambda: self.close(revision=0))
        self.assert_rejected_without_change(
            lambda: self.count(destination / "returns.csv")
        )

    def test_recipe_is_frozen_even_when_source_file_is_replaced(self):
        self.create()
        original = self.show()["dispatch"]
        self.write_csv(
            "dispatch.csv", DISPATCH_HEADER,
            [["newborn", "Changed upstream", "99", "999"], ["size-6", "Changed", "7", "7"]],
        )
        counted = self.count()
        self.assertEqual(counted["dispatch"], original)
        newborn = self.rows_by_item(counted)["newborn"]
        self.assertEqual(newborn["good_returned"], 198)
        self.assertEqual(newborn["units_per_bundle"], 18)
        self.assertEqual(self.close()["status"], "closed")

    def test_opposite_size_variances_never_cancel_each_other(self):
        self.create()
        returns = self.write_csv(
            "offset.csv", RETURNS_HEADER,
            [["newborn", "10", "8", "0", "0", ""], ["size-6", "10", "20", "0", "0", ""]],
        )
        counted = self.count(returns)
        self.assertEqual(counted["status"], "discrepancy")
        differences = {item: row["difference"] for item, row in self.rows_by_item(counted).items()}
        self.assertEqual(differences, {"newborn": 10, "size-6": -10})
        self.assertEqual(sum(differences.values()), 0)
        self.assert_rejected_without_change(lambda: self.close())

    def test_revision_replaces_all_counts_and_history_retains_observations(self):
        self.create()
        first = self.write_csv(
            "first.csv", RETURNS_HEADER,
            [["newborn", "10", "0", "0", "0", "FirstObservationSentinel"], BALANCED[1]],
        )
        self.assertEqual(self.count(first, "counter-first")["status"], "discrepancy")
        corrected = self.count(operator="counter-second")
        self.assertEqual(corrected["revision"], 2)
        self.assertEqual(self.rows_by_item(corrected)["newborn"]["bundles"], 11)
        self.assertEqual(self.rows_by_item(corrected)["newborn"]["exception_note"], "")
        self.assert_rejected_without_change(lambda: self.close(revision=1))
        self.close(revision=2)
        destination = self.root / "closed-packet"
        core.export(db=self.db, event="autumn-wrap", out=destination)
        history = json.loads((destination / "count-history.json").read_text(encoding="utf-8"))
        text = json.dumps(history)
        for observed in ["counter-first", "counter-second", "FirstObservationSentinel"]:
            self.assertIn(observed, text)

    def test_partial_duplicate_unknown_or_extra_item_is_atomic(self):
        self.create()
        self.count()
        invalid_sets = {
            "partial": [BALANCED[0]],
            "duplicate": [BALANCED[0], BALANCED[0], BALANCED[1]],
            "unknown": [BALANCED[0], ["size-7", "10", "10", "0", "0", ""]],
            "extra": BALANCED + [["size-7", "0", "0", "0", "0", ""]],
        }
        for name, rows in invalid_sets.items():
            with self.subTest(name=name):
                returns = self.write_csv(name + ".csv", RETURNS_HEADER, rows)
                self.assert_rejected_without_change(lambda: self.count(returns))

    def test_damage_and_declared_loss_require_explanatory_notes(self):
        self.create()
        for name, damaged, lost in [("damage", "1", "0"), ("loss", "0", "1")]:
            with self.subTest(name=name):
                returns = self.write_csv(
                    name + ".csv", RETURNS_HEADER,
                    [["newborn", "10", "17", damaged, lost, ""], BALANCED[1]],
                )
                self.assert_rejected_without_change(lambda: self.count(returns))
        valid = self.write_csv(
            "declared-loss.csv", RETURNS_HEADER,
            [["newborn", "10", "17", "0", "1", "One unit lost while transporting"], BALANCED[1]],
        )
        result = self.count(valid)
        self.assertEqual(result["status"], "counted")
        self.assertEqual(self.rows_by_item(result)["newborn"]["lost"], 1)
        self.assertEqual(self.close()["status"], "closed")

    def test_cancelled_session_returns_every_unit_loose(self):
        self.create()
        cancelled = self.write_csv(
            "cancelled.csv", RETURNS_HEADER,
            [["newborn", "0", "198", "0", "0", "Session cancelled"],
             ["size-6", "0", "250", "0", "0", "Session cancelled"]],
        )
        state = self.count(cancelled)
        self.assertEqual(state["status"], "counted")
        for row in state["reconciliation"]:
            self.assertEqual(row["bundles"], 0)
            self.assertEqual(row["difference"], 0)
        self.close()

    def test_event_cannot_be_reused_or_closed_twice_or_recounted(self):
        self.ready_closed()
        self.assert_rejected_without_change(lambda: self.create())
        self.assert_rejected_without_change(lambda: self.close())
        self.assert_rejected_without_change(lambda: self.count())

    def test_export_is_unavailable_until_closed(self):
        self.create()
        destination = self.root / "premature-export"
        self.assert_rejected_without_change(
            lambda: core.export(db=self.db, event="autumn-wrap", out=destination)
        )
        self.assertFalse(destination.exists())
        self.count()
        self.assert_rejected_without_change(
            lambda: core.export(db=self.db, event="autumn-wrap", out=destination)
        )
        self.assertFalse(destination.exists())

    def test_two_receivers_cannot_both_close_the_same_revision(self):
        self.create()
        self.count()
        start = threading.Barrier(2)

        def receive(operator):
            start.wait(timeout=10)
            try:
                result = self.close(operator=operator)
                return "closed", result["receipt_id"]
            except core.LedgerError:
                return "rejected", None

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(receive, ["receiver-one", "receiver-two"]))
        self.assertEqual(sorted(result[0] for result in results), ["closed", "rejected"])
        self.assertEqual(self.show()["status"], "closed")
        core.verify(db=self.db)

    def test_utf8_bom_crlf_and_quoted_label_are_supported(self):
        self.dispatch = self.write_csv(
            "bom.csv", DISPATCH_HEADER,
            [["newborn", 'Newborn, "small" – size', "18", "198"], DISPATCH[1]],
            encoding="utf-8-sig", newline="\r\n",
        )
        self.create()
        self.returns = self.write_csv(
            "bom-returns.csv", RETURNS_HEADER, BALANCED,
            encoding="utf-8-sig", newline="\r\n",
        )
        self.count()
        self.close()

    def test_invalid_dispatch_never_creates_an_event(self):
        malformed = {
            "reordered": (["label", "item", "units_per_bundle", "units_out"], DISPATCH),
            "extra-column": (DISPATCH_HEADER + ["extra"], [DISPATCH[0] + ["x"]]),
            "duplicate-item": (DISPATCH_HEADER, [DISPATCH[0], DISPATCH[0]]),
            "zero-bundle": (DISPATCH_HEADER, [["x", "Example", "0", "5"]]),
            "zero-dispatch": (DISPATCH_HEADER, [["x", "Example", "5", "0"]]),
            "coerced-number": (DISPATCH_HEADER, [["x", "Example", "5", "05"]]),
            "float": (DISPATCH_HEADER, [["x", "Example", "5", "5.0"]]),
            "plus": (DISPATCH_HEADER, [["x", "Example", "5", "+5"]]),
            "negative": (DISPATCH_HEADER, [["x", "Example", "5", "-5"]]),
            "quantity-limit": (DISPATCH_HEADER, [["x", "Example", "5", "1000000001"]]),
            "bundle-limit": (DISPATCH_HEADER, [["x", "Example", "1000001", "5"]]),
            "unsafe-id": (DISPATCH_HEADER, [["../escape", "Example", "5", "5"]]),
            "unicode-id": (DISPATCH_HEADER, [["é", "Example", "5", "5"]]),
            "long-id": (DISPATCH_HEADER, [["x" * 65, "Example", "5", "5"]]),
            "formula": (DISPATCH_HEADER, [["x", "=HYPERLINK(1)", "5", "5"]]),
            "padded-label": (DISPATCH_HEADER, [["x", " Example ", "5", "5"]]),
            "long-label": (DISPATCH_HEADER, [["x", "x" * 121, "5", "5"]]),
            "control": (DISPATCH_HEADER, [["x", "Bad\tlabel", "5", "5"]]),
            "empty": (DISPATCH_HEADER, []),
        }
        for name, (header, rows) in malformed.items():
            with self.subTest(name=name):
                bad = self.write_csv(name + ".csv", header, rows)
                db = self.root / (name + ".sqlite3")
                with self.assertRaises(core.LedgerError):
                    core.create(db=db, event="invalid-event", dispatch=bad)
                # A failed create may initialize an empty DB, but cannot commit an event.
                if db.exists():
                    with self.assertRaises(core.LedgerError):
                        core.show(db=db, event="invalid-event")

    def test_invalid_return_values_and_csv_shapes_never_replace_revision(self):
        self.create()
        self.count()
        cases = {
            "leading-zero": ["newborn", "011", "0", "0", "0", ""],
            "decimal": ["newborn", "11.0", "0", "0", "0", ""],
            "negative": ["newborn", "-1", "0", "0", "0", ""],
            "space": ["newborn", " 11", "0", "0", "0", ""],
            "blank-count": ["newborn", "", "0", "0", "0", ""],
            "huge": ["newborn", "1000000001", "0", "0", "0", ""],
            "formula-note": ["newborn", "11", "0", "0", "0", "@SUM(1)"],
            "padded-note": ["newborn", "11", "0", "0", "0", " padded "],
            "long-note": ["newborn", "11", "0", "0", "0", "x" * 241],
            "control-note": ["newborn", "11", "0", "0", "0", "line\nbreak"],
            "extra-cell": BALANCED[0] + ["unexpected"],
            "missing-cell": BALANCED[0][:-1],
        }
        for name, row in cases.items():
            with self.subTest(name=name):
                returns = self.write_csv("bad-" + name + ".csv", RETURNS_HEADER, [row, BALANCED[1]])
                self.assert_rejected_without_change(lambda: self.count(returns))
        for name, payload in {
            "blank-row": "item,bundles,loose,damaged,lost,exception_note\n\nnewborn,11,0,0,0,\nsize-6,10,10,0,0,\n",
            "bad-utf8": b"item,bundles,loose,damaged,lost,exception_note\n\xff,1,0,0,0,\n",
            "broken-quote": 'item,bundles,loose,damaged,lost,exception_note\nnewborn,11,0,0,0,"unclosed\n',
            "semicolon": "item;bundles;loose;damaged;lost;exception_note\nnewborn;11;0;0;0;\n",
        }.items():
            with self.subTest(name=name):
                returns = self.root / (name + ".csv")
                returns.write_bytes(payload if isinstance(payload, bytes) else payload.encode("utf-8"))
                self.assert_rejected_without_change(lambda: self.count(returns))

    def test_resource_limits_reject_large_inputs_without_partial_event(self):
        many = self.write_csv(
            "too-many.csv", DISPATCH_HEADER,
            [["item-" + str(i), "Example", "1", "1"] for i in range(1001)],
        )
        oversized = self.root / "too-big.csv"
        oversized.write_bytes(b"item,label,units_per_bundle,units_out\n" + b"x" * (2 * 1024 * 1024))
        for name, source in [("many", many), ("oversized", oversized)]:
            with self.subTest(name=name):
                with self.assertRaises(core.LedgerError):
                    core.create(db=self.root / (name + ".sqlite3"), event=name, dispatch=source)

    def test_thousand_item_boundary_supports_a_complete_session(self):
        self.dispatch = self.write_csv(
            "thousand.csv", DISPATCH_HEADER,
            [["item-" + str(i), "Size " + str(i), "10", "25"] for i in range(1000)],
        )
        self.returns = self.write_csv(
            "thousand-returns.csv", RETURNS_HEADER,
            [["item-" + str(i), "2", "5", "0", "0", ""] for i in range(1000)],
        )
        self.create()
        counted = self.count()
        self.assertEqual(len(counted["reconciliation"]), 1000)
        self.assertTrue(all(row["difference"] == 0 for row in counted["reconciliation"]))
        self.close()
        core.verify(db=self.db)

    def test_maximum_quantities_use_integer_arithmetic_without_overflow(self):
        self.dispatch = self.write_csv(
            "maximum.csv", DISPATCH_HEADER, [["large", "Large physical count", "1000000", "1000000000"]]
        )
        self.returns = self.write_csv(
            "maximum-returns.csv", RETURNS_HEADER, [["large", "1000000000", "0", "0", "0", ""]]
        )
        self.create()
        row = self.count()["reconciliation"][0]
        self.assertEqual(row["good_returned"], 1000000000000000)
        self.assertEqual(row["difference"], -999999000000000)
        self.assertIs(type(row["difference"]), int)
        self.assert_rejected_without_change(lambda: self.close())

    def test_invalid_event_operator_and_revision_are_operational_errors(self):
        for event in ["../escape", "bad event", "é", "x" * 65, ""]:
            with self.subTest(event=event):
                with self.assertRaises(core.LedgerError):
                    core.create(db=self.db, event=event, dispatch=self.dispatch)
        self.create()
        for operator in ["bad operator", "../escape", "", "x" * 65]:
            with self.subTest(operator=operator):
                self.assert_rejected_without_change(lambda: self.count(operator=operator))
        self.count()
        for revision in [0, -1, 2]:
            with self.subTest(revision=revision):
                self.assert_rejected_without_change(lambda: self.close(revision=revision))

    def test_output_failures_do_not_mutate_committed_ledger_or_overwrite(self):
        closed = self.ready_closed()
        existing = self.root / "already-there"
        existing.mkdir()
        sentinel = existing / "sentinel.txt"
        sentinel.write_text("preserve this", encoding="utf-8")
        for operation in [core.packet, core.export]:
            with self.subTest(operation=operation.__name__):
                self.assert_rejected_without_change(
                    lambda: operation(db=self.db, event="autumn-wrap", out=existing)
                )
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve this")
                self.assertEqual(list(existing.iterdir()), [sentinel])
        target = self.root / "existing-backup.sqlite3"
        target.write_bytes(b"do not overwrite")
        self.assert_rejected_without_change(lambda: core.backup(db=self.db, out=target))
        self.assertEqual(target.read_bytes(), b"do not overwrite")
        parent_file = self.root / "not-a-directory"
        parent_file.write_text("file", encoding="utf-8")
        for operation in [core.packet, core.export]:
            with self.subTest(operation=operation.__name__, failure="parent-is-file"):
                self.assert_rejected_without_change(
                    lambda: operation(db=self.db, event="autumn-wrap", out=parent_file / "packet")
                )
        self.assertEqual(self.show(), closed)

    def assert_export_hashes(self, destination):
        expected_names = {
            "receipt.json", "reconciliation.csv", "count-history.json", "README.txt", "SHA256SUMS"
        }
        self.assertEqual({path.name for path in destination.iterdir()}, expected_names)
        entries = {}
        for line in (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, filename = line.split(maxsplit=1)
            filename = filename.lstrip("*")
            self.assertNotIn(filename, entries)
            self.assertEqual(Path(filename).name, filename)
            self.assertEqual(hashlib.sha256((destination / filename).read_bytes()).hexdigest(), digest)
            entries[filename] = digest
        self.assertEqual(set(entries), expected_names - {"SHA256SUMS"})
        for path in destination.iterdir():
            self.assertTrue(path.is_file())
            self.assertFalse(path.stat().st_mode & 0o111, path.name)

    def test_export_is_relocatable_offline_and_hashes_cover_every_payload(self):
        state = self.ready_closed()
        first = self.root / "first-export"
        second = self.root / "second-export"
        with patch.object(socket, "socket", side_effect=AssertionError("network access is outside contract")):
            result = core.export(db=self.db, event="autumn-wrap", out=first)
            self.assertEqual(result["receipt_id"], state["receipt_id"])
            self.assert_export_hashes(first)
            core.export(db=self.db, event="autumn-wrap", out=second)
        self.assertEqual(
            json.loads((first / "receipt.json").read_text())["receipt_id"],
            json.loads((second / "receipt.json").read_text())["receipt_id"],
        )
        # The handoff remains useful when the original database/source are absent.
        relocated = self.root / "a different location" / "handoff"
        relocated.parent.mkdir()
        shutil.move(str(first), relocated)
        self.db.unlink()
        self.dispatch.unlink()
        self.returns.unlink()
        self.assert_export_hashes(relocated)
        for path in relocated.iterdir():
            self.assertNotIn(str(self.root), path.read_text(encoding="utf-8"), path.name)

    def test_backup_can_be_verified_and_relocated_as_a_read_snapshot(self):
        state = self.ready_closed()
        backup_file = self.root / "snapshot.sqlite3"
        with patch.object(socket, "socket", side_effect=AssertionError("unexpected network")):
            core.backup(db=self.db, out=backup_file)
            core.verify(db=backup_file)
        moved = self.root / "relocated" / "read-snapshot.sqlite3"
        moved.parent.mkdir()
        shutil.move(str(backup_file), moved)
        self.db.unlink()
        self.dispatch.unlink()
        self.returns.unlink()
        self.assertEqual(core.show(db=moved, event="autumn-wrap"), state)
        core.verify(db=moved)
        out = self.root / "snapshot-export"
        core.export(db=moved, event="autumn-wrap", out=out)
        self.assert_export_hashes(out)

    def test_backup_releases_all_sqlite_connections_before_returning(self):
        self.ready_closed()
        opened = []
        real_connect = sqlite3.connect

        def observe_connection(*arguments, **keywords):
            connection = real_connect(*arguments, **keywords)
            opened.append(connection)
            return connection

        try:
            # Keep real connections alive so garbage collection cannot hide a
            # leaked backup handle on POSIX before Windows CI exercises it.
            with patch.object(sqlite3, "connect", side_effect=observe_connection):
                core.backup(db=self.db, out=self.root / "closed-handles.sqlite3")
            self.assertTrue(opened)
            for index, connection in enumerate(opened):
                with self.subTest(connection=index):
                    with self.assertRaises(sqlite3.ProgrammingError):
                        connection.execute("SELECT 1")
        finally:
            for connection in opened:
                connection.close()

    def corrupt_stored_text(self, needle):
        # Discover storage rather than assume core table/column names. The edit
        # preserves JSON syntax/SQL structure while changing a recorded fact.
        with closing(sqlite3.connect(self.db)) as connection, connection:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )]
            for table in tables:
                quoted_table = '"' + table.replace('"', '""') + '"'
                cursor = connection.execute("SELECT rowid, * FROM " + quoted_table)
                columns = [item[0] for item in cursor.description]
                for row in cursor.fetchall():
                    for index, value in enumerate(row[1:], start=1):
                        if isinstance(value, str) and needle in value:
                            column = '"' + columns[index].replace('"', '""') + '"'
                            connection.execute(
                                "UPDATE " + quoted_table + " SET " + column + "=? WHERE rowid=?",
                                [value.replace(needle, "FactChangedByTamper"), row[0]],
                            )
                            return
        self.fail("Fixture fact was not persisted in the ledger")

    def test_verify_detects_dispatch_fact_tampering(self):
        self.dispatch = self.write_csv(
            "sentinel.csv", DISPATCH_HEADER,
            [["newborn", "DispatchFactSentinel", "18", "198"], DISPATCH[1]],
        )
        self.ready_closed()
        self.corrupt_stored_text("DispatchFactSentinel")
        with self.assertRaises(core.LedgerError):
            core.verify(db=self.db)

    def test_verify_detects_historical_count_fact_tampering(self):
        self.create()
        observed = self.write_csv(
            "sentinel-count.csv", RETURNS_HEADER,
            [["newborn", "10", "17", "1", "0", "CountFactSentinel"], BALANCED[1]],
        )
        self.count(observed)
        self.count()  # A retained old revision is still covered by verification.
        self.close(revision=2)
        self.corrupt_stored_text("CountFactSentinel")
        with self.assertRaises(core.LedgerError):
            core.verify(db=self.db)

    def test_verify_rejects_wrong_sqlite_application_and_schema_version(self):
        self.ready_closed()
        for pragma in ["application_id", "user_version"]:
            with self.subTest(pragma=pragma):
                other = self.root / (pragma + ".sqlite3")
                core.backup(db=self.db, out=other)
                with closing(sqlite3.connect(other)) as connection, connection:
                    current = connection.execute("PRAGMA " + pragma).fetchone()[0]
                    connection.execute("PRAGMA " + pragma + "=" + str(current + 1))
                with self.assertRaises(core.LedgerError):
                    core.verify(db=other)

    def test_missing_and_unrelated_databases_fail_clearly(self):
        absent = self.root / "absent.sqlite3"
        with self.assertRaises(core.LedgerError):
            core.verify(db=absent)
        unrelated = self.root / "unrelated.sqlite3"
        with closing(sqlite3.connect(unrelated)) as connection, connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
            connection.execute("INSERT INTO unrelated VALUES ('preserve')")
        before = unrelated.read_bytes()
        for operation in [lambda: core.verify(db=unrelated),
                          lambda: core.create(db=unrelated, event="autumn-wrap", dispatch=self.dispatch)]:
            with self.assertRaises(core.LedgerError):
                operation()
        self.assertEqual(unrelated.read_bytes(), before)

    def test_create_rejects_existing_empty_file_without_initializing_or_removing_it(self):
        existing = self.root / "existing-empty.sqlite3"
        existing.touch()
        with self.assertRaises(core.LedgerError):
            core.create(db=existing, event="autumn-wrap", dispatch=self.dispatch)
        self.assertTrue(existing.is_file())
        self.assertEqual(existing.read_bytes(), b"")
        self.assertFalse(Path(str(existing) + "-wal").exists())
        self.assertFalse(Path(str(existing) + "-journal").exists())

    def test_c1_controls_and_invisible_format_characters_are_rejected(self):
        forbidden = ["\u0080", "\u0085", "\u009f", "\u200b", "\u202e"]
        for index, character in enumerate(forbidden):
            with self.subTest(field="label", character=ascii(character)):
                bad = self.write_csv(
                    "control-label-" + str(index) + ".csv", DISPATCH_HEADER,
                    [["newborn", "Before" + character + "After", "18", "198"], DISPATCH[1]],
                )
                with self.assertRaises(core.LedgerError):
                    core.create(
                        db=self.root / ("control-" + str(index) + ".sqlite3"),
                        event="invalid-control", dispatch=bad,
                    )
        self.create()
        self.count()
        for index, character in enumerate(forbidden):
            with self.subTest(field="exception_note", character=ascii(character)):
                bad = self.write_csv(
                    "control-note-" + str(index) + ".csv", RETURNS_HEADER,
                    [["newborn", "11", "0", "0", "0", "Before" + character + "After"], BALANCED[1]],
                )
                self.assert_rejected_without_change(lambda: self.count(bad))

    def test_console_unicode_labels_and_notes_work_with_ascii_output_encoding(self):
        executable = shutil.which("wrapledger")
        self.assertIsNotNone(executable, "Install the package before running acceptance tests")
        label = "Pequeño – 幼児"
        note = "Paquete dañado"
        self.dispatch = self.write_csv(
            "unicode-dispatch.csv", DISPATCH_HEADER,
            [["newborn", label, "18", "198"], DISPATCH[1]],
        )
        observed = self.write_csv(
            "unicode-counts.csv", RETURNS_HEADER,
            [["newborn", "10", "17", "1", "0", note], BALANCED[1]],
        )
        environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        environment.update(PYTHONIOENCODING="ascii", PYTHONUTF8="0")
        for arguments in [
            ["create", "--db", self.db, "--event", "autumn-wrap", "--dispatch", self.dispatch],
            ["count", "--db", self.db, "--event", "autumn-wrap", "--returns", observed, "--operator", "counter-ascii"],
            ["close", "--db", self.db, "--event", "autumn-wrap", "--revision", "1", "--operator", "receiver-ascii"],
            ["show", "--db", self.db, "--event", "autumn-wrap"],
        ]:
            with self.subTest(command=arguments[0]):
                result = subprocess.run(
                    [executable, *map(str, arguments)], cwd=self.root, env=environment,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                state = json.loads(result.stdout.decode("ascii"))
                self.assertEqual(state["dispatch"][0]["label"], label)
                self.assertNotIn(b"Traceback", result.stderr)
                if state["reconciliation"] is not None:
                    self.assertEqual(self.rows_by_item(state)["newborn"]["exception_note"], note)

    @unittest.skipIf(os.name == "nt", "A closed POSIX pipe is required for this regression")
    def test_console_closed_stdout_pipe_fails_cleanly_without_mutating_ledger(self):
        executable = shutil.which("wrapledger")
        self.assertIsNotNone(executable, "Install the package before running acceptance tests")
        before = self.ready_closed()
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            result = subprocess.run(
                [executable, "show", "--db", str(self.db), "--event", "autumn-wrap"],
                cwd=self.root,
                stdout=write_fd,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
                env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            )
        finally:
            os.close(write_fd)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertNotIn(b"Exception ignored", result.stderr)
        self.assertIsInstance(json.loads(result.stderr), dict)
        self.assertEqual(self.show(), before)
        core.verify(db=self.db)

    def test_console_exit_codes_json_and_persisted_discrepancy(self):
        executable = shutil.which("wrapledger")
        self.assertIsNotNone(executable, "Install the package before running acceptance tests")

        def command(*arguments):
            result = subprocess.run(
                [executable, *map(str, arguments)],
                cwd=self.root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
                env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            )
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            output = result.stdout.strip() or result.stderr.strip()
            return result.returncode, json.loads(output)

        code, result = command("create", "--db", self.db, "--event", "autumn-wrap", "--dispatch", self.dispatch)
        self.assertEqual(code, 0, result)
        discrepancy = self.write_csv(
            "cli-discrepancy.csv", RETURNS_HEADER,
            [["newborn", "10", "0", "0", "0", ""], BALANCED[1]],
        )
        code, result = command("count", "--db", self.db, "--event", "autumn-wrap", "--returns", discrepancy, "--operator", "counter-cli")
        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "discrepancy")
        self.assertEqual(self.show()["revision"], 1)
        code, result = command("close", "--db", self.db, "--event", "autumn-wrap", "--revision", "1", "--operator", "receiver-cli")
        self.assertEqual(code, 2, result)
        code, result = command("count", "--db", self.db, "--event", "autumn-wrap", "--returns", self.returns, "--operator", "counter-cli")
        self.assertEqual(code, 0, result)
        code, result = command("close", "--db", self.db, "--event", "autumn-wrap", "--revision", "2", "--operator", "receiver-cli")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "closed")
        code, result = command("verify", "--db", self.db)
        self.assertEqual(code, 0, result)


if __name__ == "__main__":
    unittest.main()
