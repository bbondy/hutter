"""Shared instrumentation for native and original-x86 development binaries."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "engines/ports/cmix-neif-parity"


def instrument(source, portable_random=False):
    """Fail closed when upstream hooks drift; apply once to a disposable copy."""
    def change(name, old, new, count=1):
        path = source / "src" / name
        text = path.read_text()
        if text.count(old) != count:
            raise ValueError(f"instrumentation anchor changed: {name}: {old!r}")
        path.write_text(text.replace(old, new))

    shutil.copyfile(SUPPORT / "parity_trace.h", source / "src/parity_trace.h")
    # Both sides observe the same initialized arrays, independent of addresses.
    change("mixer/lstm-layer.hpp", '#include "lstm-layer.h"',
           '#include "lstm-layer.h"\n#include "../parity_trace.h"')
    anchor = '\n}\n\ninline void LstmLayer::ForwardPass'
    snapshot = '''
  if (parity_trace::Enabled()) {
    NeuronLayer* parity_gates[] = {&forget_gate_, &input_node_, &output_gate_};
    for (auto* gate : parity_gates) {
      for (const auto& row : gate->weights_)
        parity_trace::State("lstm_weights", &row[0], row.size()*sizeof(float));
      parity_trace::State("lstm_half",gate->weights_h_.data(),gate->weights_h_.size()*sizeof(lstmw_t));
      parity_trace::State("lstm_extra",gate->dx_w_.data(),gate->dx_w_.size()*sizeof(float));
    }
  }
'''
    # The anchor also appears after ForwardPass itself; target constructor end.
    path = source / "src/mixer/lstm-layer.hpp"
    text = path.read_text()
    position = text.index(anchor)
    path.write_text(text[:position] + snapshot + text[position:])
    change("models/indirect.h", '#include "model.h"', '#include "model.h"\n#include "../parity_trace.h"')
    change("models/indirect.h", '  map_offset_ = rand() % (map_.size() - 257);',
           '  map_offset_ = rand() % (map_.size() - 257);\n  parity_trace::State("indirect_offset", &map_offset_, sizeof(map_offset_));')
    change("predictor.cpp", '#include "predictor.h"', '#include "predictor.h"\n#include "parity_trace.h"')
    change("predictor.cpp", '  sigmoid_.S52Activate();', '  sigmoid_.S52Activate();\n  parity_trace::Ready();')
    for name in ("encoder", "decoder"):
        change(f"coder/{name}.cpp", f'#include "{name}.h"',
               f'#include "{name}.h"\n#include "../parity_trace.h"')
        change(f"coder/{name}.h", '#include "../run_mode.h"', '#include "../run_mode.h"\n#include "../parity_trace.h"')
        change(f"coder/{name}.h", 'inline void ObserveKnownBit(int bit) { p_->ObserveKnownBit(bit); }',
               'inline void ObserveKnownBit(int bit) { parity_trace::Event(3, bit, 0); p_->ObserveKnownBit(bit); }')
    change("coder/encoder.cpp", '    p_->Perceive(bit);\n    return;',
           '    parity_trace::Event(1, bit, 0);\n    p_->Perceive(bit);\n    return;')
    change("coder/encoder.cpp", '  const unsigned int xmid =',
           '  parity_trace::Event(0, bit, p);\n  const unsigned int xmid =', count=2)
    change("coder/encoder.cpp", '  if (p > 65534) p = 65534;\n  parity_trace::Event(0, bit, p);',
           '  if (p > 65534) p = 65534;\n  parity_trace::Event(2, bit, p);')
    change("coder/decoder.cpp", '      p_->Perceive(bit);\n      return bit;',
           '      parity_trace::Event(1, bit, 0);\n      p_->Perceive(bit);\n      return bit;')
    # Normal event after bit selection, before predictor/interval renormalization.
    change("coder/decoder.cpp", '  if (bit_head::Enabled()\n      && !bit_head::AuxOff()\n      && !bit_head::MetaOff()\n      && !p_->AdepthSkipped()\n      ) bit_head::Observe(bit);',
           '  parity_trace::Event(0, bit, p);\n  if (bit_head::Enabled()\n      && !bit_head::AuxOff()\n      && !bit_head::MetaOff()\n      && !p_->AdepthSkipped()\n      ) bit_head::Observe(bit);')
    change("coder/decoder.cpp", 'int Decoder::DecodeRawBit(unsigned int p) {',
           'int Decoder::DecodeRawBit(unsigned int p) {')
    path = source / "src/coder/decoder.cpp"
    text = path.read_text(); start = text.index('int Decoder::DecodeRawBit')
    text = text[:start] + text[start:].replace('  while (((x1_^x2_)', '  parity_trace::Event(2, bit, p);\n  while (((x1_^x2_)', 1)
    path.write_text(text)
    change("runner.cpp", 'exit:\n  return 0;', 'exit:\n  parity_trace::Finish();\n  return 0;')
    if portable_random:
        shutil.copyfile(SUPPORT / "linux_random.h", source / "src/linux_random.h")
        for name, prefix in (("runner.cpp", ""), ("predictor.cpp", ""),
                             ("mixer/lstm-layer.h", "../"), ("models/indirect.h", "../")):
            path = source / "src" / name
            text = path.read_text()
            text = text.replace('srand(', 'linux_random::Seed(').replace('rand()', 'linux_random::Next()')
            path.write_text(f'#include "{prefix}linux_random.h"\n' + text)
