# 2026-10-23-dashboard-v1-m4max-ctxladder-mac — notes

One dashboard-job sitting on the Mac Studio M4 Max (`Mac16,9`), 2026-10-23 06:55–06:56 JST, cells
`matrices/ctx-ladder-q06-e2-ynnpack-mac.cells`: the anchor phase `2026-10-23-dashboard-v1-m4max-ctxladder-anchor-mac`
and the payload = the platform's session anchor row (SESSION.json: COMPLETED, admitted, anchor nominal, ratio 0.991 to
the reference). It ran inside the lane's own Mac measurement window (quiet_hold `ctxladder-r1-mac1`, from 06:54:17);
the job took no window of its own.

The context ladder that followed in the same window (the HEAD cpu_only CLI, the cells file's header) ran out of the
window at 07:18:18 JST after 36 of its 40 launches (the fourth launch of the 2,048 and 4,096 allocations missing). A
ladder is read within one sitting, so none of its launches is a record: they are not imported here, and their consoles
stay in the lane's notes. The ladder is the next sitting's, `2026-10-23-dashboard-v1-m4max-ctxladder-s2-mac`, whose
admission took this dir as its reference; the two sittings are committed together (the reference chain).
