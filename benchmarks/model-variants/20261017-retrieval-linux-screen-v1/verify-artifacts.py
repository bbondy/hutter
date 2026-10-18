import json,shutil,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()))
from competitive import ENGINE,inventory
from native_cmix import PORT
from cmix_parity_support import SUPPORT,instrument
from cmix_fixture_support import instrument_fixture,context_report,validate_context
from cmix_preprocess_support import apply_portable_preprocessing
from cmix_retrieval_support import apply as apply_retrieval
from make_samples import digest
from model_history import compatible_builds,validate_runner
from order_history import checked_restoration
root=Path('build/ci-retrieval-v1');workflow=json.loads((root/'workflow.json').read_text());assert workflow['conclusion']=='success'
with tempfile.TemporaryDirectory(prefix='hutter-linux-source-verification-') as temp:
 source=Path(temp)/'source';shutil.copytree(ENGINE,source)
 shutil.copyfile(PORT/'overlay/src/native_corpus.h',source/'src/native_corpus.h')
 subprocess.run(['patch','-p1','--batch','--fuzz=0'],cwd=source,input=(SUPPORT/'corpus.patch').read_bytes(),check=True,capture_output=True)
 apply_portable_preprocessing(source);instrument_fixture(source);instrument(source,portable_random=False)
 baseline_files=inventory(source)
 for role in ('screen','holdout'):
  artifact=root/f'linux-exact-target-{role}-39085744092'/role;comp=artifact/'comparison'
  report=json.loads((comp/'report.json').read_text());protocol=json.loads((comp/'protocol.json').read_text());manifest=json.loads((comp/'manifest.json').read_text())
  assert digest(comp/'manifest.json')==report['manifest_sha256']==protocol['fixtures'][role]['manifest_sha256']
  assert digest(comp/'protocol.json')==report['protocol_sha256']
  assert protocol['parent_protocol_sha256']==digest(Path('benchmarks/model-variants/20261017-retrieval-protocol-v1/protocol.json'))
  sample=next(s for s in manifest['samples'] if s['variant']=='upstream')
  assert sample['sha256']==report['input_sha256']==protocol['fixtures'][role]['input_sha256']
  assert report['raw_sha256']==manifest['raw_sha256'] and report['raw_bytes']==manifest['raw_bytes']
  base=json.loads((artifact/'run-baseline/metadata.json').read_text())
  assert base['build']['source_files']==baseline_files
  for name,row in report['variants'].items():
   run=artifact/('run-'+name);meta=json.loads((run/'metadata.json').read_text());result=json.loads((run/'results.jsonl').read_text())
   assert meta['commit']==workflow['headSha']
   assert digest(run/'metadata.json')==row['metadata_sha256']==digest(comp/name/'metadata.json')
   assert digest(run/'results.jsonl')==row['results_sha256']==digest(comp/name/'results.jsonl')
   assert json.loads((artifact/('build-'+name)/'build.json').read_text())==meta['build']
   compatible_builds(base['build'],meta['build'],source);validate_runner(meta,protocol)
   assert all(meta[k]==base[k] for k in ('platform','machine','cpu','side_data','native_arguments'))
   for asset,info in meta['side_data'].items():assert digest(ENGINE/asset)==info['sha256'] and (ENGINE/asset).stat().st_size==info['bytes']
   assert digest(run/'cmix')==row['binary_sha256']==meta['binary_sha256']==meta['build']['binary_sha256']
   assert (run/'cmix').stat().st_size==row['binary_bytes']==meta['binary_bytes']
   assert digest(run/'payload.cmix')==row['archive_sha256']==result['archive_sha256']
   assert (run/'payload.cmix').stat().st_size==row['payload_bytes']==result['archive_bytes']
   assert digest(run/'restored')==sample['sha256'] and (run/'restored').stat().st_size==sample['bytes']
   assert result['roundtrip'] and result['context_valid'] and row['original_bytes_roundtrip']
   context={phase:context_report(run/(phase+'.log')) for phase in ('compress','decompress')}
   assert context==row['context'];validate_context(context['compress'],context['decompress'],manifest)
   for phase in context:
    assert digest(run/(phase+'.log'))==row['log_sha256'][phase]==digest(comp/(name+'-'+phase+'.log'))
    assert result[phase]['status']=='ok'
   restored=Path(temp)/(role+'-'+name+'.xml')
   subprocess.run([str(Path('build/native-fixture-v4/prepare-sample').resolve()),*manifest['helper_arguments'],'decode',str((run/'restored').resolve()),str(restored)],check=True)
   assert checked_restoration(restored.read_bytes(),sample,manifest)==row['restored_raw_sha256']==manifest['raw_sha256']
   assert row['delta_bytes_vs_baseline']==row['payload_bytes']-report['variants']['baseline']['payload_bytes']
  dest=Path(f'benchmarks/model-variants/20261017-retrieval-linux-{role}-v1');shutil.copytree(comp,dest)
  shutil.copyfile(artifact/'host.json',dest/'host.json')
  proof={'workflow_run':workflow['url'],'artifact':artifact.parent.name,'source_commit':workflow['headSha'],'verification':'Reconstructed and matched every baseline Linux source file; checked the frozen exact-target rewrite, compiler/runner/asset controls, all downloaded binary/archive/restored/log/metadata hashes, context counters and original raw XML using the canonical Mac inverse helper. Both models ran serially on the fixture host.','scope':'Canonical fixture payloads; no full score or cross-platform speed claim.'}
  (dest/'ci-provenance.json').write_text(json.dumps(proof,indent=2)+'\n')
  shutil.copyfile(__file__,dest/'verify-artifacts.py')
  print(role,[(n,r['payload_bytes'],r['delta_bytes_vs_baseline']) for n,r in report['variants'].items()])
