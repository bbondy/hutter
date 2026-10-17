#!/usr/bin/env python3
"""Audit graph density and cycle sizes without running the expensive order heuristic."""
import argparse
from collections import Counter
import json
from pathlib import Path

from article_order import link_graph, pages_from_bytes, sha, strong_components
from make_samples import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--enwik8", action="store_true", help="verify official corpus and take all complete pages")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = args.input.read_bytes()
        start, end = 0, len(data)
        if args.enwik8:
            if len(data) != 100_000_000 or digest(args.input, "sha1") != "57b8363b814821dc9d47aa4d41f58733519076b2":
                raise ValueError("not official enwik8")
            start = data.find(b"  <page>\n")
            end = data.rfind(b"  </page>\n") + len(b"  </page>\n")
        pages = pages_from_bytes(data[start:end])
        edges = link_graph(pages)
        components, _, _ = strong_components(edges)
        count = sum(map(len, edges))
        reciprocal = sum(u < v and u in edges[v] for u, targets in enumerate(edges) for v in targets)
        report = {
            "version": 1, "kind": "article-graph-audit", "input_sha256": sha(data),
            "input_bytes": len(data), "source_offset": start, "source_end": end,
            "raw_sha256": sha(data[start:end]), "pages": len(pages), "exact_title_edges": count,
            "reciprocal_pairs": reciprocal, "forward_edge_upper_bound": count - reciprocal,
            "upper_bound_note": "Each reciprocal pair forces at least one backward edge; other cycles may tighten the bound.",
            "source_forward_edges": sum(u < v for u, targets in enumerate(edges) for v in targets),
            "largest_scc": max(map(len, components)),
            "scc_size_histogram": dict(sorted(Counter(map(len, components)).items(), reverse=True)),
            "script_sha256": digest(Path(__file__)),
            "graph_code_sha256": digest(Path(__file__).with_name("article_order.py")),
            "scope": "Exact-title graph proxy, not cmix context telemetry or a compression benchmark",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as out:
            out.write(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
