# -*- coding: utf-8 -*-
"""
构建可公开推送的候选目录 public_release/（本地，不联网、不改原文件）。

纳入：纯 Python 源码、parity 脚本、脱敏后的报告、release_meta/ 下的文档、
      README / LICENSE / DISCLAIMER / NOTICE / CONTRIBUTING / SECURITY / .gitignore
排除：chunks/（第三方 JS）、*.html（含 uuid/IP/cuid 快照）、*.bin/*.txt 切片、
      __pycache__、.operit、诊断临时文件
脱敏：IP -> <REDACTED_IP>、uuid -> <REDACTED_UUID>、cuid_xxx -> cuid_<REDACTED>
"""
from __future__ import annotations

import os
import re
import shutil

SRC = "."
DST = "public_release"
META = "release_meta"

# 来自 so_qq_evidence/ 的代码与报告
CODE = [
    "main.py", "collector.py", "replay_query.py", "state_chain.py",
    "verify_all.py", "verify_other.py", "verify_upload2.py",
    "verify_variants.py", "verify_asr.py", "verify_transport.py",
    "verify_remaining2.py", "compare_parity.py", "parity.js",
    "check_search.py", "report.md",
]

# 工作区根目录的维护脚本（发布到 public_release/tools/）
TOOLS = ["build_public_release.py", "install_gh.py", "push_release.py", "gh.sh"]

# release_meta/ 下的文档（单一真相源，原样纳入）
DOCS = ["README.md", "LICENSE", "DISCLAIMER.md", "NOTICE.md",
        "CONTRIBUTING.md", "SECURITY.md"]

GITIGNORE = """__pycache__/
*.pyc
.venv/
.operit/
*.html
chunks/
*.bin
*.log
public_release/
"""

# 注意：此处的正则只用于「脱敏替换」，不打印任何命中值
REPLACERS = [
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<REDACTED_IP>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                re.I), "<REDACTED_UUID>"),
    (re.compile(r"cuid_[A-Za-z0-9+/=]{16,}"), "cuid_<REDACTED>"),
    (re.compile(r'"traceId"\s*:\s*"[0-9a-f]{20,}"'), '"traceId": "<REDACTED>"'),
]

# 这些模式出现在「审计/文档」里是说明性文本，不应被替换或视为泄露
PLAINTEXT_META = set(DOCS) | {"audit_public.py"}


def sanitize(text: str) -> str:
    for pat, rep in REPLACERS:
        text = pat.sub(rep, text)
    return text


def main():
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    os.makedirs(DST)

    kept = []

    # 代码：脱敏后写入
    for rel in CODE:
        src = os.path.join(SRC, "so_qq_evidence", rel)
        if not os.path.exists(src):
            print("MISSING", rel)
            continue
        text = open(src, encoding="utf-8", errors="replace").read()
        with open(os.path.join(DST, rel), "w", encoding="utf-8") as f:
            f.write(sanitize(text))
        kept.append(rel)

    # 审计脚本（根目录，惯例位置）
    shutil.copy2(os.path.join(SRC, "audit_public.py"),
                 os.path.join(DST, "audit_public.py"))
    kept.append("audit_public.py")

    # 维护脚本：发布到 tools/ 子目录
    os.makedirs(os.path.join(DST, "tools"), exist_ok=True)
    for rel in TOOLS:
        src = os.path.join(SRC, rel)
        if not os.path.exists(src):
            print("MISSING TOOL", rel)
            continue
        shutil.copy2(src, os.path.join(DST, "tools", rel))
        kept.append("tools/" + rel)

    # 文档：单一真相源，原样纳入
    for rel in DOCS:
        src = os.path.join(SRC, META, rel)
        if not os.path.exists(src):
            print("MISSING META", rel)
            continue
        shutil.copy2(src, os.path.join(DST, rel))
        kept.append(rel)

    with open(os.path.join(DST, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(GITIGNORE)

    total = sum(os.path.getsize(os.path.join(DST, f))
                for f in os.listdir(DST) if os.path.isfile(os.path.join(DST, f)))
    print("kept:", len(kept) + 1, "files")
    print("total bytes:", total)
    for f in sorted(os.listdir(DST)):
        p = os.path.join(DST, f)
        if os.path.isfile(p):
            print("  %8d  %s" % (os.path.getsize(p), f))


if __name__ == "__main__":
    main()