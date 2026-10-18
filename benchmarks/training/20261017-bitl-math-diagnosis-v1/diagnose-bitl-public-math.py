import json,os,subprocess,time,sys
from pathlib import Path
sys.path.insert(0,'scripts')
from make_samples import digest
root=Path.cwd();out=root/'build/bitl-public-math-diagnosis-v1';out.mkdir()
parent=root/'build/bitl-replay-v1';b=json.loads((parent/'build.json').read_text())
mathobj=root/'build/bitl-runtime-diagnosis-v3/detmath.o'
command=b['command'][:-2]+[str(mathobj),'-o',str(out/'public-replay')]
with (out/'build.log').open('wb') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
report={'kind':'public-trainer-runtime-math-diagnosis','parent_build_sha256':digest(parent/'build.json'),'command':command,'detmath_object_sha256':digest(mathobj),'binary_sha256':digest(out/'public-replay'),'results':{}}
for role in ('screen','holdout'):
 r=json.loads((root/('build/bitl-replay-'+role+'-v1/report.json')).read_text())
 env={k:v for k,v in os.environ.items() if not k.startswith(('REPLAY_','HUTTER_'))};env.update(r['environment'])
 cmd=[str(out/'public-replay'),*r['command'][1:]]
 start=time.monotonic()
 with (out/(role+'.log')).open('wb') as log:result=subprocess.run(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
 report['results'][role]={'command':cmd,'returncode':result.returncode,'seconds':time.monotonic()-start,'log_sha256':digest(out/(role+'.log'))}
 print(role,(out/(role+'.log')).read_text())
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
