# -*- coding: utf-8 -*-
"""
纯 Python 全接口验收（浏览器-free）。

对 /browser_aimode/aimode/* 的所有已证实端点做签名 + 现网重放，
并对 query_get SSE 主链路做 3 次重复验收。
JSON 报告写 stdout，关键日志写 stderr。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

import main
from replay_query import BASE, HOME, get_uid, post_json, run_one

UID = None


def call(name: str, body: dict, *, signer: str = "aimodeRequest",
         accept: str = "application/json") -> dict:
    url = BASE + name
    payload = main.build_signed_body(url, body, UID, signer=signer).encode()
    rq = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json", "Accept": accept,
        "User-Agent": main.UA, "Origin": HOME, "Referer": HOME + "/",
    })
    try:
        with urllib.request.urlopen(rq, timeout=20) as r:
            raw = r.read().decode("utf-8", "replace")
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {"raw": raw[:200]}
        return {"status": r.status, "ret_code": obj.get("ret_code"),
                "keys": sorted(obj.keys())[:12], "head": raw[:180]}
    except Exception as e:
        return {"error": repr(e)}


def main_entry() -> int:
    global UID
    UID = get_uid()
    print("[verify] uid=" + UID, file=sys.stderr)

    out = {"uid": UID, "shape": "compact-replay (browser-free)", "base": BASE,
           "endpoints": {}, "query_replays": []}

    tests = [
        ("session_list", {"uid": UID}),
        ("session_list_page", {"uid": UID, "page": 1, "page_size": 20}),
        ("session_get", {"session_id": "no-such-session", "biz": 6, "uid": UID}),
        ("session_delete", {"uid": UID, "session_ids": []}),
        ("query_stop", {"session_id": "no-such-session", "query_id": 1,
                        "uid": UID, "partial_text": ""}),
    ]
    for name, body in tests:
        out["endpoints"][name] = call(name, body)
        print(f"[{name}] {out['endpoints'][name].get('ret_code')}", file=sys.stderr)

    # query_new 在 /browser_aimode 前缀下的负对照
    out["endpoints"]["query_new_browser_base"] = call(
        "query_new", {"uid": UID, "query": "hi"})

    # 主链路 3 次（每次全新 uid? 不：同一 session chain 用同一 uid，新 sid）
    for i in range(3):
        r = run_one("用一句话介绍Python" if i else "什么是Python?")
        out["query_replays"].append({
            "i": i + 1, "frames": r["frames"], "answer_chars": r["answer_chars"],
            "query_id": r["query_id"], "done": r["done"],
            "query_stop": r.get("query_stop", {}).get("status"),
            "answer_head": r["answer_head"][:60],
        })
        print(f"[replay {i+1}] frames={r['frames']} chars={r['answer_chars']}",
              file=sys.stderr)
        time.sleep(1)

    ok = all(x["answer_chars"] > 0 for x in out["query_replays"])
    out["all_query_replays_ok"] = ok
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main_entry())