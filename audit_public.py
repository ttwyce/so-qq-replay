# -*- coding: utf-8 -*-
"""公开前内容审计：只报告命中位置与数量，绝不打印敏感值本身。"""
from __future__ import annotations

import os
import re

ROOT = "."

PATTERNS = {
    "auth_token_literal": r"aimode_token_\d+",
    "atta_token_pair": r'"(?:attaid|token)"\s*:\s*"\d+"',
    "cookie_assignment": r"document\.cookie\s*=|Set-Cookie|qb_[a-z_]+\s*=",
    "cuid_uid_sample": r"cuid_[A-Za-z0-9+/=]{16,}",
    "user_ip": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "uuid_sample": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "trace_id": r'"traceId"\s*:\s*"[0-9a-f]{20,}"',
    "cos_presign": r"q-sign-algorithm|X-Amz-Signature|q-sign-time",
    "cdn_presigned_url": r"https://photolearning-[^\"'\s]+",
}
SKIP_DIRS = {".git", "__pycache__", ".venv"}


def main():
    findings = {k: [] for k in PATTERNS}
    files_scanned = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > 8_000_000:
                    continue
                s = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            files_scanned += 1
            for name, pat in PATTERNS.items():
                n = len(re.findall(pat, s))
                if n:
                    findings[name].append((p.replace("\\", "/"), n))

    print("files_scanned:", files_scanned)
    for name, hits in findings.items():
        print("\n[%s] files=%d total_hits=%d" %
              (name, len(hits), sum(n for _, n in hits)))
        for p, n in sorted(hits, key=lambda x: -x[1])[:12]:
            print("   %4d  %s" % (n, p))

    # 体积/第三方代码清单
    print("\n[large_or_third_party]")
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            sz = os.path.getsize(p)
            if sz > 200_000:
                print("   %9d  %s" % (sz, p.replace("\\", "/")))
    print("\n[dirs]")
    for d in sorted(os.listdir(ROOT)):
        if os.path.isdir(os.path.join(ROOT, d)):
            total = sum(os.path.getsize(os.path.join(dp, f))
                        for dp, _, fs in os.walk(os.path.join(ROOT, d))
                        for f in fs)
            print("   %9d  %s/" % (total, d))


if __name__ == "__main__":
    main()