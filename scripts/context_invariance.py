#!/usr/bin/env python3
"""Repeat an encoding with context reports disabled; verify against a saved trial."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from benchmark import measured
from cmix_fixture_support import corpus_arguments
from competitive import ENGINE
from make_samples import digest
from native_cmix import WEIGHTS, write_json


def encode(args):
    baseline = args.baseline.resolve()
    metadata = json.loads((baseline / 'metadata.json').read_text())
    manifest = json.loads(args.manifest.read_text())
    input_file = args.input.resolve()
    flags = corpus_arguments(manifest, metadata['build'])
    if flags[0] != '--native-corpus' or flags != metadata['native_arguments']:
        raise ValueError('requires the same corrected corpus protocol')
    if not any(s['sha256'] == digest(input_file) and s['bytes'] == input_file.stat().st_size
               for s in manifest['samples']):
        raise ValueError('input differs from manifest')
    if digest(baseline / 'cmix') != metadata['binary_sha256']:
        raise ValueError('baseline binary changed')
    for name, info in metadata['side_data'].items():
        if digest(ENGINE / name) != info['sha256']:
            raise ValueError('baseline asset changed')
    run = args.output.resolve()
    run.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(baseline / 'cmix', run / 'cmix')
    (run / 'cmix').chmod(0o755)
    for name, dest in ((WEIGHTS, WEIGHTS), ('dictionary/english.dic', 'dictionary.dic')):
        shutil.copyfile(ENGINE / name, run / dest)
    archive = run / 'payload.cmix'
    command = [str(run / 'cmix'), *flags, '-c', 'dictionary.dic', str(input_file), str(archive)]
    report = {'kind': 'context-telemetry-invariance', 'baseline': str(baseline),
              'baseline_metadata_sha256': digest(baseline / 'metadata.json'),
              'binary_sha256': metadata['binary_sha256'], 'input_sha256': digest(input_file),
              'manifest_sha256': digest(args.manifest), 'side_data': metadata['side_data'],
              'script_sha256': digest(Path(__file__)), 'context_report': '0'}
    os.chdir(run)
    os.environ['CMIX_CONTEXT_REPORT'] = '0'
    result = measured(command, run / 'compress.log', args.timeout)
    report.update(compress=result, log_sha256=digest(run / 'compress.log'))
    if result['status'] == 'ok':
        report.update(archive_sha256=digest(archive), archive_bytes=archive.stat().st_size)
    write_json(run / 'report.json', report)
    if result['status'] != 'ok':
        raise ValueError('encoding failed; see saved log')
    print('Encoding complete; use verify after the baseline round trip finishes.')


def verify(args):
    run = args.run.resolve()
    report = json.loads((run / 'report.json').read_text())
    baseline = Path(report['baseline'])
    if digest(baseline / 'metadata.json') != report['baseline_metadata_sha256']:
        raise ValueError('baseline metadata changed')
    rows = [json.loads(line) for line in (baseline / 'results.jsonl').read_text().splitlines()]
    rows = [r for r in rows if r['input_sha256'] == report['input_sha256']]
    if len(rows) != 1 or not rows[0]['roundtrip'] or not rows[0].get('context_valid'):
        raise ValueError('requires one successful baseline with validated context reports')
    row = rows[0]
    archive = Path(row['compress']['command'][-1])
    if (digest(archive) != row['archive_sha256'] or digest(run / 'payload.cmix') != report['archive_sha256']
            or digest(run / 'compress.log') != report['log_sha256']):
        raise ValueError('saved artifact changed')
    if 'CMIX_CONTEXT ' in (run / 'compress.log').read_text(errors='replace'):
        raise ValueError('context reports were not disabled')
    report.update(baseline_results_sha256=digest(baseline / 'results.jsonl'),
                  baseline_archive_sha256=row['archive_sha256'],
                  archive_matches=report['archive_sha256'] == row['archive_sha256'],
                  scope='One repeated screen-source encoding; identical archive inherits its verified decoder round trip.')
    write_json(run / 'report.json', report)
    if not report['archive_matches']:
        raise ValueError('telemetry changed the archive')
    print(f'Identical {report["archive_bytes"]}-byte archive with context reports disabled.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    enc = sub.add_parser('encode')
    for option in ('baseline', 'manifest', 'input', 'output'):
        enc.add_argument('--' + option, required=True, type=Path)
    enc.add_argument('--timeout', type=float, default=3600)
    check = sub.add_parser('verify')
    check.add_argument('run', type=Path)
    args = parser.parse_args()
    try:
        (encode if args.command == 'encode' else verify)(args)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
