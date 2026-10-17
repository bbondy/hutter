#!/usr/bin/env python3
"""Prepare reversible, identical-content article-order experiments for native cmix.

Graph edges are exact-title wiki links, a proxy for available prior context.
They do not reproduce cmix's token matching, prompt budgets or prefix matches.
"""
import argparse
import hashlib
import heapq
import html
import json
from pathlib import Path
import re
import subprocess

from make_samples import digest
from cmix_fixture_support import CAPABILITY

PAGE = re.compile(rb"  <page>\n.*?  </page>\n", re.S)
LINK = re.compile(r"\[\[([^\[\]|#\n]+)")
VARIANTS = ("source", "graph", "random")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pages_from_bytes(data):
    pages = []
    for match in PAGE.finditer(data):
        raw = match.group()
        title = re.search(rb"<title>(.*?)</title>", raw)
        page_id = re.search(rb"<id>(\d+)</id>", raw)
        text = re.search(rb"<text\b[^>]*>(.*?)</text>", raw, re.S)
        empty_text = re.search(rb"<text\b[^>]*/>", raw)
        if not title or not page_id or (text is None and empty_text is None):
            raise ValueError("page lacks title, id or text")
        pages.append({"id": int(page_id[1]), "title": html.unescape(title[1].decode()),
                      "text": html.unescape(text[1].decode()) if text else "", "raw": raw})
    if not pages or b"".join(p["raw"] for p in pages) != data:
        raise ValueError("input must contain only complete, consecutive pages")
    if len({p["id"] for p in pages}) != len(pages):
        raise ValueError("duplicate page id cannot be restored unambiguously")
    if len({p["title"] for p in pages}) != len(pages):
        raise ValueError("duplicate title makes graph matching ambiguous")
    return pages


def restore_source(data):
    """Decoder needs only recovered page IDs, never the encoder's graph/order."""
    return b"".join(p["raw"] for p in sorted(pages_from_bytes(data), key=lambda p: p["id"]))


def link_graph(pages):
    titles = {p["title"]: i for i, p in enumerate(pages)}
    edges = [set() for _ in pages]
    for i, page in enumerate(pages):
        for target in LINK.findall(page["text"]):
            # No case folding, underscore normalization or redirect resolution.
            j = titles.get(target)
            if j is not None and j != i:
                edges[i].add(j)
    return edges


def strong_components(edges):
    """Iterative SCC decomposition, without the costly within-component ordering."""
    n = len(edges)
    reverse = [set() for _ in edges]
    for u, targets in enumerate(edges):
        for v in targets:
            reverse[v].add(u)
    seen, finish = set(), []
    for root in range(n):
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(sorted(edges[root])))]
        while stack:
            u, neighbors = stack[-1]
            v = next(neighbors, None)
            if v is None:
                finish.append(u)
                stack.pop()
            elif v not in seen:
                seen.add(v)
                stack.append((v, iter(sorted(edges[v]))))
    components, owner = [], {}
    for root in reversed(finish):
        if root in owner:
            continue
        cid, members, stack = len(components), [], [root]
        owner[root] = cid
        while stack:
            u = stack.pop()
            members.append(u)
            for v in sorted(reverse[u]):
                if v not in owner:
                    owner[v] = cid
                    stack.append(v)
        components.append(members)
    return components, owner, reverse


def graph_order(edges):
    """Stable SCC topological order; greedily break cycles inside each SCC.

    A source should precede a page it links to. Strongly connected components
    have unavoidable backward edges; choose max remaining outdegree-indegree
    inside each, breaking ties by source position. Isolated pages and available
    components retain source order. This is a heuristic, not an optimum claim.
    """
    components, owner, reverse = strong_components(edges)
    successors = [set() for _ in components]
    indegree = [0 for _ in components]
    for u, targets in enumerate(edges):
        for v in targets:
            a, b = owner[u], owner[v]
            if a != b and b not in successors[a]:
                successors[a].add(b)
                indegree[b] += 1
    frontier = [(min(c), i) for i, c in enumerate(components) if not indegree[i]]
    heapq.heapify(frontier)
    order = []
    while frontier:
        _, cid = heapq.heappop(frontier)
        remaining = set(components[cid])
        while remaining:
            u = min(remaining, key=lambda x: (-(len(edges[x] & remaining)
                                               - len(reverse[x] & remaining)), x))
            order.append(u)
            remaining.remove(u)
        for v in sorted(successors[cid]):
            indegree[v] -= 1
            if not indegree[v]:
                heapq.heappush(frontier, (min(components[v]), v))
    return order, sorted((len(c) for c in components), reverse=True)


# Match upstream article_reorder.h on RAW XML, including its exact casing and
# lack of a word boundary. Do not broaden this classifier silently.
REDIRECT_PREFIXES = tuple(b'      <text xml:space="preserve">' + prefix
                          for prefix in (b"#REDIRECT", b"#redirect", b"#Redirect", b"#REdirect", b"{{softredirect"))


def is_redirect(page):
    return any(line.startswith(REDIRECT_PREFIXES) for line in page["raw"].splitlines())


def orders_for(pages, seed, fixed_redirects=False):
    edges = link_graph(pages)
    graph, components = graph_order(edges)
    # Hash sorting specifies a reproducible control across Python versions.
    random = sorted(range(len(pages)),
                    key=lambda i: (sha(f"{seed}:{pages[i]['id']}".encode()), i))
    orders = {"source": list(range(len(pages))), "graph": graph, "random": random}
    if fixed_redirects:
        prefix = [i for i, page in enumerate(pages) if is_redirect(page)]
        ordinary = [i for i, page in enumerate(pages) if not is_redirect(page)]
        # Graph ordering is computed only on the movable ordinary subgraph.
        # The prefix's placement is fixed, so its edges are not objectives.
        remap = {old: new for new, old in enumerate(ordinary)}
        subgraph = [{remap[v] for v in edges[u] if v in remap} for u in ordinary]
        ordered, _ = graph_order(subgraph)
        orders = {"source": prefix + ordinary,
                  "graph": prefix + [ordinary[i] for i in ordered],
                  "random": prefix + [i for i in random if i in remap]}
    metrics = {}
    for name, order in orders.items():
        rank = {u: i for i, u in enumerate(order)}
        forward = [(u, v) for u, targets in enumerate(edges) for v in targets if rank[u] < rank[v]]
        metrics[name] = {"forward_edges": len(forward),
                         "pages_with_prior_incoming_link": len({v for _, v in forward}),
                         "displaced_pages": sum(i != u for i, u in enumerate(order))}
    return orders, {"exact_title_edges": sum(map(len, edges)),
                    "linked_pages": len({v for u, targets in enumerate(edges) for v in ({u} | targets)
                                         if targets}),
                    "scc_sizes": components, "variants": metrics}


def prepare(args):
    source, build, destination = args.enwik8.resolve(), args.build.resolve(), args.output.resolve()
    if source.stat().st_size != 100_000_000 or digest(source, "sha1") != "57b8363b814821dc9d47aa4d41f58733519076b2":
        raise ValueError("requires checksum-verified official enwik8")
    provenance = json.loads((build / "build.json").read_text())
    helper = build / "prepare-sample"
    if digest(helper) != provenance["sample_helper"]["sha256"]:
        raise ValueError("preprocessor differs from its build record")
    data = source.read_bytes()
    start = data.find(b"  <page>\n", args.start_offset)
    end = data.find(b"  </page>\n", start + args.target_bytes)
    if start < 0 or end < 0:
        raise ValueError("requested range does not fit complete pages")
    end += len(b"  </page>\n")
    raw = data[start:end]
    pages = pages_from_bytes(raw)
    if restore_source(raw) != raw:
        raise ValueError("source must have strictly increasing page IDs for zero-permutation restoration")
    fixed = args.phase_mode == "corrected"
    orders, metrics = orders_for(pages, args.seed, fixed_redirects=fixed)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {
        "version": 3 if fixed else 1, "kind": "article-order-fixture", "role": args.role,
        "source": str(source), "source_sha256": sha(data), "source_bytes": len(data),
        "source_requested_offset": args.start_offset, "source_offset": start, "source_end": end,
        "raw_bytes": len(raw), "raw_sha256": sha(raw), "page_count": len(pages),
        "page_set_sha256": sha("\n".join(sorted(sha(p["raw"]) for p in pages)).encode()),
        "pages": [{"id": p["id"], "sha256": sha(p["raw"])} for p in pages],
        "helper_sha256": digest(helper), "upstream_commit": provenance["upstream_commit"],
        "preparation_script_sha256": digest(Path(__file__)), "seed": args.seed,
        "preprocessing": "phda9 per ordered fixture; no full-corpus reorder or census/comment-index transforms",
        "baseline": "source page-ID order, NOT upstream embedding/residual order",
        "restoration": "sort recovered raw pages by unique ascending page ID",
        "order_side_information_bytes": 0,
        "size_scope": "Payload plus explicit order side data only. Decoder/encoder code and assets must be packaged and charged for a prize score.",
        "graph_scope": "Exact-title unique wiki-link pairs; XML unescaped; fragments/pipes removed; no case/underscore normalization. Proxy, not actual cmix prompt telemetry.",
        "graph": metrics, "samples": [],
    }
    if fixed:
        manifest.update(redirect_prefix_count=sum(is_redirect(p) for p in pages),
                        redirect_classifier="upstream article_reorder.h exact raw line prefixes",
                        phase_protocol=CAPABILITY,
                        helper_arguments=["--native-corpus", str(len(pages)), str(sum(is_redirect(p) for p in pages))],
                        development_header_bytes=16,
                        baseline="fixed redirect prefix, then ordinary pages in source page-ID order; NOT upstream embedding/residual order")
    for name, order in orders.items():
        ordered = b"".join(pages[i]["raw"] for i in order)
        xml, ready, restored = [destination / f"{name}.{ext}" for ext in ("xml", "ready", "restored.xml")]
        xml.write_bytes(ordered)
        subprocess.run([str(helper), *manifest.get("helper_arguments", []), "encode", str(xml), str(ready)], check=True)
        subprocess.run([str(helper), *manifest.get("helper_arguments", []), "decode", str(ready), str(restored)], check=True)
        if restored.read_bytes() != ordered or restore_source(restored.read_bytes()) != raw:
            raise ValueError(f"{name} preprocessing and source restoration failed")
        manifest["samples"].append({"variant": name, "path": str(ready), "bytes": ready.stat().st_size,
                                    "sha256": digest(ready), "role": args.role,
                                    "ordered_raw_sha256": sha(ordered),
                                    "page_ids": [pages[i]["id"] for i in order],
                                    "preprocessing_roundtrip": True, "source_restoration": True})
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"bytes": len(raw), "pages": len(pages), "graph": metrics}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--enwik8", type=Path, required=True)
    prep.add_argument("--build", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--target-bytes", type=int, default=1_000_000)
    prep.add_argument("--start-offset", type=int, default=0)
    prep.add_argument("--phase-mode", choices=("corrected", "legacy"), default="corrected")
    prep.add_argument("--seed", type=int, default=20261017)
    prep.add_argument("--role", choices=("screen", "holdout"), default="screen")
    args = parser.parse_args()
    if not 0 <= args.start_offset < 100_000_000 or not 0 < args.target_bytes < 99_000_000:
        parser.error("offset and size must fit enwik8")
    try:
        prepare(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
