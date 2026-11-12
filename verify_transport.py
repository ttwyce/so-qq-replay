# -*- coding: utf-8 -*-
"""
传输身份锁定验证：curl_cffi chrome124 vs stdlib urllib，同一 wire bytes。

运行： /tmp/skvenv/bin/python verify_transport.py

用当前时间戳生成固定 verify（salt 固定、ts 当前），使两个客户端的
body 字节完全一致；唯一变量是 HTTP 客户端 / TLS-H2 指纹。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.request

import main

try:
    from curl_cffi import requests as cr
except ImportError:
    print("需要 curl_cffi：uv venv /tmp/skvenv && "
          "uv pip install --python /tmp/skvenv/bin/python curl_cffi",
          file=sys.stderr)
    raise

HOME = "https://so.qq.com"
BASE = "https://lizhiassistant.search.qq.com/browser_aimode/aimode/"
IMPERSONATE = "chrome124"          # 与浏览器基线 UA Chrome/124 对齐
SALT = bytes.fromhex("00112233445566778899aabbccddeeff")


def cuid_from_html(html: str) -> str:
    m = re.search(r'cuid(?:\\"){0,2}:[^A-Za-z0-9]{0,6}([A-Za-z0-9+/=]{20,})',
                  html)
    if not m:
        raise RuntimeError("cuid not found")
    return "cuid_" + m.group(1)


def fixed_payload(url: str, body: dict, uid: str, signer: str,
                  ts: int) -> bytes:
    v = main.generate_auth_sign(
        main.sign_data_for(url, body, uid, signer=signer),
        salt=SALT, timestamp=ts)
    return main.build_signed_body(url, body, uid, verify=v,
                                  signer=signer).encode()


def urllib_post(url: str, payload: bytes, accept: str) -> dict:
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json", "Accept": accept,
        "User-Agent": main.UA, "Origin": HOME, "Referer": HOME + "/",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read(262144).decode("utf-8", "replace")
        return {"status": r.status, "bytes": len(raw), "head": raw[:200]}
    except Exception as e:
        return {"error": repr(e)}


def cf_post(session, url: str, payload: bytes, accept: str) -> dict:
    try:
        r = session.post(url, data=payload, timeout=30, headers={
            "Content-Type": "application/json", "Accept": accept,
            "Origin": HOME, "Referer": HOME + "/",
        })
        raw = r.text[:262144]
        return {"status": r.status_code, "bytes": len(r.content),
                "head": raw[:200], "http_version": getattr(r, "http_version", None)}
    except Exception as e:
        return {"error": repr(e)}


def ok_json(r: dict) -> bool:
    return (r.get("status") == 200
            and '"ret_code":0' in r.get("head", "").replace(" ", ""))


def ok_sse(r: dict) -> bool:
    h = r.get("head", "")
    return (r.get("status") == 200 and "anti_crawl" in h
            and "authentication failed" not in h)


def main_entry() -> int:
    out = {"impersonate": IMPERSONATE, "curl_cffi": "0.17.0"}
    ts = int(time.time())
    out["timestamp"] = ts

    s = cr.Session(impersonate=IMPERSONATE)
    home = s.get(HOME + "/", timeout=20)
    out["home"] = {"status": home.status_code, "bytes": len(home.content)}
    uid = cuid_from_html(home.text)
    out["uid"] = uid

    # 1) session_list_page：同一 payload 两个客户端
    url = BASE + "session_list_page"
    body = {"uid": uid, "page": 1, "page_size": 20}
    p = fixed_payload(url, body, uid, "aimodeRequest", ts)
    out["payload_sha256"] = hashlib.sha256(p).hexdigest()
    out["session_list_page"] = {
        "curl_cffi": cf_post(s, url, p, "application/json"),
        "stdlib": urllib_post(url, p, "application/json"),
    }

    # 2) query_get SSE：同一 payload 两个客户端（签名数据 = query）
    qurl = BASE + "query_get"
    qbody = {"session_id": "transport-probe", "stream": True, "uid": uid,
             "qinfo": "", "query": "用一句话介绍Python",
             "enable_enhancement": True, "model": "deepseek-v3",
             "ext": {"regen_query_id": -1, "neo_sphere": "outer"}}
    qp = fixed_payload(qurl, qbody, uid, "addAuthToBody", ts)
    out["query_get"] = {
        "curl_cffi": cf_post(s, qurl, qp, "text/event-stream"),
        "stdlib": urllib_post(qurl, qp, "text/event-stream"),
    }

    a = out["session_list_page"]["curl_cffi"]
    b = out["session_list_page"]["stdlib"]
    q1 = out["query_get"]["curl_cffi"]
    q2 = out["query_get"]["stdlib"]
    out["transport_parity"] = (ok_json(a) and ok_json(b)
                               and ok_sse(q1) and ok_sse(q2)
                               and a.get("head") == b.get("head"))
    print("[transport]", IMPERSONATE, "parity=", out["transport_parity"],
          file=sys.stderr)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["transport_parity"] else 1


if __name__ == "__main__":
    sys.exit(main_entry())