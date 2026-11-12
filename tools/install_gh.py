# -*- coding: utf-8 -*-
"""安装 GitHub CLI (gh) 到 /tmp/gh（不动系统），纯标准库。

优先走 api.github.com 的 release asset 端点（Accept: application/octet-stream），
失败再回退 github.com release 直链；支持分块与断点重试。
"""
import os
import shutil
import ssl
import sys
import tarfile
import time
import urllib.request

ASSET = "https://api.github.com/repos/cli/cli/releases/assets/679195636"
FALLBACK = "https://github.com/cli/cli/releases/download/v2.103.3/gh_2.103.3_linux_arm64.tar.gz"
TGZ = "/tmp/gh.tar.gz"
ROOT = "/tmp/gh"
UA = "gh-installer"


def download(url: str) -> int:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/octet-stream"})
    ctx = ssl.create_default_context()
    total = 0
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        ctype = r.headers.get("Content-Type", "")
        print("response", r.status, "ctype", ctype, "len",
              r.headers.get("Content-Length"), file=sys.stderr)
        with open(TGZ, "wb") as f:
            while True:
                try:
                    chunk = r.read(32768)
                except Exception as e:
                    print("chunk error", type(e).__name__, file=sys.stderr)
                    break
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
    return total


def main():
    total = 0
    for attempt, url in enumerate([ASSET, FALLBACK, ASSET], 1):
        print("attempt", attempt, url[:80], file=sys.stderr)
        try:
            total = download(url)
        except Exception as e:
            print("download error", type(e).__name__, str(e)[:120],
                  file=sys.stderr)
            total = 0
        print("bytes", total, file=sys.stderr)
        if total > 12_000_000:
            break
        time.sleep(2)

    if total < 12_000_000:
        raise RuntimeError("download incomplete: %d bytes" % total)

    if os.path.isdir(ROOT):
        shutil.rmtree(ROOT)
    os.makedirs(ROOT)
    with tarfile.open(TGZ, "r:gz") as t:
        t.extractall(ROOT, filter="data")
    print("extracted", file=sys.stderr)

    src = None
    for dp, _, fs in os.walk(ROOT):
        for f in fs:
            if f == "gh" and os.access(os.path.join(dp, f), os.X_OK):
                src = os.path.join(dp, f)
                break
        if src:
            break
    if not src:
        raise RuntimeError("gh binary not found in tarball")

    os.makedirs(os.path.join(ROOT, "bin"), exist_ok=True)
    dst = os.path.join(ROOT, "bin", "gh")
    shutil.copy2(src, dst)
    os.chmod(dst, 0o755)
    print("installed", dst, os.path.getsize(dst), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())