#!/bin/zsh
# Medians per arm (D / H / J) of the counted runs in runs.tsv (w00 is not counted), with each arm's lowest and highest,
# and D / H, D / J and J / H for cold decode, warm decode, warm prefill and cold prefill. usage: med.sh logs/runs.tsv
f=${1:?runs.tsv}
LC_ALL=C tr -d '\r' < "$f" | awk -F'\t' '
NR == 1 { next }
$1 == "w00" { next }
$15 != "True" { bad[$2]++; next }
{ n[$2]++; cd[$2, n[$2]] = $11; cp[$2, n[$2]] = $12; wd[$2, n[$2]] = $13; wp[$2, n[$2]] = $14 }
function med(arr, a, k,   i, j, t, v, m) {
  m = n[a]; if (m == 0) return "na"
  for (i = 1; i <= m; i++) v[i] = arr[a, i] + 0
  for (i = 1; i <= m; i++) for (j = i + 1; j <= m; j++) if (v[j] < v[i]) { t = v[i]; v[i] = v[j]; v[j] = t }
  if (m % 2) return v[(m + 1) / 2]
  return (v[m / 2] + v[m / 2 + 1]) / 2
}
function rng(arr, a,   i, lo, hi, x) {
  lo = ""; hi = ""
  for (i = 1; i <= n[a]; i++) { x = arr[a, i] + 0; if (lo == "" || x < lo) lo = x; if (hi == "" || x > hi) hi = x }
  return lo "-" hi
}
END {
  split("D H J", arms, " ")
  for (q = 1; q <= 3; q++) {
    a = arms[q]
    printf "ARM %s n %d (not usable %d) | cold decode %s [%s] | warm decode %s [%s] | warm prefill %s [%s] | cold prefill %s [%s]\n", a, n[a], bad[a] + 0, med(cd, a), rng(cd, a), med(wd, a), rng(wd, a), med(wp, a), rng(wp, a), med(cp, a), rng(cp, a)
    M["cd", a] = med(cd, a); M["wd", a] = med(wd, a); M["wp", a] = med(wp, a); M["cp", a] = med(cp, a)
  }
  split("cd wd wp cp", ks, " "); split("cold-decode warm-decode warm-prefill cold-prefill", kn, " ")
  for (q = 1; q <= 4; q++) {
    k = ks[q]
    if (M[k, "H"] > 0 && M[k, "J"] > 0 && M[k, "D"] > 0)
      printf "RATIO %s D/H %.3f D/J %.3f J/H %.3f\n", kn[q], M[k, "D"] / M[k, "H"], M[k, "D"] / M[k, "J"], M[k, "J"] / M[k, "H"]
  }
}'
