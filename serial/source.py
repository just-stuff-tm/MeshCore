#!/usr/bin/env python3
"""Prepare a source tree: stock MeshCore at <base_sha>, merged with EasySkyMesh's power-saving
source (if ESM_SHA is set), then serial.ondemand + headless envs on top (apply-serial.py).
Usage: source.py <dir> <base_sha>
Env: UP (stock owner/repo), ESM_REPO (owner/repo of EasySkyMesh source), ESM_SHA,
     ESM_MODE = fail (default: stop on conflicts) | prefer (resolve conflicts with EasySkyMesh's side).
Exit 3 on merge conflicts; the conflicting files are written to <dir>.conflicts.
The merge commit is deterministic (fixed identity and date), so every job gets the same commit hash."""
import os, subprocess, sys
d, base = sys.argv[1], sys.argv[2]
up = os.environ["UP"]; esm_repo = os.environ.get("ESM_REPO", ""); esm = os.environ.get("ESM_SHA", "")
mode = os.environ.get("ESM_MODE", "fail")
HERE = os.path.dirname(os.path.abspath(__file__))

def git(*a, check=True, **kw):
    return subprocess.run(["git", "-C", d, *a], check=check, text=True, capture_output=True, **kw)

if not os.path.isdir(os.path.join(d, ".git")):
    subprocess.run(["git", "init", "-q", d], check=True)
    git("fetch", "-q", "--filter=blob:none", f"https://github.com/{up}", base)
    git("checkout", "-q", "FETCH_HEAD")
    if esm:
        git("fetch", "-q", "--filter=blob:none", f"https://github.com/{esm_repo}", esm)
        date = git("log", "-1", "--format=%cI", esm).stdout.strip()
        env = dict(os.environ, GIT_AUTHOR_NAME="serial-build", GIT_AUTHOR_EMAIL="serial-build@users.noreply.github.com",
                   GIT_COMMITTER_NAME="serial-build", GIT_COMMITTER_EMAIL="serial-build@users.noreply.github.com",
                   GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        msg = f"Merge EasySkyMesh {esm_repo}@{esm[:12]} into stock {base[:12]}"
        args = ["merge", "--no-ff", "--no-edit", "-m", msg] + (["-X", "theirs"] if mode == "prefer" else []) + [esm]
        r = git(*args, check=False, env=env)
        if r.returncode != 0:
            files = git("diff", "--name-only", "--diff-filter=U", check=False).stdout.split()
            open(d.rstrip("/") + ".conflicts", "w").write("\n".join(files) + "\n")
            print(f"MERGE CONFLICT ({len(files)} files) merging {esm_repo}@{esm[:12]} into {up}@{base[:12]}:", file=sys.stderr)
            print("\n".join("  " + f for f in files) or r.stderr[-1000:], file=sys.stderr)
            sys.exit(3)
        print(f"merged {esm_repo}@{esm[:12]} into {base[:12]} -> {git('rev-parse', '--short', 'HEAD').stdout.strip()}")
subprocess.run([sys.executable, os.path.join(HERE, "apply-serial.py"), d], check=True)
