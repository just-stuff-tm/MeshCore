#!/usr/bin/env python3
"""Build matrix: every env upstream's own CI releases for each firmware type
(build.sh get-<type>-firmwares-to-build) plus the headless Heltec V3 envs, on the prepared
source (source.py), split into chunks.
Usage: matrix_stock.py '<types json>' [chunk]
Prints {"include":[{"id":..,"sha":..,"envs":"a b c"}]}, writes envs-all.json.
On merge conflicts writes conflicts.txt and exits 3."""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
types = json.loads(sys.argv[1])
chunk = int(sys.argv[2]) if len(sys.argv) > 2 else 6
by_sha, all_envs, conflicts = {}, [], {}
for t in types:
    d = f"src-{t['sha'][:12]}"
    if t["sha"] not in by_sha and not os.path.isdir(d):
        r = subprocess.run([sys.executable, os.path.join(HERE, "source.py"), d, t["sha"]], stdout=sys.stderr)  # stdout = matrix JSON only
        if r.returncode == 3:
            conflicts[t["sha"]] = open(d + ".conflicts").read().split(); continue
        if r.returncode != 0:
            sys.exit(f"preparing {t['tag']} failed")
    if t["sha"] in conflicts or not os.path.isdir(d):
        continue
    out = subprocess.run(["bash", "build.sh", f"get-{t['type']}-firmwares-to-build"], cwd=d, capture_output=True, text=True)
    envs = [e for e in out.stdout.split() if e]
    if not envs:
        sys.exit(f"no {t['type']} envs found at {t['sha']}: {out.stderr[-500:]}")
    if t["type"] == "repeater":  # headless Heltec V3 envs (all roles) ride along with the repeater set
        p = os.path.join(d, "variants", "heltec_v3_headless", "platformio.ini")
        if os.path.exists(p):
            envs += re.findall(r'(?m)^\[env:([^\]]+)\]', open(p).read())
    lst = by_sha.setdefault(t["sha"], [])
    for e in envs:
        if e not in lst:
            lst.append(e)
if conflicts:
    files = sorted({f for fs in conflicts.values() for f in fs})
    open("conflicts.txt", "w").write("\n".join(files) + "\n")
    sys.exit(3)
include = []
for sha, envs in by_sha.items():
    all_envs += envs
    for i in range(0, len(envs), chunk):
        include.append({"id": len(include) + 1, "sha": sha, "envs": " ".join(envs[i:i + chunk])})
json.dump(all_envs, open("envs-all.json", "w"))
print(f"{len(all_envs)} envs in {len(include)} jobs", file=sys.stderr)
print(json.dumps({"include": include}, separators=(",", ":")))
