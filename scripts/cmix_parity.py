#!/usr/bin/env python3
"""Reproducible native/x86 initialization, probability and cross-decoding checks."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid

from benchmark import capture
from cmix_parity_support import ROOT, SUPPORT, instrument
from competitive import ENGINE, MANIFEST, differences, inventory
from make_samples import digest
from native_cmix import PORT, WEIGHTS, write_json


def docker(args, *cmd, **kwargs):
    return subprocess.run(['docker', '--context', args.context, *map(str, cmd)], check=True, **kwargs)


def output(args, *cmd):
    return docker(args, *cmd, capture_output=True, text=True).stdout.strip()


def reference(args):
    image = json.loads(output(args, 'image', 'inspect', args.image))[0]
    pinned = image['Id']
    sha = output(args, 'run', '--rm', '--network', 'none', '--read-only', '--platform', 'linux/amd64',
                 '--entrypoint', '/usr/bin/sha256sum', pinned, '/opt/cmix-build/comp9').split()[0]
    expected = json.loads(MANIFEST.read_text())['expected_comp9_sha256']
    if sha != expected:
        raise ValueError('reference comp9 does not match the pinned upstream artifact')
    return {'image_id': pinned, 'image_tags': image.get('RepoTags'), 'comp9_sha256': sha,
            'matches_published_artifact': True, 'context': args.context}


def rng(args):
    args.output.mkdir(parents=True, exist_ok=False)
    ref = reference(args)
    probe = args.output.resolve() / 'random-probe'
    subprocess.run(['clang++', '-O2', '-std=c++17', str(SUPPORT/'random_probe.cpp'), '-o', str(probe)], check=True)
    script = '''import ctypes,hashlib,json,struct
c=ctypes.CDLL(None)
r={}
for s in [0,1,923,2147483648,4294967295]:
 c.srand(ctypes.c_uint(s)); a=[c.rand() for _ in range(10000)]
 r[s]={"first_ten":a[:10],"sha256":hashlib.sha256(struct.pack("<10000I",*a)).hexdigest()}
print(json.dumps(r))'''
    golden = json.loads(output(args, 'run', '--rm', '--network', 'none', '--read-only', '--platform', 'linux/amd64',
                               '--entrypoint', '/usr/bin/python3', ref['image_id'], '-c', script))
    for seed, row in golden.items():
        data = subprocess.check_output([str(probe), 'portable', seed, '10000'])
        row['portable_sha256'] = hashlib.sha256(data).hexdigest()
        row['matches'] = row['portable_sha256'] == row['sha256']
    report = {'reference':ref, 'draws_per_seed':10000, 'seeds':golden,
              'source_sha256':digest(SUPPORT/'linux_random.h'), 'passed':all(r['matches'] for r in golden.values())}
    write_json(args.output/'result.json',report)
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


def build_linux(args):
    ref = reference(args)
    upstream = json.loads(MANIFEST.read_text())
    if any(differences(upstream['files'],inventory(ENGINE)).values()):
        raise ValueError('modified upstream source')
    destination = args.output.resolve()
    destination.mkdir(parents=True,exist_ok=False)
    source=destination/'source'; shutil.copytree(ENGINE,source)
    shutil.copyfile(PORT/'overlay/src/native_corpus.h', source/'src/native_corpus.h')
    with (SUPPORT/'corpus.patch').open('rb') as patch:
        subprocess.run(['patch','-p1','--batch'],cwd=source,stdin=patch,check=True)
    instrument(source,portable_random=False)  # Linux uses its original libc RNG.
    name='hutter-parity-build-'+uuid.uuid4().hex[:10]
    command='cd /work/source && make CC=clang++-18 -j4 prof_use'
    cid=output(args,'create','--name',name,'--network','none','--platform','linux/amd64',
               '--memory','20g','--workdir','/work',ref['image_id'],'bash','-lc',command)
    metadata={'reference':ref,'upstream_commit':upstream['commit'],'command':command,
              'source_files':inventory(source),'support_files':inventory(SUPPORT),
              'container':name,'commit':capture('git','-C',str(ROOT),'rev-parse','HEAD'),
              'scope':'Original x86 kernels, Linux paging, upstream PGO/LTO/FP flags; shared corpus-count and diagnostics only'}
    write_json(destination/'build.json',metadata)
    try:
        docker(args,'cp',source,f'{cid}:/work/source')
        t=time.monotonic()
        with (destination/'build.log').open('wb') as log:
            docker(args,'start','-a',cid,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
        code=int(output(args,'inspect','--format','{{.State.ExitCode}}',cid))
        metadata.update(exit_code=code,wall_seconds=time.monotonic()-t)
        if code==0:
            docker(args,'cp',f'{cid}:/work/source/cmix',destination/'cmix')
            metadata['binary_sha256']=digest(destination/'cmix')
            metadata['binary_bytes']=(destination/'cmix').stat().st_size
            metadata['compiler']=output(args,'run','--rm','--network','none','--platform','linux/amd64',
                                        '--entrypoint','clang++-18',ref['image_id'],'--version')
        write_json(destination/'build.json',metadata)
        if code: raise ValueError(f'Linux build failed: see {destination / "build.log"}')
    finally:
        docker(args,'rm','-f',cid,stdout=subprocess.DEVNULL)
    print(f'Built {destination / "cmix"}',flush=True)


def first_difference(a,b,record_size=1):
    """Streaming comparison, including length differences; no false prefix pass."""
    offset=0
    with a.open('rb') as left,b.open('rb') as right:
        while True:
            x,y=left.read(65536),right.read(65536)
            if x!=y:
                n=min(len(x),len(y))
                i=next((i for i in range(n) if x[i]!=y[i]),n)
                at=offset+i; start=at//record_size*record_size
                left.seek(start);right.seek(start)
                return {'byte_offset':at,'record_index':at//record_size,
                        'left_hex':left.read(record_size).hex(),'right_hex':right.read(record_size).hex()}
            if not x: return None
            offset+=len(x)


def validate_trace(trial, init_only=False, event_limit=0):
    """Require complete, nonempty state/trace files before accepting equality."""
    errors=[]
    try:
        rows=[json.loads(line) for line in (trial/'initial.jsonl').read_text().splitlines()]
        if not rows or sum(r['bytes'] for r in rows)!=(trial/'initial.bin').stat().st_size:
            errors.append('initial state index/length mismatch')
        if not (trial/'initial.complete').is_file(): errors.append('missing initialization completion')
        if not init_only:
            count=int((trial/'trace.complete').read_text())
            if count<=0 or (trial/'probabilities.bin').stat().st_size!=8*count:
                errors.append('probability trace count/length mismatch')
            if event_limit:
                if count!=event_limit or int((trial/'prefix.complete').read_text())!=event_limit:
                    errors.append('diagnostic prefix count mismatch')
                rows=[json.loads(line) for line in (trial/'detail.jsonl').read_text().splitlines()]
                if not rows or sum(r['bytes'] for r in rows)!=(trial/'detail.bin').stat().st_size:
                    errors.append('detail index/length mismatch')
            elif (trial/'prefix.complete').exists():
                errors.append('diagnostic prefix is not a completed encoding')
    except (OSError,ValueError,KeyError,TypeError) as e:
        errors.append(str(e))
    return errors


def phase(args, platform, binary, image_id, trial, mode, input_file, page_count, init_only=False):
    trial.mkdir(parents=True,exist_ok=False)
    shutil.copy2(binary,trial/'cmix')
    for name,dest in ((WEIGHTS,WEIGHTS),('dictionary/english.dic','dictionary.dic')):
        shutil.copyfile(ENGINE/name,trial/dest)
    shutil.copyfile(input_file,trial/'input')
    flags=['--native-pages',str(page_count),mode,'dictionary.dic','input','output']
    started=time.monotonic()
    event_limit=getattr(args,'event_limit',0)
    status='failed'; code=None
    if platform=='native':
        env={**os.environ,'LC_ALL':'C','CMIX_PARITY_DIR':str(trial)}
        env.pop('CMIX_PARITY_INIT_ONLY',None)
        env.pop('CMIX_PARITY_EVENT_LIMIT',None)
        if init_only: env['CMIX_PARITY_INIT_ONLY']='1'
        if event_limit: env['CMIX_PARITY_EVENT_LIMIT']=str(event_limit)
        with (trial/'process.log').open('wb') as log:
            p=subprocess.Popen(['/usr/bin/time','-l','./cmix',*flags],cwd=trial,env=env,
                               stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try: code=p.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL);p.wait();status='timeout'
    else:
        cid=output(args,'create','--network','none','--platform','linux/amd64','--memory','20g',
                   '--workdir','/work','-e','CMIX_PARITY_DIR=/work',
                   *(['-e','CMIX_PARITY_INIT_ONLY=1'] if init_only else []),
                   *(['-e',f'CMIX_PARITY_EVENT_LIMIT={event_limit}'] if event_limit else []),
                   image_id,'/usr/bin/time','-v','./cmix',*flags)
        try:
            for file in trial.iterdir(): docker(args,'cp',file,f'{cid}:/work/{file.name}')
            with (trial/'process.log').open('wb') as log:
                try:
                    docker(args,'start','-a',cid,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
                    code=int(output(args,'inspect','--format','{{.State.ExitCode}}',cid))
                except subprocess.TimeoutExpired:
                    status='timeout';docker(args,'kill',cid,stdout=subprocess.DEVNULL)
            for name in ('output','initial.jsonl','initial.bin','initial.complete','probabilities.bin','trace.complete',
                         'prefix.complete','detail.jsonl','detail.bin'):
                subprocess.run(['docker','--context',args.context,'cp',f'{cid}:/work/{name}',str(trial/name)],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        finally: docker(args,'rm','-f',cid,stdout=subprocess.DEVNULL)
    if code==0: status='ok'
    trace_errors=validate_trace(trial,init_only,event_limit)
    if status=='ok' and trace_errors: status='invalid-trace'
    row={'platform':platform,'mode':mode,'init_only':init_only,'exit_code':code,'status':status,
         'trace_errors':trace_errors,'event_limit':event_limit,
         'wall_seconds':time.monotonic()-started,'command':['./cmix',*flags],
         'input_sha256':digest(input_file),'binary_sha256':digest(binary),
         'files':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in trial.iterdir()
                  if p.name in ('output','initial.bin','initial.jsonl','probabilities.bin','trace.complete','initial.complete',
                                'prefix.complete','detail.jsonl','detail.bin')}}
    if status!='ok': row['failure_log_tail']=(trial/'process.log').read_text(errors='replace')[-8192:]
    write_json(trial/'phase.json',row)
    print(f'{trial.name}: {status}, {row["wall_seconds"]:.2f}s',flush=True)
    return row


def compare(args):
    native=args.native.resolve();linux=args.linux.resolve();run=args.output.resolve()
    nm=json.loads((native/'build.json').read_text());lm=json.loads((linux/'build.json').read_text())
    bins={'native':native/'source/cmix','linux':linux/'cmix'}
    for name,meta in [('native',nm),('linux',lm)]:
        if digest(bins[name])!=meta['binary_sha256']: raise ValueError(f'{name} binary differs from build record')
        for asset in (WEIGHTS,'dictionary/english.dic'):
            if digest(ENGINE/asset)!=meta['source_files'][asset]['sha256']:
                raise ValueError(f'{name} build asset changed: {asset}')
    manifest=json.loads(args.manifest.read_text());input_file=args.input.resolve()
    if not any(s['sha256']==digest(input_file) and s['bytes']==input_file.stat().st_size for s in manifest['samples']):
        raise ValueError('sample does not match manifest')
    ref=reference(args)
    if ref['image_id']!=lm['reference']['image_id']:raise ValueError('Linux runtime image changed')
    run.mkdir(parents=True,exist_ok=False)
    report={'date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'commit':capture('git','-C',str(ROOT),'rev-parse','HEAD'),
            'reference':ref,'native_build':nm,'linux_build':lm,'manifest':manifest,
            'runner_sha256':digest(Path(__file__)),'phases':{},
            'scope':'initialization' if args.init_only else ('diagnostic prefix' if args.event_limit else 'cross-platform fixture'),
            'event_limit':args.event_limit,
            'assets':{n:{'sha256':digest(ENGINE/n),'bytes':(ENGINE/n).stat().st_size} for n in (WEIGHTS,'dictionary/english.dic')}}
    write_json(run/'report.json',report)
    # Sequential: measured elapsed time includes emulator/container overhead.
    for name in ('native','linux'):
        key=name+'-encode'
        report['phases'][key]=phase(args,name,bins[name],ref['image_id'],run/key,'-c',input_file,manifest['page_count'],args.init_only)
        write_json(run/'report.json',report)
    def compare_file(name,width=1):
        a,b=run/'native-encode'/name,run/'linux-encode'/name
        if not(a.is_file() and b.is_file()):return {'status':'missing'}
        diff=first_difference(a,b,width)
        return {'equal':diff is None,'first_difference':diff,'native_sha256':digest(a),'linux_sha256':digest(b)}
    report['initialization']=compare_file('initial.bin',4)
    if args.init_only:
        report['passed']=all(p['status']=='ok' and 'initial.complete' in p['files'] for p in report['phases'].values()) and report['initialization'].get('equal',False)
    elif args.event_limit:
        report['probabilities']=compare_file('probabilities.bin',8)
        report['details']=compare_file('detail.bin',4)
        report['detail_index']=compare_file('detail.jsonl')
        diff=report['details'].get('first_difference')
        if diff and report['detail_index'].get('equal'):
            offset=0
            for line in (run/'native-encode/detail.jsonl').read_text().splitlines():
                row=json.loads(line)
                if offset+row['bytes']>diff['byte_offset']:
                    diff['stage']=row;diff['float_index']=(diff['byte_offset']-offset)//4
                    break
                offset+=row['bytes']
        report['passed']=(all(p['status']=='ok' for p in report['phases'].values())
                          and all(report[k].get('equal',False) for k in ('initialization','probabilities','details','detail_index')))
        report['decoding_skipped']='Diagnostic prefix only; no valid payload or full compatibility claim.'
    else:
        report['probabilities']=compare_file('probabilities.bin',8)
        report['payload']=compare_file('output')
        # Divergent adaptive streams cannot cross-decode reliably; diagnose the
        # first difference before spending hours decoding a known mismatch.
        matched=all(report[k].get('equal',False) for k in ('initialization','probabilities','payload'))
        if not matched: report['decoding_skipped']='Encoding differs; resolve the first divergence before cross-decoding.'
        write_json(run/'report.json',report)
        for encoder in (('native','linux') if matched else ()):
            encoded=run/(encoder+'-encode')/'output'
            if report['phases'][encoder+'-encode']['status']!='ok' or not encoded.is_file():continue
            for decoder in ('native','linux'):
                key=encoder+'-to-'+decoder
                row=phase(args,decoder,bins[decoder],ref['image_id'],run/key,'-d',encoded,manifest['page_count'])
                row['roundtrip']=row['status']=='ok' and (run/key/'output').is_file() and digest(run/key/'output')==digest(input_file)
                row['trace_matches_encoder']=(row['status']=='ok' and first_difference(
                    run/key/'probabilities.bin',run/(encoder+'-encode')/'probabilities.bin',8) is None)
                report['phases'][key]=row;write_json(run/'report.json',report)
        report['passed']=(report['initialization'].get('equal',False) and report['probabilities'].get('equal',False)
                          and report['payload'].get('equal',False) and len(report['phases'])==6
                          and all(p['status']=='ok' and 'trace.complete' in p['files'] for p in report['phases'].values())
                          and all(p.get('roundtrip',False) and p.get('trace_matches_encoder',False)
                                  for k,p in report['phases'].items() if '-to-' in k))
    write_json(run/'report.json',report)
    if args.record:
        target=ROOT/'benchmarks/parity'/args.record
        target.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(run/'report.json',target/'report.json')
        for key in report['phases']:
            # Preserve diagnostics and timings, not large binaries or trace streams.
            for name in ('process.log','initial.jsonl','detail.jsonl'):
                f=run/key/name
                if f.exists():shutil.copyfile(f,target/(key+'-'+name))
    print(json.dumps({k:v for k,v in report.items() if k in ('passed','initialization','payload','probabilities','details')},indent=2))
    return 0 if report['passed'] else 1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context',default='colima-hutter')
    p.add_argument('--image',default='hutter-cmix-neif:baseline')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('rng','build-linux','compare'):
        sp=sub.add_parser(name);sp.add_argument('--output',type=Path,required=True)
        if name!='rng':sp.add_argument('--timeout',type=float,default=7200)
        if name=='compare':
            sp.add_argument('--native',type=Path,required=True);sp.add_argument('--linux',type=Path,required=True)
            sp.add_argument('--manifest',type=Path,required=True);sp.add_argument('--input',type=Path,required=True)
            sp.add_argument('--init-only',action='store_true');sp.add_argument('--record')
            sp.add_argument('--event-limit',type=int,default=0,help='diagnostic prefix only, with model-stage snapshots; no valid payload')
    args=p.parse_args()
    if getattr(args,'timeout',1)<=0:p.error('timeout must be positive')
    if getattr(args,'event_limit',0)<0:p.error('event limit must be nonnegative')
    if getattr(args,'event_limit',0) and args.init_only:p.error('event limit and init-only are mutually exclusive')
    if getattr(args,'record',None):
        import re
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',args.record):p.error('invalid record ID')
        if (ROOT/'benchmarks/parity'/args.record).exists():p.error('record already exists')
    try:return {'rng':rng,'build-linux':build_linux,'compare':compare}[args.command](args)
    except (OSError,ValueError,subprocess.SubprocessError) as e:p.exit(1,str(e)+'\n')


if __name__=='__main__':raise SystemExit(main())
