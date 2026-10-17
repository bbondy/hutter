#!/usr/bin/env python3
"""Project the verified competitive order and test constrained link-guided moves."""
import argparse
import copy
import json
from pathlib import Path
import subprocess

from article_order import graph_order, link_graph, pages_from_bytes, restore_source, sha
from cmix_fixture_support import CAPABILITY, corpus_arguments
from make_samples import digest

NAMES = ('upstream', 'local', 'graph')


def local_order(baseline, edges, classes, ranks, span=4096, passes=4, blocks=None):
    """Swap adjacent normal fixture pages only for a strict forward-edge gain.

    Every moved page must stay within `span` FULL-corpus ranks of the original
    occupant of its destination slot. Other classes never move. Four passes
    are fixed before scores; this is a projected-fixture heuristic, not an
    assertion about omitted full-corpus edges or an optimum.
    """
    order = list(baseline)
    for _ in range(passes):
        changed = False
        for i in range(len(order) - 1):
            a, b = order[i:i+2]
            if classes[a] != 0 or classes[b] != 0 or (blocks is not None and blocks[a] != blocks[b]):
                continue
            if max(abs(ranks[b] - ranks[baseline[i]]), abs(ranks[a] - ranks[baseline[i+1]])) > span:
                continue
            if a in edges[b] and b not in edges[a]:
                order[i], order[i+1] = b, a
                changed = True
        if not changed:
            break
    return order


def prepare(args):
    old = json.loads(args.manifest.read_text())
    corpus_arguments(old)  # Refuse the rejected runtime-only protocol.
    index = args.index.resolve()
    validation = json.loads(args.validation.read_text())
    if (not validation['upstream_digest_matches'] or validation['reordered_md5'] != '28ca879dcfdafe7833b042f58cfee517'
            or digest(index) != validation['order_index_sha256']):
        raise ValueError('index is not the verified upstream order')
    rows = [list(map(int, line.split())) for line in index.read_text().splitlines()]
    if (len(rows) != 243425 or [r[0] for r in rows] != list(range(243425))
            or len({r[1] for r in rows}) != 243425):
        raise ValueError('incomplete or ambiguous full order index')
    rank_by_id = {pid: rank for rank, pid, _ in rows}
    class_by_id = {pid: kind for _, pid, kind in rows}
    # Keep normal regions separated by upstream calendar/special blocks.
    # This also prevents later Wikipedia pages (class 0) moving into the main
    # normal region across the census and image blocks.
    block_by_id, previous, block = {}, None, -1
    for _, pid, kind in rows:
        if kind != previous:
            block += 1
        block_by_id[pid] = block
        previous = kind
    with Path(old['source']).open('rb') as source:
        source.seek(old['source_offset'])
        raw = source.read(old['raw_bytes'])
    if sha(raw) != old['raw_sha256'] or restore_source(raw) != raw:
        raise ValueError('frozen original article bytes changed')
    pages = pages_from_bytes(raw)
    ranks = [rank_by_id[p['id']] for p in pages]
    classes = [class_by_id[p['id']] for p in pages]
    blocks = [block_by_id[p['id']] for p in pages]
    baseline = sorted(range(len(pages)), key=lambda i: ranks[i])
    prefix = [i for i in baseline if ranks[i] < 71148]
    if baseline[:len(prefix)] != prefix:
        raise ValueError('upstream front block is not contiguous')
    edges = link_graph(pages)
    local = local_order(baseline, edges, classes, ranks, args.span, args.passes, blocks=blocks)
    graph = list(baseline)
    for block in sorted(set(blocks)):
        slots = [i for i,u in enumerate(baseline) if classes[u] == 0 and blocks[u] == block]
        movable = [baseline[i] for i in slots]
        mapping = {u:i for i,u in enumerate(movable)}
        subgraph = [{mapping[v] for v in edges[u] if v in mapping} for u in movable]
        ordered, _ = graph_order(subgraph)
        for slot, i in zip(slots, ordered):
            graph[slot] = movable[i]
    orders = {'upstream': baseline, 'local': local, 'graph': graph}
    build = args.build.resolve()
    provenance = json.loads((build / 'build.json').read_text())
    helper = build / 'prepare-sample'
    if digest(helper) != provenance['sample_helper']['sha256']:
        raise ValueError('preparation helper changed')
    manifest = copy.deepcopy(old)
    manifest.update(version=4, kind='competitive-order-projection', variant_names=list(NAMES),
                    baseline_variant='upstream', baseline='Projection of exact upstream full-corpus order; surrounding pages/context omitted',
                    redirect_prefix_count=len(prefix), redirect_classifier='Full-order rank < 71148: redirects plus excluded ordinary pages',
                    phase_protocol=CAPABILITY, helper_sha256=digest(helper),
                    helper_arguments=['--native-corpus', str(len(pages)), str(len(prefix))],
                    preparation_script_sha256=digest(Path(__file__)),
                    local_parameters={'max_full_rank_displacement': args.span, 'passes': args.passes},
                    parent_manifest_sha256=digest(args.manifest),
                    full_order_index_sha256=digest(index), full_order_validation_sha256=digest(args.validation),
                    projected_pages=[{'id':p['id'], 'full_rank':ranks[i], 'class':classes[i], 'full_block':blocks[i]} for i,p in enumerate(pages)],
                    samples=[])
    flags = corpus_arguments(manifest, provenance)
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    metrics = {}
    for name, order in orders.items():
        if sorted(order) != list(range(len(pages))) or order[:len(prefix)] != prefix:
            raise ValueError('order lost pages or changed the front block')
        if any((classes[u] != 0 and order[i] != u) or blocks[order[i]] != blocks[u]
               for i, u in enumerate(baseline)):
            raise ValueError('order moved a special page')
        position = {u:i for i,u in enumerate(order)}
        forward = [(u,v) for u,targets in enumerate(edges) for v in targets if position[u]<position[v]]
        metrics[name] = {'forward_edges':len(forward), 'pages_with_prior_incoming_link':len({v for _,v in forward}),
                         'displaced_pages_vs_upstream':sum(u != baseline[i] for i,u in enumerate(order))}
        xml, ready, restored = [destination/f'{name}.{ext}' for ext in ('xml','ready','restored.xml')]
        ordered_raw = b''.join(pages[i]['raw'] for i in order)
        xml.write_bytes(ordered_raw)
        subprocess.run([str(helper), *flags, 'encode', str(xml), str(ready)], check=True)
        subprocess.run([str(helper), *flags, 'decode', str(ready), str(restored)], check=True)
        if restored.read_bytes() != ordered_raw or restore_source(restored.read_bytes()) != raw:
            raise ValueError('preparation or original-order restoration failed')
        manifest['samples'].append({'variant':name, 'path':str(ready), 'bytes':ready.stat().st_size,
                                   'sha256':digest(ready), 'role':old['role'], 'ordered_raw_sha256':sha(ordered_raw),
                                   'page_ids':[pages[i]['id'] for i in order],
                                   'preprocessing_roundtrip':True, 'source_restoration':True})
    manifest['graph']['variants'] = metrics
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'redirect_prefix_count':len(prefix), 'metrics':metrics}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('manifest', 'index', 'validation', 'build', 'output'):
        parser.add_argument('--'+option, required=True, type=Path)
    parser.add_argument('--span', type=int, default=4096)
    parser.add_argument('--passes', type=int, default=4)
    args = parser.parse_args()
    if args.span < 0 or args.passes < 1:
        parser.error('span must be nonnegative and passes positive')
    try:
        prepare(args)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
