"""Split an ORT prefill profile by op kind (ORT GenAI Galaxy S26 1K prefill
diagnosis, round r2b, 2026-10-07).

Input: the profile JSON that ORT run-level profiling writes (model_benchmark
--profile_prefill on the S26, mac_ladder.py --profile on the Mac): one "Node"
event per executed node, `name` = "<node>_kernel_time", `dur` in us,
`args.op_name`, `args.provider`, `args.input_type_shape`, and
`args.thread_scheduling_stats` (the intra-op pool: the calling thread plus one
entry per pool thread); "Session" events model_run / SequentialExecutor::Execute.
graph_nodes.json (graph_nodes.py) gives each MatMulNBits node's bits, K and N.

Kinds: MatMulNBits bits 4, MatMulNBits bits 8 in the layers, the bits-8
lm_head (logits for every prompt position), GroupQueryAttention,
SkipSimplifiedLayerNormalization, SimplifiedLayerNormalization, and the rest by
op type. For MatMulNBits, M = the product of the leading dims of the first
input, multiply-accumulates = M x K x N, and the rate is MACs / kernel time.

usage: python -I profile_summary.py <profile.json> <graph_nodes.json> [--label L] [--json out.json]
Prints a markdown summary; --json writes the same numbers.
"""
import argparse
import collections
import json
import math


def first_shape(args):
    shapes = args.get("input_type_shape") or []
    if not shapes:
        return None
    (dims,) = shapes[0].values()
    return dims


def kind_of(node, op, graph):
    entry = graph.get(node, {})
    if op == "MatMulNBits":
        bits = entry.get("bits")
        if node.startswith("/lm_head/"):
            return f"MatMulNBits bits {bits} lm_head"
        return f"MatMulNBits bits {bits} (layers)"
    return op


def summarize(profile_path, graph_path, label):
    with open(profile_path, encoding="utf-8") as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = events.get("traceEvents", [])
    with open(graph_path, encoding="utf-8") as f:
        graph = json.load(f)["nodes"]
    session = {e["name"]: e["dur"] for e in events if e.get("cat") == "Session"}
    kinds = collections.defaultdict(lambda: {"us": 0, "count": 0, "macs": 0})
    rows = []
    pool = None
    providers = collections.Counter()
    for e in events:
        if e.get("cat") != "Node" or not e.get("name", "").endswith("_kernel_time"):
            continue
        node = e["name"][: -len("_kernel_time")]
        args = e.get("args", {})
        op = args.get("op_name") or graph.get(node, {}).get("op_type", "?")
        providers[args.get("provider", "?")] += 1
        kind = kind_of(node, op, graph)
        k = kinds[kind]
        k["us"] += e["dur"]
        k["count"] += 1
        macs = 0
        if op == "MatMulNBits" and node in graph:
            dims = first_shape(args)
            if dims:
                m = math.prod(dims[:-1])
                macs = m * graph[node]["K"] * graph[node]["N"]
                k["macs"] += macs
        rows.append({"node": node, "op": op, "kind": kind, "us": e["dur"], "macs": macs,
                     "input0": first_shape(args)})
        tss = args.get("thread_scheduling_stats")
        if pool is None and tss:
            pool = {"pool": tss.get("main_thread", {}).get("thread_pool_name"),
                    "pool_threads_incl_caller": 1 + len(tss.get("sub_threads", {}))}
    total = sum(r["us"] for r in rows)
    out = {
        "label": label, "profile": profile_path, "node_events": len(rows),
        "node_kernel_ms": round(total / 1e3, 3),
        "model_run_ms": round(session.get("model_run", 0) / 1e3, 3),
        "providers": dict(providers), "intra_op_pool": pool,
        "prompt_tokens": None, "kinds": [], "top": [],
    }
    m_rows = [r for r in rows if r["op"] == "MatMulNBits" and r["input0"]]
    if m_rows:
        out["prompt_tokens"] = math.prod(m_rows[0]["input0"][:-1])
    for kind, k in sorted(kinds.items(), key=lambda kv: -kv[1]["us"]):
        item = {"kind": kind, "count": k["count"], "ms": round(k["us"] / 1e3, 3),
                "share": round(k["us"] / total, 4) if total else None}
        if k["macs"]:
            item["gmacs"] = round(k["macs"] / 1e9, 2)
            item["gmac_per_s"] = round(k["macs"] / k["us"] / 1e3, 1)
        out["kinds"].append(item)
    for r in sorted(rows, key=lambda r: -r["us"])[:10]:
        out["top"].append({"node": r["node"], "kind": r["kind"], "ms": round(r["us"] / 1e3, 3),
                           "share": round(r["us"] / total, 4) if total else None,
                           "input0": r["input0"]})
    return out


def markdown(s):
    lines = [f"### {s['label']}",
             f"profile {s['profile']}; {s['node_events']} node events, sum of node kernel times "
             f"{s['node_kernel_ms']:.1f} ms, model_run {s['model_run_ms']:.1f} ms; prompt tokens "
             f"(MatMulNBits M) {s['prompt_tokens']}; providers {s['providers']}; intra-op pool {s['intra_op_pool']}",
             "",
             "| kind | nodes | ms | share | GMAC | GMAC/s |",
             "|---|---|---|---|---|---|"]
    for k in s["kinds"]:
        lines.append(f"| {k['kind']} | {k['count']} | {k['ms']:.1f} | {k['share'] * 100:.1f} % | "
                     f"{k.get('gmacs', '')} | {k.get('gmac_per_s', '')} |")
    lines += ["", "| top node | kind | ms | share | input 0 |", "|---|---|---|---|---|"]
    for t in s["top"]:
        lines.append(f"| {t['node']} | {t['kind']} | {t['ms']:.1f} | {t['share'] * 100:.1f} % | {t['input0']} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profile")
    ap.add_argument("graph_nodes")
    ap.add_argument("--label", default="")
    ap.add_argument("--json")
    a = ap.parse_args()
    s = summarize(a.profile, a.graph_nodes, a.label or a.profile)
    print(markdown(s))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)


if __name__ == "__main__":
    main()
