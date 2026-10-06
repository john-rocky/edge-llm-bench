import mmap, sys, re, hashlib
for p in sys.argv[1:]:
    with open(p, 'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        # metadata sits near the start; scan the first 64 MB and the last 64 MB for a jinja block
        hits = []
        for lo, hi in ((0, min(len(mm), 64 << 20)), (max(0, len(mm) - (64 << 20)), len(mm))):
            buf = mm[lo:hi]
            for m in re.finditer(rb'\{%-? *(if|for|set) ', buf):
                hits.append(lo + m.start()); break
        name = p.rsplit('/', 1)[-1]
        if not hits:
            print(f"== {name}: no jinja block found in the first/last 64 MB"); continue
        start = hits[0]
        chunk = mm[start:start + 20000]
        end = max(chunk.rfind(b'%}'), chunk.rfind(b'}}'))
        # stop at the first non-text byte
        m = re.search(rb'[\x00-\x08\x0e-\x1f]', chunk)
        text = chunk[:m.start() if m else end + 2].decode('utf-8', 'replace')
        lines = text.split('\n')
        print(f"== {name}: template at byte {start}, {len(lines)} lines, sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]}")
        for i, l in enumerate(lines, 1):
            if 'content' in l and ('+' in l or 'is string' in l or 'is iterable' in l or 'is sequence' in l):
                print(f"   {i:3d}: {l.strip()[:200]}")
