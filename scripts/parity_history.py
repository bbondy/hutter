#!/usr/bin/env python3
"""Read saved native/Linux fixture results without treating them as prize scores."""
import argparse
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]/'benchmarks/parity'


def fixture(report):
    if report.get('scope')!='cross-platform fixture':
        return None
    phases=report['phases']
    native,linux=phases['native-encode'],phases['linux-encode']
    if native['status']!='ok' or linux['status']!='ok':
        raise ValueError('incomplete encode phases')
    input_sha=native['input_sha256']
    if linux['input_sha256']!=input_sha:
        raise ValueError('platforms encoded different inputs')
    manifest=report['manifest']
    sample=next((s for s in manifest['samples'] if s['sha256']==input_sha),None)
    if sample is None:
        raise ValueError('manifest does not describe the encoded input')
    return {'input_sha256':input_sha,'prepared_bytes':sample['bytes'],
            'source_offset':manifest.get('source_offset'),'page_count':manifest['page_count'],
            'native_payload_bytes':native['files']['output']['bytes'],
            'linux_payload_bytes':linux['files']['output']['bytes'],
            'payloads_equal':report['payload']['equal'],
            'assets':report['assets'],'reference_image_id':report['reference']['image_id'],
            'upstream_commits':(report['native_build']['upstream_commit'],
                                report['linux_build']['upstream_commit'])}


def decoder_fixture(report):
    if report.get('scope')!='same-platform decoder validation':
        return None
    row=report['decoder_phase']
    sample=next((s for s in report['manifest']['samples']
                 if s['sha256']==report['prepared_sha256']),None)
    if sample is None:
        raise ValueError('decoder manifest does not describe restored input')
    if report['payload_sha256']!=report['encoder_phase']['files']['output']['sha256']:
        raise ValueError('decoder input does not match encoder payload')
    return {'platform':row['platform'],'page_count':report['manifest']['page_count'],
            'prepared_bytes':sample['bytes'],
            'payload_bytes':report['encoder_phase']['files']['output']['bytes'],
            'roundtrip':row['roundtrip'],'trace_matches_encoder':row['trace_matches_encoder'],
            'passed':report['passed'],'wall_seconds':row['wall_seconds']}


def load(record_id,root=ROOT):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',record_id):
        raise ValueError('invalid record ID')
    result=fixture(json.loads((root/record_id/'report.json').read_text()))
    if result is None:
        raise ValueError(f'{record_id} is not a completed fixture encoding comparison')
    return result


def comparable(before,after):
    fields=('input_sha256','prepared_bytes','page_count','assets',
            'reference_image_id','upstream_commits')
    changed=[field for field in fields if before[field]!=after[field]]
    if changed:
        raise ValueError('records are not comparable; changed '+', '.join(changed))


def list_records(root=ROOT):
    print('| Record | Offset | Pages | Prepared bytes | Native payload | Linux payload | Same payload? |')
    print('|---|---:|---:|---:|---:|---:|---|')
    for entry in sorted(root.iterdir()):
        if not (entry/'report.json').is_file():continue
        report=json.loads((entry/'report.json').read_text())
        row=fixture(report)
        if row is None:continue
        offset=row['source_offset'] if row['source_offset'] is not None else '—'
        print(f'| {entry.name} | {offset} | {row["page_count"]} | {row["prepared_bytes"]} | '
              f'{row["native_payload_bytes"]} | {row["linux_payload_bytes"]} | '
              f'{"yes" if row["payloads_equal"] else "no"} |')


def list_decoders(root=ROOT):
    print('| Record | Platform | Pages | Prepared bytes | Payload bytes | Restored? | Trace matched? | Passed? | Decode seconds |')
    print('|---|---|---:|---:|---:|---|---|---|---:|')
    for entry in sorted(root.iterdir()):
        if not (entry/'report.json').is_file():continue
        row=decoder_fixture(json.loads((entry/'report.json').read_text()))
        if row is None:continue
        yes=lambda key:'yes' if row[key] else 'no'
        print(f'| {entry.name} | {row["platform"]} | {row["page_count"]} | '
              f'{row["prepared_bytes"]} | {row["payload_bytes"]} | '
              f'{yes("roundtrip")} | {yes("trace_matches_encoder")} | '
              f'{yes("passed")} | {row["wall_seconds"]:.2f} |')


def compare(before_id,after_id,root=ROOT):
    before,after=load(before_id,root),load(after_id,root)
    comparable(before,after)
    print('Payload bytes only; negative delta is smaller. Decoder and full prize gates are separate.')
    print('| Platform | Before | After | Delta bytes |')
    print('|---|---:|---:|---:|')
    for platform in ('native','linux'):
        field=platform+'_payload_bytes'
        print(f'| {platform} | {before[field]} | {after[field]} | {after[field]-before[field]:+d} |')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('list')
    sub.add_parser('decoders')
    difference=sub.add_parser('compare')
    difference.add_argument('before')
    difference.add_argument('after')
    args=parser.parse_args()
    try:
        if args.command=='list':list_records()
        elif args.command=='decoders':list_decoders()
        else:compare(args.before,args.after)
    except (OSError,ValueError,KeyError,TypeError) as e:parser.exit(1,str(e)+'\n')


if __name__=='__main__':main()
