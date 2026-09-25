import json, sys, collections
for path in sys.argv[1:]:
    rows=[json.loads(l) for l in open(path)]
    W=sum(r["ref_words"] for r in rows)
    def wer(g):
        w=sum(r["ref_words"] for r in g); return 100*sum(r["errors"] for r in g)/w if w else float("nan"), len(g), w
    b=collections.defaultdict(list)
    for r in rows:
        d=r["audio_seconds"]; k="<5s (1 window)" if d<5 else "5-10s" if d<10 else "10-20s" if d<20 else ">=20s"
        b[k].append(r)
    loops=[r for r in rows if r["I"]>=20]; empty=[r for r in rows if not r["hyp"].strip()]
    print(f"== {path.split('/')[-1]}: n={len(rows)} W={W} WER={100*sum(r['errors'] for r in rows)/W:.2f}%  S/D/I={sum(r['S'] for r in rows)}/{sum(r['D'] for r in rows)}/{sum(r['I'] for r in rows)}")
    for k in ["<5s (1 window)","5-10s","10-20s",">=20s"]:
        w,n,ww=wer(b[k]); print(f"   {k:16s} n={n:5d} WER={w:6.2f}%  (ref words {ww})")
    print(f"   insertion runs (I>=20): {len(loops)} utts, {sum(r['I'] for r in loops)} insertions; empty hyps: {len(empty)} ({sum(r['ref_words'] for r in empty)} words); utts with WER>50%: {sum(1 for r in rows if r['wer']>0.5)}")
    noloop=[r for r in rows if r["I"]<20 and r["hyp"].strip()]
    w,n,ww=wer(noloop); print(f"   excluding runs and empties: n={n} WER={w:.2f}%")
