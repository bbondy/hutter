"""Refresh the frozen transformer's mixer row after the final injected alias byte."""
import hashlib
from pathlib import Path

from competitive import ENGINE
from make_samples import digest

SOURCE = "src/predictor.cpp"
VARIANT = "refresh"
BEFORE = """void Predictor::ObserveTfOnlyByte(unsigned int byte) {
  if (tf1_engine_) tf1_engine_->Step(byte_model_->BytePredict(), byte);
}"""
AFTER = """void Predictor::ObserveTfOnlyByte(unsigned int byte) {
  if (!tf1_engine_) return;
  const float* row = tf1_engine_->Step(byte_model_->BytePredict(), byte);
  // Step consumes the alias counter; only its final row predicts a real byte.
  if (row && transformer::Active() && !alias_prompt::Laeuft()
      && !tf1_engine_->GateMasked() && !timestamp_skip::Laeuft()) {
    tf1_slot_->SetProbs(row);
    tf1_slot_output = tf1_slot_->Predict()[0];
  }
}"""


def rewrite(text, variant=VARIANT):
    if variant != VARIANT:
        raise ValueError("unknown alias variant")
    if text.count(BEFORE) != 1:
        raise ValueError("alias patch anchor changed")
    return text.replace(BEFORE, AFTER)


def apply(source, variant):
    if source.resolve().is_relative_to(ENGINE.resolve()):
        raise ValueError("alias experiments must not modify pinned upstream")
    path = source / SOURCE
    before = digest(path)
    changed = rewrite(path.read_text(), variant)
    path.write_text(changed)
    return {"name": variant, "source_file": SOURCE, "before_sha256": before,
            "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
            "recipe_sha256": digest(Path(__file__)),
            "scope": "Refresh only the transformer slot and cached first-bit probability after the final injected alias row; preserve model states, prior, gate and all other predictors."}
