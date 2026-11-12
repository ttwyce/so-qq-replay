# -*- coding: utf-8 -*-
"""
纯 Python 端到端复现 so.qq.com AI 问答链路（浏览器-free）。

链路:
  1) GET /  -> 从 RSC flight 提取 server-issued cuid -> uid = "cuid_" + cuid
  2) POST /browser_aimode/aimode/query_get (Accept: text/event-stream)
       body = addAuthToBody({session_id, stream, uid, qinfo, query,
                             enable_enhancement, model, ext}, uid)
       读 SSE 帧 -> query_id / choices[0].delta.content
  3) POST /browser_aimode/aimode/query_stop {session_id, query_id, uid, partial_text}
  4) POST /browser_aimode/aimode/session_get {session_id, biz:6, uid}

只读 / 有界 / 无登录态 / 不重试风控。stdout=JSON, 关键日志=stderr。
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid

import main  # 复用已验证的签名实现

HOME = "https://so.qq.com"
BASE = "https://lizhiassistant.search.qq.com/browser_aimode/aimode/"


def get_uid() -> str:
    req = urllib.request.Request(HOME + "/", headers={"User-Agent": main.UA})
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    m = re.search(r'cuid(?:\\"){0,2}:[^A-Za-z0-9]{0,6}([A-Za-z0-9+/=]{20,})', html)
    if not m:
        raise RuntimeError("cuid not found in home RSC flight")
    return "cuid_" + m.group(1)


def post_json(name: str, body: dict, uid: str, *, accept: str = "application/json",
              timeout: int = 30, signer: str = "aimodeRequest"):
    url = BASE + name
    payload = main.build_signed_body(url, body, uid, signer=signer).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": accept,
        "User-Agent": main.UA,
        "Origin": HOME,
        "Referer": HOME + "/",
    }
    req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def run_one(query: str) -> dict:
    uid = get_uid()
    sid = str(uuid.uuid4())
    print(f"[run] uid={uid} sid={sid} query={query}", file=sys.stderr)

    body = {
        "session_id": sid,
        "stream": True,
        "uid": uid,
        "qinfo": "",
        "query": query,
        "enable_enhancement": True,
        "model": "deepseek-v3",
        "ext": {"regen_query_id": -1, "neo_sphere": "outer"},
    }

    resp = post_json("query_get", body, uid, accept="text/event-stream",
                     timeout=30, signer="addAuthToBody")
    ct = resp.headers.get("content-type", "")
    status = resp.status
    print(f"[sse] status={status} content-type={ct}", file=sys.stderr)

    frames, content, query_id, done = [], [], None, False
    buf = b""
    t0 = time.time()
    # 有界：最多 20s / 200 帧 / 64KB
    while time.time() - t0 < 20 and len(frames) < 200 and len(buf) < 65536:
        chunk = resp.read(1)
        if not chunk:
            break
        buf += chunk
        while b"\n\n" in buf:
            raw, buf = buf.split(b"\n\n", 1)
            text = raw.decode("utf-8", "replace")
            data = "\n".join(l[5:].strip() for l in text.splitlines()
                             if l.startswith("data:"))
            if not data:
                continue
            frames.append(data[:400])
            if data == "[DONE]":
                done = True
                break
            try:
                obj = json.loads(data)
            except Exception:
                continue
            if obj.get("query_id") and not query_id:
                query_id = obj["query_id"]
            ch = (obj.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            c = delta.get("content")
            if c:
                content.append(c)
            if obj.get("data_type") == "anti_crawl":
                print("[sse] anti_crawl frame", file=sys.stderr)
        if done:
            break
    try:
        resp.close()
    except Exception:
        pass

    answer = "".join(content)
    out = {
        "uid": uid, "session_id": sid, "query": query,
        "sse_status": status, "sse_content_type": ct,
        "frames": len(frames), "done": done,
        "query_id": query_id,
        "answer_chars": len(answer),
        "answer_head": answer[:120],
        "frame_samples": frames[:3],
    }

    # 停止生成（仅当拿到 query_id）
    if query_id:
        try:
            r = post_json("query_stop", {"session_id": sid, "query_id": query_id,
                                         "uid": uid, "partial_text": answer}, uid)
            out["query_stop"] = {"status": r.status,
                                 "body": r.read().decode("utf-8", "replace")[:300]}
        except Exception as e:
            out["query_stop"] = {"error": repr(e)}
    return out


def main_entry() -> int:
    result = run_one("什么是Python?")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("frames", 0) > 0 else 1


if __name__ == "__main__":
    sys.exit(main_entry())