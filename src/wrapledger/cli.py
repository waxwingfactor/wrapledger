"""Console interface; no runtime network calls."""
import argparse
import json
import os
import sys
from . import __version__
from . import core


def main(argv=None):
    parser = argparse.ArgumentParser(prog='wrapledger', description='Counted dispatch → balanced mobile wrapping return → locked receipt.')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('create', 'packet', 'count', 'show', 'close', 'export', 'events', 'verify', 'backup'):
        p = sub.add_parser(name)
        p.add_argument('--db', required=True, help='One authoritative local SQLite ledger')
        if name not in ('events', 'verify', 'backup'):
            p.add_argument('--event', required=True)
        if name == 'create':
            p.add_argument('--dispatch', required=True)
        if name == 'count':
            p.add_argument('--returns', required=True)
        if name in ('count', 'close'):
            p.add_argument('--operator', required=True, help='Operator code; a declaration, not authentication')
        if name == 'close':
            p.add_argument('--revision', type=int, required=True)
        if name in ('packet', 'export', 'backup'):
            p.add_argument('--out', required=True, help='New output path; existing paths are never overwritten')
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        result = getattr(core, command)(**args)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        sys.stdout.flush()
        return 3 if command == 'count' and result['status'] == 'discrepancy' else 0
    except core.LedgerError as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
    except (OSError, UnicodeError):
        # Stop interpreter shutdown from retrying a failed buffered stdout flush.
        try:
            with open(os.devnull, 'w') as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        # A pipe may close after a successful mutation. Inspect state before retrying.
        try:
            print(json.dumps({'error': 'Output failed; operation may have committed. Inspect ledger state before retrying.'}), file=sys.stderr)
        except (OSError, UnicodeError):
            pass
        return 2


if __name__ == '__main__':
    sys.exit(main())
