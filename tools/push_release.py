# -*- coding: utf-8 -*-
"""
把 public_release/ 推送到公开仓库（无需本地 git）。

空仓库限制：Git Data API 在 "Git Repository is empty" 时返回 409，
必须先用 contents API 建一个初始文件来初始化默认分支。
之后再用 Git Data API 一次性提交其余文件。

token 由 gh 自己保管，本脚本不接触凭证。
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

OWNER = "ttwyce"
REPO = "so-qq-replay"
BRANCH = "master"
SRC = "public_release"
API = f"repos/{OWNER}/{REPO}"


import time


def gh(method: str, path: str, data=None, retries: int = 3) -> dict:
    cmd = ["gh", "api", "--method", method, path]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "--input", "-"]
    last = ""
    for attempt in range(1, retries + 1):
        p = subprocess.run(
            cmd,
            input=(json.dumps(data, ensure_ascii=False).encode("utf-8")
                   if data is not None else None),
            capture_output=True, timeout=90)
        if p.returncode == 0:
            txt = p.stdout.decode("utf-8", "replace").strip()
            return json.loads(txt) if txt else {}
        last = p.stderr.decode("utf-8", "replace")[:400]
        if attempt < retries:
            print("retry", attempt, method, path, "->", last[:80], file=sys.stderr)
            time.sleep(2 * attempt)
    raise RuntimeError(method + " " + path + " -> " + last)


def ref_head():
    p = subprocess.run(["gh", "api", f"{API}/git/ref/heads/{BRANCH}"],
                       capture_output=True, timeout=30)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout.decode())["object"]["sha"]


def main() -> int:
    # 递归收集所有文件（支持 tools/ 等子目录）
    names = []
    for dp, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", ".git", ".venv")]
        for fn in sorted(filenames):
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, SRC).replace(os.sep, "/")
            names.append(rel)
    names.sort()
    print("files:", len(names), file=sys.stderr)

    base_sha = ref_head()

    # 空仓库：用 contents API 提交 README 初始化分支
    if not base_sha:
        readme = open(os.path.join(SRC, "README.md"), "rb").read()
        r = gh("PUT", f"{API}/contents/README.md", {
            "message": "docs: add README",
            "content": base64.b64encode(readme).decode(),
            "branch": BRANCH,
        })
        print("initial commit", (r.get("commit") or {}).get("sha", "")[:10],
              file=sys.stderr)
        base_sha = ref_head()
        if not base_sha:
            raise RuntimeError("branch still missing after initial commit")

    commit0 = gh("GET", f"{API}/git/commits/{base_sha}")
    base_tree = commit0["tree"]["sha"]

    # 其余文件建 blob（README 已存在，跳过或覆盖都行；这里全部重建成一个新 tree）
    entries = []
    for name in names:
        raw = open(os.path.join(SRC, name), "rb").read()
        blob = gh("POST", f"{API}/git/blobs", {
            "content": base64.b64encode(raw).decode(),
            "encoding": "base64",
        })
        entries.append({"path": name, "mode": "100644", "type": "blob",
                        "sha": blob["sha"]})
        print("blob", name, len(raw), blob["sha"][:10], file=sys.stderr)

    tree = gh("POST", f"{API}/git/trees",
              {"base_tree": base_tree, "tree": entries})
    print("tree", tree["sha"][:10], file=sys.stderr)

    commit = gh("POST", f"{API}/git/commits", {
        "message": "feat: pure-Python browser-free protocol replay (redacted)",
        "tree": tree["sha"],
        "parents": [base_sha],
    })
    print("commit", commit["sha"][:10], file=sys.stderr)

    gh("PATCH", f"{API}/git/refs/heads/{BRANCH}",
       {"sha": commit["sha"], "force": False})

    print(json.dumps({
        "repo": f"{OWNER}/{REPO}", "branch": BRANCH,
        "files": len(names), "commit": commit["sha"],
        "html_url": f"https://github.com/{OWNER}/{REPO}",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())