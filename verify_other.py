# -*- coding: utf-8 -*-
"""其余非签名类端点的纯 Python 复现验收（只读 / 有界）。"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request

import main

HOME = "https://so.qq.com"
UA = main.UA


def get(url: str, headers: dict | None = None, timeout: int = 15) -> dict:
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
         "Referer": HOME + "/"}
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                    timeout=timeout) as r:
            raw = r.read()
        return {"status": r.status, "bytes": len(raw),
                "ct": r.headers.get("content-type"),
                "head": raw[:260].decode("utf-8", "replace")}
    except Exception as e:
        return {"error": repr(e)}


def main_entry() -> int:
    out = {"ua": UA, "probes": {}}

    # 1) /isearch SSR 业务页（已验证的 decode-gated 端点）
    q = urllib.parse.quote("天气")
    r = get(HOME + "/isearch?query=" + q + "&quick=1")
    out["probes"]["isearch"] = r
    print("[isearch]", r.get("status"), file=sys.stderr)

    # 2) robots.txt
    out["probes"]["robots"] = get(HOME + "/robots.txt")

    # 3) JSONP 搜索建议
    cb = "jsonp_%d_1" % int(time.time() * 1000)
    sug = ("https://sor.html5.qq.com/api/getsug?type=pc&pid=aimode"
           "&pagename=sgresult&key=" + urllib.parse.quote("python") + "&m=" + cb)
    out["probes"]["getsug_jsonp"] = get(sug)

    # 4) 登录刷新（未登录负对照）
    out["probes"]["refreshWxToken"] = get(HOME + "/web_login/refreshWxToken")

    # 5) 同源会话 API（未登录态 fallback）
    out["probes"]["api_conversations"] = get(HOME + "/api/conversations")

    # 6) RSC 导航（AI 搜索页 sid 续接）
    sid = "<REDACTED_UUID>"
    rsc = (HOME + "/iaimode/search?query=" + urllib.parse.quote("你好")
           + "&sid=" + sid + "&_rsc=il7bb")
    out["probes"]["rsc_navigation"] = get(rsc, headers={"RSC": "1"})

    # 7) ASR WebSocket 端点可达性（HTTP GET 负对照，不建立 WS）
    out["probes"]["asr_ws_http_probe"] = get(
        "https://so.qq.com/iaimode/api/asr/ws?uid=probe")

    # 8) Atta / Aegis 上报端点可达性（不发送真实上报）
    out["probes"]["atta_kv"] = get("https://h.trace.qq.com/kv")

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())