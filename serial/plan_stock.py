#!/usr/bin/env python3
"""Find the newest stock MeshCore release (tags repeater-/room-server-/companion-vX.Y.Z)
plus the EasySkyMesh power-saving source of its latest release, and decide whether
"vX.Y.Z-powersaving" (port), "vX.Y.Z-psNN-serial" (EasySkyMesh release source)
or "vX.Y.Z-serial" (no power saving) needs building. Writes outputs to $GITHUB_OUTPUT."""
import hashlib, json, os, re, sys, urllib.request, urllib.error

API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "")
REPO = os.environ["GITHUB_REPOSITORY"]
IN_VER = os.environ.get("IN_VERSION", "").strip().lstrip("v")
FORCE = os.environ.get("IN_FORCE", "false").lower() == "true"
PS_MODE = (os.environ.get("IN_PS", "") or "port").strip()   # port | easyskymesh-latest | off
USE_ESM = PS_MODE != "off"
PORT_BRANCH = os.environ.get("PS_PORT_BRANCH", "powersaving-port")      # our port of EasySkyMesh power saving
ESM_REF = os.environ.get("IN_ESM_REF", "").strip()
ESM_RELEASES = os.environ.get("ESM_RELEASES", "IoTThinks/EasySkyMesh")   # binaries + release notes
ESM_SOURCE = os.environ.get("ESM_SOURCE", "IoTThinks/MeshCore")         # source branches PowerSaving-vNN
HERE = os.path.dirname(os.path.abspath(__file__))
TYPES = ("repeater", "room-server", "companion")

def api(path, ok404=False):
    req = urllib.request.Request(API + path, headers={"Accept": "application/vnd.github+json", "User-Agent": "serial-build", **({"Authorization": "Bearer " + TOKEN} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if ok404 and e.code == 404:
            return None
        sys.exit(f"GitHub API {path}: HTTP {e.code} {e.read()[:300]!r}")

me = api(f"/repos/{REPO}")
upstream = (me.get("parent") or {}).get("full_name") or "meshcore-dev/MeshCore"
rels = api(f"/repos/{upstream}/releases?per_page=60")
found = {}
for r in rels:
    if r.get("draft") or r.get("prerelease"):
        continue
    m = re.match(r"^(repeater|room-server|companion)-v(\d+)\.(\d+)\.(\d+)$", r["tag_name"])
    if m:
        found.setdefault(tuple(map(int, m.group(2, 3, 4))), {})[m.group(1)] = r
if not found:
    sys.exit(f"no stock releases found in {upstream}")
ver = tuple(map(int, IN_VER.split("."))) if IN_VER else max(found)
if ver not in found:
    sys.exit(f"v{IN_VER} not found in {upstream} releases")
version = "v%d.%d.%d" % ver
types = []
for t in TYPES:
    r = found[ver].get(t)
    if r:
        sha = api(f"/repos/{upstream}/commits/{r['tag_name']}")["sha"]
        types.append({"type": t, "tag": r["tag_name"], "sha": sha, "url": r["html_url"]})

h = hashlib.sha256()
for root, _, files in sorted(os.walk(HERE)):
    for f in sorted(files):
        if f.endswith((".py", ".h", ".cpp")):
            h.update(open(os.path.join(root, f), "rb").read())
patch_id = h.hexdigest()[:12]

# EasySkyMesh power saving: source branch of its latest release (PowerSaving17.1 -> PowerSaving-v17),
# or the esm_ref input (branch, tag or commit in ESM_SOURCE).
esm = {}
if USE_ESM and PS_MODE == "port":
    ref = ESM_REF or PORT_BRANCH
    c = api(f"/repos/{REPO}/commits/{ref}", ok404=True)
    if not c:
        sys.exit(f"power-saving port {REPO}@{ref} not found")
    esm = {"repo": REPO, "ref": ref, "sha": c["sha"], "release": "", "release_url": "", "short": "powersaving"}
elif USE_ESM:
    ref, rel = ESM_REF, None
    if not ref:
        rel = next((r for r in api(f"/repos/{ESM_RELEASES}/releases?per_page=20") if not r.get("draft") and not r.get("prerelease")), None)
        if not rel:
            sys.exit(f"no EasySkyMesh release found in {ESM_RELEASES}")
        m = re.search(r"(\d+)", rel["tag_name"])
        if not m:
            sys.exit(f"cannot tell the source branch of EasySkyMesh release {rel['tag_name']}; set the esm_ref input")
        ref = f"PowerSaving-v{m.group(1)}"
    c = api(f"/repos/{ESM_SOURCE}/commits/{ref}", ok404=True)
    if not c:
        sys.exit(f"EasySkyMesh source {ESM_SOURCE}@{ref} not found; set the esm_ref input")
    mm = re.search(r"(\d+)", ref)
    esm = {"repo": ESM_SOURCE, "ref": ref, "sha": c["sha"], "release": rel["tag_name"] if rel else "",
           "release_url": rel["html_url"] if rel else "", "short": f"ps{mm.group(1)}" if mm else "ps"}

if PS_MODE == "port":
    tag = f"{version}-powersaving"        # serial.ondemand + headless are features of this build
elif esm:
    tag = f"{version}-{esm['short']}-serial"
else:
    tag = f"{version}-serial"
mine = api(f"/repos/{REPO}/releases/tags/{tag}", ok404=True)
sig = "source-commits: " + ",".join(f"{t['type']}={t['sha']}" for t in types) + (f" · esm={esm['repo']}@{esm['sha']}" if esm else " · esm=none") + f" · patch-id: {patch_id}"
build = FORCE or not (mine and sig in (mine.get("body") or ""))

res = dict(build=str(build).lower(), upstream=upstream, version=version, tag=tag,
           types=json.dumps(types, separators=(",", ":")), sig=sig, patch_id=patch_id,
           esm_repo=esm.get("repo", ""), esm_ref=esm.get("ref", ""), esm_sha=esm.get("sha", ""),
           esm_release=esm.get("release", ""), esm_release_url=esm.get("release_url", ""),
           fwver=tag)
with open(os.environ.get("GITHUB_OUTPUT", "/dev/stdout"), "a") as f:
    for k, v in res.items():
        f.write(f"{k}={v}\n")
for k, v in res.items():
    print(f"{k}={v}")
if not build:
    print(f"{tag} already built from the same source and patch; nothing to do.")
