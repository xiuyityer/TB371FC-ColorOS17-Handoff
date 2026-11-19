#!/usr/bin/env python3
"""Summarize the slow SystemUI frames and scheduling waits in an atrace."""
from collections import defaultdict
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
systemui = int(sys.argv[2])
line_re = re.compile(r"-(\d+)\s+\(\s*(\d+|-----)\)\s+\[\d+\]\s+\S+\s+([\d.]+): (\w+): (.*)")
switch_re = re.compile(r"prev_pid=(\d+).*?prev_state=(\S+) ==> .*?next_pid=(\d+)")
wake_re = re.compile(r"\bpid=(\d+)")
opened = defaultdict(list)
waited = {}
waits = defaultdict(list)
running = {}
cpu = defaultdict(list)
children = defaultdict(list)
slices = defaultdict(list)
thread_name = {}
with path.open() as stream:
    for row in stream:
        match = line_re.search(row)
        if not match:
            continue
        tid, pid, seconds, event, detail = match.groups()
        tid, t = int(tid), float(seconds)
        if pid == str(systemui):
            thread_name[tid] = row[:match.start()].strip()
        if event == "sched_wakeup":
            x = int(wake_re.search(detail)[1])
            waited.setdefault(x, t)
        if event == "sched_switch":
            s = switch_re.search(detail)
            if not s:
                continue
            out, state, incoming = s.groups()
            out, incoming = int(out), int(incoming)
            start = running.pop(out, None)
            if start is not None:
                cpu[out].append((start, t))
            if state.startswith("R"):
                waited[out] = t
            start = waited.pop(incoming, None)
            if start is not None:
                waits[incoming].append((start, t))
            running[incoming] = t
        if event != "tracing_mark_write" or pid != str(systemui):
            continue
        if detail.startswith(f"B|{systemui}|"):
            opened[tid].append((t, detail.split("|", 2)[2]))
        elif (detail == "E" or detail.startswith("E|")) and opened[tid]:
            start, name = opened[tid].pop()
            slices[tid].append((start, t, name))
            if opened[tid]:
                children[(tid, opened[tid][-1][0])].append((start, t, name))


def coverage(intervals, start, end):
    return 1000 * sum(max(0, min(b, end) - max(a, start)) for a, b in intervals
                      if a < end and b > start)


for tid in sorted(slices):
    pool = [(a, b, n) for a, b, n in slices[tid]
            if n.startswith(("Choreographer#doFrame", "DrawFrame", "syncAndDrawFrame"))]
    if not pool:
        continue
    print(f"thread {tid} {thread_name.get(tid, '')}, {len(pool)} sampled frame slices")
    for a, b, name in sorted(pool, key=lambda row: row[1] - row[0], reverse=True)[:9]:
        print(f"  {a:.6f} {1000*(b-a):6.2f} ms cpu={coverage(cpu[tid],a,b):5.2f} "
              f"runnable_wait={coverage(waits[tid],a,b):5.2f} {name}")
        for c, d, n in sorted(children[tid, a], key=lambda row: row[1] - row[0], reverse=True)[:3]:
            print(f"      {1000*(d-c):5.2f} ms {n}")

print("Largest SystemUI main-thread slices")
for a, b, name in sorted(slices[systemui], key=lambda row: row[1] - row[0], reverse=True)[:30]:
    print(f"{a:.6f} {1000*(b-a):6.2f} ms {name}")
