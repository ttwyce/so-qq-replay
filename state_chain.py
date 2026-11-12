# -*- coding: utf-8 -*-
"""
会话状态链闭环验收（同一 uid / 同一 session chain）。

create(query_get SSE) -> session_get -> session_list -> session_delete -> 复核
所有请求由纯 Python 生成 verify，浏览器-free。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid

import main
from replay_query import BASE, HOME, get_uid

UA = main.UA


def post(name: str, body: dict, uid: str, *, signer: str = "aimodeRequest",
         accept: str = "application/json", timeout: int = 25):
    url = BASE + name
    payload = main.build_signed_body(url, body, uid, signer=signer).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json", "Accept": accept,
        "User-Agent": UA, "Origin": HOME, "Referer": HOME + "/",
    })
    return urllib.request.urlopen(req, timeout=timeout)


def json_call(name: str, body: dict, uid: str) -> dict:
    with post(name, body, uid) as r:
        return {"status": r.status,
                "body": json.loads(r.read().decode("utf-8", "replace"))}


def create_session(uid: str, sid: str, query: str) -> dict:
    """query_get SSE：用固定 uid/sid 创建会话，读完整流。"""
    body = {
        "session_id": sid, "stream": True, "uid": uid, "qinfo": "",
        "query": query, "enable_enhancement": True, "model": "deepseek-v3",
        "ext": {"regen_query_id": -1, "neo_sphere": "outer"},
    }
    r = post("query_get", body, uid, accept="text/event-stream",
             signer="addAuthToBody", timeout=30)
    ct = r.headers.get("content-type", "")
    content, query_id, frames = [], None, 0
    buf = b""
    t0 = time.time()
    while time.time() - t0 < 25 and frames < 300:
        chunk = r.read(1)
        if not chunk:
            break
        buf += chunk
        while b"\n\n" in buf:
            raw, buf = buf.split(b"\n\n", 1)
            data = "\n".join(l[5:].strip() for l in
                             raw.decode("utf-8", "replace").splitlines()
                             if l.startswith("data:"))
            if not data or data == "[DONE]":
                continue
            frames += 1
            try:
                obj = json.loads(data)
            except Exception:
                continue
            if obj.get("query_id") and not query_id:
                query_id = obj["query_id"]
            c = ((obj.get("choices") or [{}])[0].get("delta") or {}).get("content")
            if c:
                content.append(c)
    try:
        r.close()
    except Exception:
        pass
    return {"content_type": ct, "frames": frames, "query_id": query_id,
            "answer_chars": len("".join(content))}


def session_ids(obj: dict) -> list:
    return [str(x.get("session_id")) for x in (obj.get("session_list") or [])]


def main_entry() -> int:
    uid = get_uid()             # 全链路唯一 uid
    sid = str(uuid.uuid4())
    print(f"[chain] uid={uid} sid={sid}", file=sys.stderr)

    out = {"uid": uid, "sid": sid, "steps": []}

    # 1) create
    c = create_session(uid, sid, "用一句话说明会话状态链测试")
    out["steps"].append({"step": "create_query_get", **c})
    print("[1 create]", c, file=sys.stderr)
    time.sleep(1)

    # 2) session_get 读回
    g1 = json_call("session_get", {"session_id": sid, "biz": 6, "uid": uid}, uid)
    b1 = g1["body"]
    out["steps"].append({"step": "session_get_after_create",
                         "ret_code": b1.get("ret_code"),
                         "is_valid": b1.get("is_valid"),
                         "queries": len(b1.get("queries") or []),
                         "keys": sorted(b1.keys())})
    print("[2 get]", b1.get("ret_code"), b1.get("is_valid"),
          len(b1.get("queries") or []), file=sys.stderr)

    # 3) session_list 应含该 sid
    l1 = json_call("session_list", {"uid": uid}, uid)["body"]
    out["steps"].append({"step": "session_list_after_create",
                         "ret_code": l1.get("ret_code"),
                         "ids": session_ids(l1)[:5],
                         "contains_sid": sid in session_ids(l1)})
    print("[3 list]", l1.get("ret_code"), session_ids(l1)[:5], file=sys.stderr)

    # 4) session_delete 真删
    d = json_call("session_delete", {"uid": uid, "session_ids": [sid]}, uid)["body"]
    out["steps"].append({"step": "session_delete", "ret_code": d.get("ret_code"),
                         "message": d.get("message"), "keys": sorted(d.keys())})
    print("[4 delete]", d, file=sys.stderr)
    time.sleep(1)

    # 5) 复核：session_get + session_list
    g2 = json_call("session_get", {"session_id": sid, "biz": 6, "uid": uid}, uid)["body"]
    l2 = json_call("session_list", {"uid": uid}, uid)["body"]
    out["steps"].append({"step": "verify_after_delete",
                         "get_is_valid": g2.get("is_valid"),
                         "get_queries": len(g2.get("queries") or []),
                         "list_contains_sid": sid in session_ids(l2),
                         "list_ids": session_ids(l2)[:5]})
    print("[5 verify]", g2.get("is_valid"), sid in session_ids(l2), file=sys.stderr)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())