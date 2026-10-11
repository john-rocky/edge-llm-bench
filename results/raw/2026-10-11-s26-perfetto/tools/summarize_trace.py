#!/usr/bin/env python3
"""Numbers out of one Perfetto trace of an LLM benchmark process (or app session) on the Galaxy S26, Android 16.

  <venv with the perfetto package>/bin/python summarize_trace.py <trace> --process <name substring> [--json out.json]

The window = the first to last scheduled slice of the named process (whole trace when no process is named).
Prints: CPU frequency per cpu over the window (time-weighted mean, max, share of the window at the cpu's top step
seen in the trace), GPU frequency the same way (kgsl `gpufreq` counter), the process's CPU time per thread and every
other process's CPU time in the window (top 10), battery current / power counters (1 s polls), the engine's own log
lines (tag `litert`, `native`, `tflite`) with their offset from the process start, and the thermal-service log lines.
This phone's kernel emitted no `thermal/thermal_temperature` or `power/cpu_frequency_limits` ftrace events into the
trace (checked 2026-10-11 on P1), so temperatures and clock caps come from the 1-second sampler beside each run.
"""
import argparse, json
from perfetto.trace_processor import TraceProcessor


def rows(tp, sql):
  out = []
  for r in tp.query(sql):
    out.append({k: getattr(r, k) for k in r.__dict__ if not k.startswith("_")})
  return out


def tw(tp, track_sql, t0, t1):
  """time-weighted stats of a counter track set: mean, max, share at max; track_sql yields (track_id, grp)."""
  return rows(tp, f"""
    with tr as ({track_sql}),
    c as (select tr.grp as grp, cv.ts as ts, cv.value as v, lead(cv.ts) over (partition by cv.track_id order by cv.ts) as nts
          from counter cv join tr on cv.track_id = tr.id),
    w as (select grp, v, max(ts, {t0}) as a, min(coalesce(nts, {t1}), {t1}) as b from c where coalesce(nts, {t1}) > {t0} and ts < {t1}),
    m as (select grp, max(v) as vmax from w group by grp)
    select w.grp as grp, sum(v * (b - a)) / sum(b - a) as mean, m.vmax as max,
           sum(case when v >= m.vmax then (b - a) else 0 end) * 1.0 / sum(b - a) as top_share, count(*) as n
    from w join m using(grp) group by w.grp order by w.grp""")


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("trace"); ap.add_argument("--process", default=""); ap.add_argument("--json", default="")
  a = ap.parse_args()
  tp = TraceProcessor(trace=a.trace)
  res = {"trace": a.trace, "process": a.process}
  b = rows(tp, "select start_ts, end_ts from trace_bounds")[0]
  t0, t1 = b["start_ts"], b["end_ts"]
  res["trace_s"] = (t1 - t0) / 1e9
  if a.process:
    pr = rows(tp, f"""
      select p.upid as upid, p.pid as pid, p.name as name, min(s.ts) as first_ts, max(s.ts + s.dur) as last_ts, sum(s.dur) / 1e9 as cpu_s
      from sched_slice s join thread t using(utid) join process p using(upid)
      where p.name like '%{a.process}%' group by p.upid order by cpu_s desc""")
    res["process_rows"] = pr
    if pr:
      t0, t1 = pr[0]["first_ts"], pr[0]["last_ts"]
      upid = pr[0]["upid"]
      res["threads"] = rows(tp, f"""
        select t.tid as tid, t.name as name, sum(s.dur) / 1e9 as cpu_s from sched_slice s join thread t using(utid)
        where t.upid = {upid} group by t.utid order by cpu_s desc limit 10""")
  res["window_s"] = (t1 - t0) / 1e9
  res["cpu_freq_khz"] = tw(tp, "select id, cpu as grp from cpu_counter_track where name = 'cpufreq'", t0, t1)
  res["gpu_freq_khz"] = tw(tp, "select id, 'gpu' as grp from gpu_counter_track where name = 'gpufreq'", t0, t1)
  res["cpu_time_by_process_s"] = rows(tp, f"""
    select p.pid as pid, p.name as name, sum(min(s.ts + s.dur, {t1}) - max(s.ts, {t0})) / 1e9 as cpu_s
    from sched_slice s join thread t using(utid) left join process p using(upid)
    where s.ts < {t1} and s.ts + s.dur > {t0} and s.utid != 0 group by p.upid order by cpu_s desc limit 10""")
  res["cpu_time_total_s"] = rows(tp, f"""
    select sum(min(s.ts + s.dur, {t1}) - max(s.ts, {t0})) / 1e9 as cpu_s from sched_slice s
    where s.ts < {t1} and s.ts + s.dur > {t0} and s.utid != 0""")[0]["cpu_s"]
  res["battery"] = rows(tp, f"""
    select t.name as name, count(*) as n, min(c.value) as min, max(c.value) as max, avg(c.value) as mean
    from counter c join counter_track t on c.track_id = t.id where t.name like 'batt.%' and c.ts between {t0} and {t1} group by t.name""")
  res["engine_log"] = [dict(r, t_rel_s=(r["ts"] - t0) / 1e9) for r in rows(tp, f"""
    select l.ts as ts, l.tag as tag, l.msg as msg from android_logs l
    where l.ts between {t0} - 2000000000 and {t1} + 2000000000 and l.tag in ('litert', 'native', 'tflite', 'AGBenchmarkVM')
      and (l.msg like '%max_tokens%' or l.msg like '%Prefill%' or l.msg like '%Decode%' or l.msg like '%Init%' or l.msg like '%cache%'
           or l.msg like '%RegisterAccelerator%' or l.msg like '%OpenCL%' or l.msg like '%Benchmark%' or l.msg like '%Done #%' or l.msg like '%tokens/s%')
    order by l.ts limit 120""")]
  res["thermal_log"] = [dict(r, t_rel_s=(r["ts"] - t0) / 1e9) for r in rows(tp, f"""
    select l.ts as ts, l.tag as tag, l.msg as msg from android_logs l
    where l.ts between {t0} - 2000000000 and {t1} + 2000000000 and (l.tag like '%thermal%') order by l.ts limit 60""")]
  out = json.dumps(res, indent=1, default=str)
  if a.json:
    open(a.json, "w").write(out)
  print(out)


if __name__ == "__main__":
  main()
