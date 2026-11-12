# -*- coding: utf-8 -*-
"""
学术模式变体 + 裸 base query_new + query_get 重生路径的受控验证。

每个变体单独一次、有界、不重试风控。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid

import main
from replay_query import HOME, get_uid

UA = main.UA
PLAIN = "https://lizhiassistant.search.qq.com"
BROWSER = PLAIN + "/browser_aimode"


def signed(url: str, body: dict, uid: str, signer: str = "aimodeRequest"):
    return main.build_signed_body(url, body, uid, signer=signer).encode()


def call(url: str, body: dict, uid: str, *, signer: str = "aimodeRequest",
         accept: str = "application/json", timeout: int = 20):
    req = urllib.request.Request(url, data=signed(url, body, uid, signer),
                                 method="POST", headers={
        "Content-Type": "application/json", "Accept": accept,
        "User-Agent": UA, "Origin": HOME, "Referer": HOME + "/",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(262144).decode("utf-8", "replace")  # 有界 256KB，不截断 SSE
        ct = r.headers.get("content-type")
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {"raw": raw}          # SSE 是 NDJSON 流，保留全文
        if not isinstance(obj, dict):
            obj = {"value": obj}
        return {"status": r.status, "ct": ct, "obj": obj,
                "bytes": len(raw.encode("utf-8", "replace"))}
    except Exception as e:
        return {"error": repr(e), "status": None, "obj": None}


def sse(url: str, body: dict, uid: str) -> dict:
    r = call(url, body, uid, signer="addAuthToBody",
             accept="text/event-stream", timeout=25)
    if "error" in r:
        return r
    # call() 已读完 body（非流式），SSE 文本直接落 obj.raw
    raw = r["obj"].get("raw", "")
    frames = [x for x in raw.split("\n\n") if x.strip().startswith("data:")]
    return {"status": r["status"], "ct": r["ct"],
            "bytes": len(raw), "frames": len(frames),
            "head": raw[:300], "tail": raw[-160:]}


def brief(r: dict) -> dict:
    return {"status": r.get("status"), "error": r.get("error"),
            "obj": r.get("obj")}


def main_entry() -> int:
    uid = get_uid()
    sid = str(uuid.uuid4())
    out = {"uid": uid, "sid": sid, "variants": {}}
    print(f"[variants] uid={uid}", file=sys.stderr)

    qbody = {"session_id": sid, "stream": True, "uid": uid, "qinfo": "",
             "query": "什么是微分方程?", "enable_enhancement": True,
             "model": "deepseek-v3",
             "ext": {"regen_query_id": -1, "neo_sphere": "outer"}}

    # A) academic_agent/query_get（学术模式，裸 base 前缀）
    a = sse(PLAIN + "/academic_agent/query_get", dict(qbody), uid)
    out["variants"]["academic_query_get"] = a
    print("[A academic]", a.get("status"), a.get("frames"), file=sys.stderr)

    # B) academic_agent/query_stop
    b = call(PLAIN + "/academic_agent/query_stop",
             {"session_id": sid, "query_id": 1, "uid": uid,
              "partial_text": ""}, uid)
    out["variants"]["academic_query_stop"] = brief(b)
    print("[B academic_stop]", b.get("status"), b.get("error"), file=sys.stderr)

    # C) 裸 base /aimode/query_new
    c = call(PLAIN + "/aimode/query_new",
             {"uid": uid, "query": "hi", "session_id": sid}, uid)
    out["variants"]["plain_query_new"] = brief(c)
    print("[C plain_query_new]", c.get("status"), c.get("error"), file=sys.stderr)

    # D) 裸 base /aimode/session_list（对比 base 前缀敏感性）
    d = call(PLAIN + "/aimode/session_list", {"uid": uid}, uid)
    out["variants"]["plain_session_list"] = brief(d)
    print("[D plain_session_list]", d.get("status"), file=sys.stderr)

    # E) query_get 重生路径（regen_query_id > 0，无 query 字段）
    # 先真创建一轮拿 query_id，再用同 sid 重生
    r = call(BROWSER + "/aimode/query_get", dict(qbody), uid,
             signer="addAuthToBody", accept="text/event-stream")
    raw = r.get("obj", {}).get("raw", "")
    qid = None
    for f in raw.split("\n\n"):
        if '"query_id"' in f:
            try:
                qid = json.loads(f.split("data:", 1)[1].strip()).get("query_id")
            except Exception:
                pass
            if qid:
                break
    regen = {"session_id": sid, "stream": True, "uid": uid, "qinfo": "",
             "query_id": qid or 1,
             "ext": {"regen_query_id": qid or 1, "neo_sphere": "outer"}}
    e = call(BROWSER + "/aimode/query_get", regen, uid,
             signer="addAuthToBody", accept="text/event-stream")
    eraw = e.get("obj", {}).get("raw", "")
    out["variants"]["regen_query_get"] = {
        "created_query_id": qid,
        "create_bytes": len(raw),
        "status": e.get("status"), "ct": e.get("ct"),
        "bytes": len(eraw),
        "frames": len([x for x in eraw.split("\n\n") if "data:" in x]),
        "head": eraw[:240]}
    print("[E regen]", qid, e.get("status"), len(eraw), file=sys.stderr)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())