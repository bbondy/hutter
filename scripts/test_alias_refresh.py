from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cmix_alias_support import AFTER


class AliasRefreshTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("clang++"), "requires a C++ compiler")
    def test_compiled_callback_updates_only_after_last_eligible_row(self):
        # Compile the exact replacement function against small observable
        # stand-ins, so missing the cached first-bit refresh is also caught.
        code = r'''
#include <cassert>
namespace transformer { bool active=true; bool Active(){return active;} }
namespace alias_prompt { int remaining=0; bool Laeuft(){return remaining>0;} }
namespace timestamp_skip { bool skipping=false; bool Laeuft(){return skipping;} }
struct Byte { float prior=0.3f; const float* BytePredict(){return &prior;} };
struct Engine {
  int calls=0; bool gate=false; float row=0.75f;
  const float* Step(const float*,unsigned int) {++calls; --alias_prompt::remaining; return &row;}
  bool GateMasked(){return gate;}
};
struct Slot {
  int sets=0,predicts=0; float probability=0.25f;
  void SetProbs(const float* row){++sets; probability=*row;}
  const float* Predict(){++predicts; return &probability;}
};
float tf1_slot_output=0.25f;
struct Predictor {
  Engine* tf1_engine_; Byte* byte_model_; Slot* tf1_slot_;
  void ObserveTfOnlyByte(unsigned int byte);
};
''' + AFTER + r'''
int main() {
  Engine engine; Byte byte; Slot slot; Predictor p{&engine,&byte,&slot};
  alias_prompt::remaining=2;
  p.ObserveTfOnlyByte(1);
  assert(engine.calls==1 && slot.sets==0 && tf1_slot_output==0.25f);
  p.ObserveTfOnlyByte(2);
  assert(engine.calls==2 && slot.sets==1 && slot.predicts==1 && tf1_slot_output==0.75f);
  for(int guard=0;guard<3;++guard) {
    engine.gate=guard==0; transformer::active=guard!=1; timestamp_skip::skipping=guard==2;
    alias_prompt::remaining=1; p.ObserveTfOnlyByte(3);
    assert(slot.sets==1 && slot.predicts==1);
  }
  p.tf1_engine_=nullptr; p.ObserveTfOnlyByte(4);
  assert(engine.calls==5 && slot.sets==1);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory) / "probe.cpp", Path(directory) / "probe"
            source.write_text(code)
            subprocess.run(["clang++", "-std=c++17", "-O2", str(source), "-o", str(binary)],
                           check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)
