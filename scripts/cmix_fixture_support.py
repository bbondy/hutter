"""Shared development-only phase configuration and read-only context reports."""
from pathlib import Path
import json
import re

from make_samples import digest

CAPABILITY = "corpus-frame-v2-context-v1-preparer-v2"
HEADER = Path(__file__).resolve().parents[1] / "engines/ports/cmix-neif-macos/overlay/src/native_corpus.h"


def provenance():
    return {"capability": CAPABILITY, "header_sha256": digest(HEADER),
            "instrumenter_sha256": digest(Path(__file__)),
            "preparer_source_sha256": digest(HEADER.parents[2] / "prepare_sample.cpp")}


def corpus_arguments(manifest, build=None):
    count = manifest.get("page_count")
    if type(count) is not int or not 1 <= count <= 243425:
        raise ValueError("invalid development article count")
    if "redirect_prefix_count" not in manifest:
        return ["--native-pages", str(count)]
    redirects = manifest["redirect_prefix_count"]
    if type(redirects) is not int or not 0 <= redirects <= count:
        raise ValueError("invalid development redirect prefix")
    expected = ["--native-corpus", str(count), str(redirects)]
    if manifest.get("helper_arguments") != expected:
        raise ValueError("fixture helper must use the same declared corpus phases as the coder")
    if build is not None and build.get("fixture_support", {}).get("capability") != CAPABILITY:
        raise ValueError("build lacks corrected corpus phases and context telemetry")
    return ["--native-corpus", str(count), str(redirects)]


def context_report(path):
    reports = {}
    for match in re.finditer(r'CMIX_CONTEXT (\{[^\n]+\})', path.read_text(errors="replace")):
        row = json.loads(match[1])
        kind = row.pop("kind")
        row.pop("side", None)  # Encoder/decoder labels differ, counters must match.
        if kind in reports:
            raise ValueError(f"duplicate {kind} context report")
        reports[kind] = row
    return reports


def validate_context(encode, decode, manifest):
    if set(encode) != {"z3", "prompt", "alias"} or encode != decode:
        raise ValueError("missing or unequal encoder/decoder context reports")
    # Upstream emits page-prefix prompts AFTER a page separator. The first
    # article has no preceding separator, so it receives no redirect prompt.
    expected_prompts = max(0, manifest["redirect_prefix_count"] - 1)
    if encode["prompt"]["redirect_prompt_pages"] != expected_prompts:
        raise ValueError("redirect prompt boundary differs from fixture")
    if encode["prompt"]["articles"] != manifest["page_count"]:
        raise ValueError("observed article count differs from fixture")


def instrument_fixture(source):
    def replace(name, old, new):
        path = source / "src" / name
        text = path.read_text()
        if text.count(old) != 1:
            raise ValueError(f"fixture patch anchor changed: {name}: {old[:70]}")
        path.write_text(text.replace(old, new))

    def include(name):
        path = source / "src" / name
        relative = "../" * (len(Path(name).parts) - 1)
        path.write_text(f'#include "{relative}native_corpus.h"\n' + path.read_text())

    for name in ("redirect_table.h", "tf1/tf1_prompt.h"):
        include(name)
        replace(name, "71148", "native_corpus::RedirectCount()")
    replace("runner.cpp", "  WriteHeaderVocfix(temp_bytes, dictionary != NULL, &data_out);",
            "  if (!native_corpus::WriteHeader(&data_out)) return false;\n"
            "  WriteHeaderVocfix(temp_bytes, dictionary != NULL, &data_out);")
    replace("runner.cpp", "  ReadHeaderVocfix(&data_in, output_bytes, &dictionary_used, &vocab);",
            "  if (!native_corpus::ReadHeader(&data_in)) return false;\n"
            "  ReadHeaderVocfix(&data_in, output_bytes, &dictionary_used, &vocab);")
    replace("tf1/tf1_engine.cpp", "void Tf1Engine::ReportChannels() const {",
            "void Tf1Engine::ReportChannels() const {\n"
            "  if (impl_->z3) impl_->z3->Report();\n"
            "  if (impl_->prompt) impl_->prompt->Report();")

    def report_body(kind, fields, extra=None):
        items = [(key, "st_." + field) for key, field in fields.items()]
        items += list((extra or {}).items())
        fmt = 'CMIX_CONTEXT {"kind":"' + kind + '"' + ''.join(',"' + key + '":%llu' for key, _ in items) + '}\n'
        return '  if (!native_corpus::Telemetry()) return;\n  std::fprintf(stderr, ' + json.dumps(fmt) + ',\n      ' + ', '.join(value for _, value in items) + ');\n'

    include("tf1/tf1_z3.cpp")
    replace("tf1/tf1_z3.cpp", "void CoderZ3::Report() const {\n}",
            "void CoderZ3::Report() const {\n" + report_body("z3", {
                key: key for key in ("articles", "usable_titles", "articles_with_mentions", "articles_with_prefix",
                                     "mentions_total", "prefix_tokens_total", "chunks_total", "anchors")
            }, {"fed_tokens": "fed_"}) + "}")
    replace("tf1/tf1_prompt.cpp", "void CoderPrompt::Report() const {\n}",
            "void CoderPrompt::Report() const {\n" + report_body("prompt", {
                "articles": "articles", "redirect_prompt_pages": "rd_seiten", "redirect_prompt_tokens": "rd_tokens",
                "redirect_pages": "redirect_pages", "meta_pages": "meta_seiten", "alias_tokens": "alias_tokens",
                "alias_articles": "alias_articles", "links": "links", "links_piped": "links_piped",
                "redirects": "redirects",
            }, {"fed_tokens": "fed_"}) + "}")
    include("alias_context.h")
    replace("alias_context.h", "    (void)side;", "    (void)side;\n" + report_body("alias", {
        key: key for key in ("articles", "titles", "blocks", "bytes", "links", "links_piped", "links_dropped",
                            "redirects", "from_redirect", "from_linktext")
    }))
