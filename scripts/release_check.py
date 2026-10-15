#!/usr/bin/env python3
"""Install actual supplied wheel/sdist outside the checkout and exercise both."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import venv

SMOKE = r'''
import csv, hashlib, json, pathlib, shutil, socket, sys
import wrapledger
from wrapledger import core
root = pathlib.Path.cwd()
assert pathlib.Path(wrapledger.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
def offline(*a, **k): raise AssertionError('Unexpected runtime network access')
socket.socket = offline
def csvfile(name, body):
 p=root/name; p.write_text(body,encoding='utf-8'); return p
dispatch=csvfile('dispatch.csv','item,label,units_per_bundle,units_out\na,Size A,25,102\nb,Size B,10,35\n')
db=root/'event.db'
assert core.create(db,'demo',dispatch)['status']=='open'
core.packet(db,'demo',root/'paper')
blank=list(csv.DictReader((root/'paper'/'returns.csv').open()))
assert blank[0]['bundles']==''
returns=csvfile('returns.csv','item,bundles,loose,damaged,lost,exception_note\na,4,1,0,0,\nb,3,5,0,0,\n')
assert core.count(db,'demo',returns,'counter')['status']=='discrepancy'
try: core.close(db,'demo',1,'lead')
except core.LedgerError: pass
else: raise AssertionError('Unbalanced close accepted')
returns.write_text('item,bundles,loose,damaged,lost,exception_note\na,4,1,1,0,Torn unit observed\nb,3,5,0,0,\n')
assert core.count(db,'demo',returns,'counter')['revision']==2
try: core.close(db,'demo',1,'lead')
except core.LedgerError: pass
else: raise AssertionError('Stale close accepted')
receipt=core.close(db,'demo',2,'lead')['receipt_id']
try: core.close(db,'demo',2,'lead')
except core.LedgerError: pass
else: raise AssertionError('Repeated close accepted')
core.export(db,'demo',root/'receipt')
for line in (root/'receipt'/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ')
 assert hashlib.sha256((root/'receipt'/name).read_bytes()).hexdigest()==digest
core.backup(db,root/'backup.db')
shutil.rmtree(root/'paper'); dispatch.unlink(); returns.unlink(); db.unlink()
moved=root/'relocated'; moved.mkdir(); shutil.move(root/'backup.db',moved/'ledger.db')
assert core.verify(moved/'ledger.db')['verified']
assert core.show(moved/'ledger.db','demo')['receipt_id']==receipt
core.export(moved/'ledger.db','demo',moved/'receipt')
assert json.loads((moved/'receipt'/'receipt.json').read_text())['receipt_id']==receipt
print(json.dumps({'version':wrapledger.__version__,'installed_in_fresh_venv':True,'offline_runtime':True,'relocated_after_inputs_removed':True,'discrepancy_and_stale_and_repeat_close_rejected':True,'receipt_hashes_verified':True}))
'''


def run(command, cwd, env):
    result = subprocess.run([str(s) for s in command], cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', required=True, type=Path)
    args = parser.parse_args()
    artifacts = sorted(args.dist.resolve().glob('wrapledger-*'))
    wheels = [p for p in artifacts if p.suffix == '.whl']
    sources = [p for p in artifacts if p.name.endswith('.tar.gz')]
    assert len(wheels) == len(sources) == 1, 'Exactly one wheel and sdist required'
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
    results = []
    with tempfile.TemporaryDirectory(prefix='wrapledger-release-') as temporary:
        root = Path(temporary)
        for index, artifact in enumerate(wheels + sources):
            area = root/str(index); area.mkdir()
            venv.EnvBuilder(with_pip=True).create(area/'venv')
            binaries = area/'venv'/('Scripts' if os.name == 'nt' else 'bin')
            python = binaries/('python.exe' if os.name == 'nt' else 'python')
            local_env = dict(env, PATH=str(binaries) + os.pathsep + env.get('PATH', ''))
            if artifact.suffix == '.whl':
                run([python,'-m','pip','install','--no-index','--no-deps',artifact],area,local_env)
            else:
                run([python,'-m','pip','install','setuptools>=77','wheel'],area,local_env)
                run([python,'-m','pip','install','--no-build-isolation','--no-deps',artifact],area,local_env)
                with tarfile.open(artifact) as archive:
                    members = archive.getnames()
                    for required in ('tests/test_acceptance.py','docs/contract.md','docs/research.md','examples/dispatch.csv','scripts/release_check.py'):
                        assert any(name.endswith('/'+required) for name in members), required
                    # Only inspect/extract our own built source distribution with explicit safe filter.
                    archive.extractall(area/'source', filter='data')
                source = next((area/'source').iterdir())
                run([python,'-m','unittest','discover','-s',source/'tests','-v'],area,local_env)
            version = run([binaries/('wrapledger.exe' if os.name=='nt' else 'wrapledger'),'--version'],area,local_env).strip()
            report = json.loads(run([python,'-I','-c',SMOKE],area,local_env))
            results.append({'artifact':artifact.name,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(), 'cli_version':version, **report})
    print(json.dumps({'python':platform.python_version(),'platform':platform.system(),'artifacts':results},indent=2))


if __name__ == '__main__':
    main()
