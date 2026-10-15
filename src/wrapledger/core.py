"""Transactional event-local count ledger. All quantities are individual units."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone

APP_ID = 0x57524C31
SCHEMA = 1
LIMIT = 1_000_000_000
MAX_ROWS = 1000
MAX_BYTES = 2 * 1024 * 1024
DISPATCH = ['item', 'label', 'units_per_bundle', 'units_out']
RETURNS = ['item', 'bundles', 'loose', 'damaged', 'lost', 'exception_note']
SLUG = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
INTEGER = re.compile(r'(0|[1-9][0-9]{0,9})\Z')


class LedgerError(Exception):
    """An input, state, integrity, or filesystem error safe to show the operator."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _hash(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _slug(value, field):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise LedgerError(f'{field}: use 1–64 ASCII letters/digits/dashes/underscores, starting with a letter/digit')
    return value


def _text(value, field, maximum, required=True):
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise LedgerError(f'{field}: text required, maximum {maximum} characters')
    if value != value.strip() or any(unicodedata.category(c) in ('Cc', 'Cf', 'Cs') for c in value):
        raise LedgerError(f'{field}: no surrounding whitespace or control characters')
    if value.startswith(('=', '+', '-', '@')):
        raise LedgerError(f'{field}: spreadsheet formula prefixes are unsupported')
    return value


def _integer(value, field, minimum=0, maximum=LIMIT):
    if not isinstance(value, str) or not INTEGER.fullmatch(value) or not minimum <= int(value) <= maximum:
        raise LedgerError(f'{field}: canonical integer {minimum}..{maximum} required')
    return int(value)


def _validate_rows(rows, header):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise LedgerError(f'CSV must have 1..{MAX_ROWS} item rows')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(header):
            raise LedgerError('Unexpected row fields')
        item = _slug(row['item'], 'item')
        if item in seen:
            raise LedgerError(f'Duplicate item: {item}')
        seen.add(item)
        if header == DISPATCH:
            _text(row['label'], f'{item} label', 120)
            for key, lo, hi in [('units_per_bundle', 1, 1_000_000), ('units_out', 1, LIMIT)]:
                value = row[key]
                if type(value) is not int or not lo <= value <= hi:
                    raise LedgerError(f'{item} {key}: integer {lo}..{hi} required')
        else:
            for key in RETURNS[1:5]:
                if type(row[key]) is not int or not 0 <= row[key] <= LIMIT:
                    raise LedgerError(f'{item} {key}: integer 0..{LIMIT} required')
            _text(row['exception_note'], f'{item} exception_note', 240, False)
            if (row['damaged'] or row['lost']) and not row['exception_note']:
                raise LedgerError(f'{item}: damage/loss requires an exception_note')
    return rows


def _csv(path, header):
    try:
        with Path(path).open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise LedgerError(f'CSV exceeds {MAX_BYTES} bytes')
        source_hash = hashlib.sha256(data).hexdigest()
        reader = csv.reader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
        if next(reader, None) != header:
            raise LedgerError(f'CSV header must be exactly: {",".join(header)}')
        rows = []
        for line, values in enumerate(reader, 2):
            if len(values) != len(header):
                raise LedgerError(f'CSV row {line}: expected {len(header)} fields')
            row = dict(zip(header, values))
            for key in (DISPATCH[2:] if header == DISPATCH else RETURNS[1:5]):
                row[key] = _integer(row[key], f'row {line} {key}', 1 if key in DISPATCH[2:] else 0,
                                    1_000_000 if key == 'units_per_bundle' else LIMIT)
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise LedgerError(f'CSV exceeds {MAX_ROWS} rows')
        return _validate_rows(rows, header), source_hash
    except (OSError, UnicodeError, csv.Error) as exc:
        raise LedgerError(f'Cannot read CSV: {exc}') from exc


@contextmanager
def _db(path, initialize=False, write=False):
    connection = None
    created = False
    try:
        p = Path(path).resolve()
        if initialize:
            # O_EXCL prevents a new ledger from overwriting an existing file.
            try:
                fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                created = True
            except FileExistsError:
                pass
        connection = sqlite3.connect(p.as_uri() + '?mode=rw', uri=True, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        app_id = connection.execute('PRAGMA application_id').fetchone()[0]
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if created and app_id == 0 and not tables:
            connection.execute(f'PRAGMA application_id={APP_ID}')
            connection.execute(f'PRAGMA user_version={SCHEMA}')
            connection.execute('CREATE TABLE events (event TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)')
        elif app_id != APP_ID or connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA:
            raise LedgerError('Not a supported WrapLedger database (schema 1)')
        yield connection
        connection.commit()
    except LedgerError:
        if connection:
            connection.rollback()
        raise
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        if connection:
            connection.rollback()
        raise LedgerError(f'Ledger operation failed: {exc}') from exc
    finally:
        if connection:
            connection.close()


def _reconcile(payload, counts):
    if {r['item'] for r in payload['dispatch']} != {r['item'] for r in counts}:
        raise LedgerError('Return items must match every dispatched item exactly; donations/new items need a separate record')
    indexed = {r['item']: r for r in counts}
    results = []
    for sent in payload['dispatch']:
        row = dict(indexed[sent['item']])
        good = row['bundles'] * sent['units_per_bundle'] + row['loose']
        accounted = good + row['damaged'] + row['lost']
        results.append({**sent, **row, 'good_returned': good, 'accounted': accounted,
                        'difference': sent['units_out'] - accounted})
    return results


def _receipt_id(payload, rev):
    return 'WL-' + _hash({'event': payload['event'], 'dispatch_digest': payload['dispatch_digest'], 'revision': rev})


def _check(payload):
    if not isinstance(payload, dict) or set(payload) != {'event', 'created_at', 'dispatch', 'dispatch_digest', 'source_digest', 'revisions', 'closure'}:
        raise LedgerError('Invalid event structure')
    _slug(payload['event'], 'event')
    _validate_rows(payload['dispatch'], DISPATCH)
    if _hash(payload['dispatch']) != payload['dispatch_digest']:
        raise LedgerError('Dispatch checksum mismatch')
    if not isinstance(payload['revisions'], list):
        raise LedgerError('Invalid count history')
    for i, rev in enumerate(payload['revisions'], 1):
        if not isinstance(rev, dict) or set(rev) != {'revision', 'operator', 'recorded_at', 'source_digest', 'counts', 'digest'}:
            raise LedgerError('Invalid count revision structure')
        if type(rev['revision']) is not int or rev['revision'] != i:
            raise LedgerError('Count revision sequence mismatch')
        _slug(rev['operator'], 'operator')
        _validate_rows(rev['counts'], RETURNS)
        if _hash(rev['counts']) != rev['digest']:
            raise LedgerError('Count checksum mismatch')
        _reconcile(payload, rev['counts'])
    closure = payload['closure']
    if closure is not None:
        if not isinstance(closure, dict) or set(closure) != {'revision', 'operator', 'closed_at', 'receipt_id'}:
            raise LedgerError('Invalid closeout structure')
        if not payload['revisions'] or closure['revision'] != len(payload['revisions']):
            raise LedgerError('Closed revision does not match latest count')
        rev = payload['revisions'][-1]
        _slug(closure['operator'], 'operator')
        if any(r['difference'] for r in _reconcile(payload, rev['counts'])):
            raise LedgerError('Closed event has an unexplained discrepancy')
        if closure['receipt_id'] != _receipt_id(payload, rev):
            raise LedgerError('Closeout receipt checksum mismatch')
    return payload


def _load(connection, event):
    _slug(event, 'event')
    row = connection.execute('SELECT payload, digest FROM events WHERE event=?', (event,)).fetchone()
    if row is None:
        raise LedgerError(f'Unknown event: {event}')
    payload = json.loads(row['payload'])
    if _hash(payload) != row['digest']:
        raise LedgerError('Event checksum mismatch; recover a verified backup')
    _check(payload)
    if payload['event'] != event:
        raise LedgerError('Event identity mismatch')
    return payload


def _save(connection, payload, new=False):
    _check(payload)
    if new:
        connection.execute('INSERT INTO events VALUES (?,?,?)', (payload['event'], _json(payload), _hash(payload)))
    else:
        connection.execute('UPDATE events SET payload=?,digest=? WHERE event=?', (_json(payload), _hash(payload), payload['event']))


def _view(payload):
    revisions = payload['revisions']
    latest = revisions[-1] if revisions else None
    reconciliation = _reconcile(payload, latest['counts']) if latest else None
    status = 'open' if latest is None else 'discrepancy' if any(r['difference'] for r in reconciliation) else 'counted'
    if payload['closure']:
        status = 'closed'
    return {'event': payload['event'], 'status': status, 'revision': len(revisions),
            'dispatch': payload['dispatch'], 'counts': latest['counts'] if latest else None,
            'reconciliation': reconciliation,
            'receipt_id': payload['closure']['receipt_id'] if payload['closure'] else None}


def create(db, event, dispatch):
    _slug(event, 'event')
    rows, source_digest = _csv(dispatch, DISPATCH)
    payload = {'event': event, 'created_at': _now(), 'dispatch': rows, 'dispatch_digest': _hash(rows),
               'source_digest': source_digest, 'revisions': [], 'closure': None}
    with _db(db, initialize=True, write=True) as connection:
        if connection.execute('SELECT 1 FROM events WHERE event=?', (event,)).fetchone():
            raise LedgerError(f'Event already exists: {event}')
        _save(connection, payload, new=True)
    return _view(payload)


def show(db, event):
    with _db(db) as connection:
        return _view(_load(connection, event))


def count(db, event, returns, operator):
    _slug(operator, 'operator')
    rows, source_digest = _csv(returns, RETURNS)
    with _db(db, write=True) as connection:
        payload = _load(connection, event)
        if payload['closure']:
            raise LedgerError('Event is closed; count revisions are locked')
        _reconcile(payload, rows)
        payload['revisions'].append({'revision': len(payload['revisions']) + 1, 'operator': operator,
                                     'recorded_at': _now(), 'source_digest': source_digest,
                                     'counts': rows, 'digest': _hash(rows)})
        _save(connection, payload)
    return _view(payload)


def close(db, event, revision, operator):
    _slug(operator, 'operator')
    if type(revision) is not int or revision < 1:
        raise LedgerError('revision must be a positive integer')
    with _db(db, write=True) as connection:
        payload = _load(connection, event)
        if payload['closure']:
            raise LedgerError('Event already closed; receipt cannot be posted twice through this ledger')
        if revision != len(payload['revisions']):
            raise LedgerError('Stale or missing revision; inspect the latest count before closing')
        rev = payload['revisions'][-1]
        if any(r['difference'] for r in _reconcile(payload, rev['counts'])):
            raise LedgerError('Unexplained discrepancy: correct counts or document an observed loss before closeout')
        payload['closure'] = {'revision': revision, 'operator': operator, 'closed_at': _now(),
                              'receipt_id': _receipt_id(payload, rev)}
        _save(connection, payload)
    return _view(payload)


def events(db):
    with _db(db) as connection:
        ids = [r[0] for r in connection.execute('SELECT event FROM events ORDER BY event')]
        return {'events': [{k: v for k, v in _view(_load(connection, event)).items()
                            if k in ('event', 'status', 'revision', 'receipt_id')} for event in ids]}


def verify(db):
    with _db(db) as connection:
        if [r[0] for r in connection.execute('PRAGMA integrity_check')] != ['ok']:
            raise LedgerError('SQLite integrity check failed')
        ids = [r[0] for r in connection.execute('SELECT event FROM events ORDER BY event')]
        for event in ids:
            _load(connection, event)
        return {'verified': True, 'schema': SCHEMA, 'events': len(ids)}


def _write_csv(path, header, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


@contextmanager
def _output(out):
    target = Path(out).absolute()
    if target.exists() or target.is_symlink():
        raise LedgerError(f'Output already exists: {target}')
    stage = None
    try:
        stage = Path(tempfile.mkdtemp(prefix='.wrapledger-', dir=target.parent))
        yield stage
        # Reserve the output directory without overwriting concurrent writers.
        target.mkdir()
        try:
            for file in stage.iterdir():
                file.rename(target / file.name)
        except OSError:
            shutil.rmtree(target)
            raise
    except OSError as exc:
        raise LedgerError(f'Cannot write output: {exc}') from exc
    finally:
        if stage:
            shutil.rmtree(stage, ignore_errors=True)


def packet(db, event, out):
    with _db(db) as connection:
        payload = _load(connection, event)
    with _output(out) as directory:
        _write_csv(directory / 'manifest.csv', DISPATCH, payload['dispatch'])
        _write_csv(directory / 'returns.csv', RETURNS, [{'item': row['item']} for row in payload['dispatch']])
        lines = [f'WrapLedger | event {event}', 'DISPATCH / RETURN COUNT SHEET',
                 'Count actual units before departure. Keep each item/size separate.',
                 'Expected yield is planning only. Count returned bundles; never copy the expected yield.',
                 'No onsite donations or new items in this manifest. Keep those separate.', '',
                 f'Dispatch digest: {payload["dispatch_digest"]}', '']
        for row in payload['dispatch']:
            bundles, loose = divmod(row['units_out'], row['units_per_bundle'])
            lines += [f'{row["item"]}: {row["label"]}',
                      f'OUT {row["units_out"]} units | {row["units_per_bundle"]} units per bundle',
                      f'PLANNED ONLY: at most {bundles} whole bundles + {loose} loose units (before damage/loss).',
                      'ACTUAL bundles ____ loose ____ damaged ____ declared lost ____',
                      'Damage/loss explanation ______________________________________', '']
        lines += ['Counter code __________  Date __________  Checked by __________',
                  'A discrepancy is unresolved until recounted or an observed exception is explicitly recorded.',
                  'Wrapping changes packaging, not total units. This sheet never posts inventory.']
        (directory / 'count-sheet.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'out': str(Path(out)), 'event': event}


def export(db, event, out):
    with _db(db) as connection:
        payload = _load(connection, event)
    if payload['closure'] is None:
        raise LedgerError('Close the balanced latest count before exporting a receipt')
    view = _view(payload)
    with _output(out) as directory:
        receipt = {'format': 'wrapledger-receipt-v1', **view, 'created_at': payload['created_at'],
                   'dispatch_digest': payload['dispatch_digest'], 'dispatch_source_sha256': payload['source_digest'],
                   'closure': payload['closure']}
        (directory / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        _write_csv(directory / 'reconciliation.csv', list(view['reconciliation'][0]), view['reconciliation'])
        (directory / 'count-history.json').write_text(json.dumps(payload['revisions'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (directory / 'README.txt').write_text(
            f'WrapLedger closeout: {event}\nReceipt ID: {view["receipt_id"]}\n\n'
            'Review in your inventory system using this stable receipt ID to avoid duplicate manual posting.\n'
            'This is count/custody evidence, not an import file or inventory adjustment instruction.\n'
            'Wrapping alone changes packaging, never total units. Do not add bundled units to units already counted.\n'
            'Apply custody transfers, damage and declared loss only under your bank policy.\n'
            'Damage and loss are operator declarations, not independently verified physical observations.\n'
            'SHA256SUMS detects accidental file changes; it is not a signature or proof of physical stock.\n', encoding='utf-8')
        sums = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in sorted(directory.iterdir())]
        (directory / 'SHA256SUMS').write_text('\n'.join(sums) + '\n', encoding='ascii')
    return {'out': str(Path(out)), 'receipt_id': view['receipt_id']}


def backup(db, out):
    target = Path(out)
    reserved = False
    try:
        # O_EXCL also rejects existing empty files and symlinks.
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        reserved = True
        # A read transaction is established by _db; backup uses its snapshot.
        with _db(db) as source:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
        result = verify(target)
        return {'out': str(target), **result}
    except (OSError, sqlite3.Error, LedgerError) as exc:
        if reserved:
            target.unlink(missing_ok=True)
        if isinstance(exc, LedgerError):
            raise
        raise LedgerError(f'Cannot create backup: {exc}') from exc
