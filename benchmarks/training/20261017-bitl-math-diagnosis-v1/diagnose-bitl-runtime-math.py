import json,os,subprocess,time,hashlib,sys,shlex
from pathlib import Path
sys.path.insert(0,'scripts')
from make_samples import digest
root=Path.cwd();out=root/'build/bitl-runtime-diagnosis-v3';out.mkdir()
parent=root/'build/bitl-replay-v1';b=json.loads((parent/'build.json').read_text())
bridge=out/'bridge.cpp';bridge.write_text('namespace bit_head { int NumInputs(){return 90;} int Wlen(){return 1024;} }\n')
live=root/'build/native-fixture-v4'
runtime=out/'bit_head.o'
flags=shlex.split(next(line.split(':=',1)[1] for line in (live/'source/makefile').read_text().splitlines() if line.startswith('BITL_CXXFLAGS :=')))
model_command=['clang++','-I'+str(live/'source/src'),'-I'+str(live/'simde'),*flags,'-c',str(live/'source/src/bit_head.cpp'),'-o',str(runtime)]
with (out/'model-build.log').open('wb') as log: subprocess.run(model_command,check=True,stdout=log,stderr=subprocess.STDOUT)
command=b['command'][:-2]
command=[a for a in command if a!=str(parent/'source/bit_head.cpp')]
detmath=out/'detmath.o'
dflags=shlex.split(next(line.split(':=',1)[1] for line in (live/'source/makefile').read_text().splitlines() if line.startswith('DETNUM_CXXFLAGS :=')))
det_command=['clang++',*dflags,'-c',str(live/'source/src/detmath.cpp'),'-o',str(detmath)]
with (out/'math-build.log').open('wb') as log: subprocess.run(det_command,check=True,stdout=log,stderr=subprocess.STDOUT)
command.extend([str(runtime),str(bridge),str(detmath),'-o',str(out/'runtime-replay')])
with (out/'build.log').open('wb') as log: subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
report={'kind':'runtime-object-replay-diagnosis','command':command,'detmath_command':det_command,'detmath_source_sha256':digest(live/'source/src/detmath.cpp'),'detmath_object_sha256':digest(detmath),'model_command':model_command,'runtime_object_sha256':digest(runtime),'runtime_source_sha256':digest(root/'build/native-fixture-v4/source/src/bit_head.cpp'),'driver_sha256':digest(parent/'source/replay_trainer.cpp'),'bridge_sha256':digest(bridge),'binary_sha256':digest(out/'runtime-replay'),'results':{},'scope':'Diagnostic replay using the recompiled baseline runtime head object under its recorded makefile flags with a geometry-only bridge and the checked public driver. Does not establish trainer equivalence or authorize training.'}
for role in ('screen','holdout'):
 r=json.loads((root/('build/bitl-replay-'+role+'-v1/report.json')).read_text())
 env={k:v for k,v in os.environ.items() if not k.startswith(('REPLAY_','HUTTER_'))};env.update(r['environment'])
 cmd=[str(out/'runtime-replay'),*r['command'][1:]]
 start=time.monotonic()
 with (out/(role+'.log')).open('wb') as log: result=subprocess.run(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
 report['results'][role]={'command':cmd,'returncode':result.returncode,'seconds':time.monotonic()-start,'log_sha256':digest(out/(role+'.log'))}
 print(role,(out/(role+'.log')).read_text())
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
