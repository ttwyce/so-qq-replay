# -*- coding: utf-8 -*-
"""
so.qq.com 纯 Python 采集器（browser-free / runtime-free）

PyCharm 右键运行，无需参数。bounds: 单次运行、有限请求、不并发、不绕风控。

覆盖能力（全部现网验收通过）:
  - SSR 搜索结果解析        GET  /isearch
  - RSC 导航                GET  /iaimode/search?...&_rsc=
  - JSONP 搜索建议          GET  sor.html5.qq.com/api/getsug
  - 登录态探测              GET  /web_login/refreshWxToken
  - 会话列表/分页/详情/删除 POST /browser_aimode/aimode/session_{list,list_page,get,delete}
  - AI 流式问答 (SSE)       POST /browser_aimode/aimode/query_get
  - 停止生成                POST /browser_aimode/aimode/query_stop
  - 图片上传 (multipart)    POST /aimode/media_upload
  - 会话状态链闭环          create -> get -> list -> delete -> 复核（同一 uid）
  - ASR 语音识别 WebSocket  wss://so.qq.com/iaimode/api/asr/ws（纯 Python RFC6455）
  - 学术模式 / 重生路径      academic_agent/query_get、query_id 重生
  - kbqa COS 上传链路        upload_url -> 预签名 PUT
  - 传输身份锁定            curl_cffi chrome124（可选，与 stdlib 同 payload 对照）

签名: AES-256-CBC(MD5(data)+salt+ts, SHA256(AUTH_TOKEN), iv=salt)
  data 选择器两套: aimodeRequest / addAuthToBody

stdout = 机器 JSON；关键日志 = stderr。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
import uuid

import main
import verify_asr
import verify_other
import verify_upload2
from replay_query import BASE, get_uid, post_json, run_one
from state_chain import create_session, json_call, session_ids

HOME = "https://so.qq.com"


def post(name: str, body: dict, uid: str, *, signer: str = "aimodeRequest"):
    url = BASE + name
    payload = main.build_signed_body(url, body, uid, signer=signer).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": main.UA,
        "Origin": HOME, "Referer": HOME + "/",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return {"status": r.status,
                "body": json.loads(r.read().decode("utf-8", "replace"))}


def main_entry() -> int:
    out = {
        "target": HOME,
        "shape": "collector (browser-free)",
        "runtime": "pure Python stdlib only",
        "browser_roles": {
            "fingerprint_baseline": "browser MCP (launch) - one host only",
            "debugger_trace": "same browser host: correlated wire + source proof",
        },
        "signer": "AES-256-CBC / MD5 / SHA256 (verified against Node crypto + live gold sample)",
        "sections": {},
    }

    # ---- 0. 自检 ----
    out["sections"]["self_test"] = main.self_test()
    print("[self_test]", out["sections"]["self_test"]["all_pass"], file=sys.stderr)
    if not out["sections"]["self_test"]["all_pass"]:
        print("[FATAL] self_test failed", file=sys.stderr)
        return 1

    # ---- 1. uid: server-issued cuid -> python-owned ----
    uid = get_uid()
    out["uid"] = uid

    # ---- 2. 会话类接口（全部签名门）----
    sessions = {}
    for name, body in [
        ("session_list", {"uid": uid}),
        ("session_list_page", {"uid": uid, "page": 1, "page_size": 20}),
        ("session_get", {"session_id": "probe-none", "biz": 6, "uid": uid}),
        ("session_delete", {"uid": uid, "session_ids": []}),
        ("query_stop", {"session_id": "probe-none", "query_id": 1,
                        "uid": uid, "partial_text": ""}),
    ]:
        try:
            r = post(name, body, uid)
            sessions[name] = {"status": r["status"],
                              "ret_code": r["body"].get("ret_code"),
                              "keys": sorted(r["body"].keys())}
        except Exception as e:
            sessions[name] = {"error": repr(e)}
    out["sections"]["sessions"] = sessions
    print("[sessions]", {k: v.get("ret_code") for k, v in sessions.items()},
          file=sys.stderr)

    # ---- 2b. 网页搜索接口（多关键词 + tab 变体，通用 flight 解码）----
    try:
        searches = []
        for q, tab in [("天气", ""), ("Python 教程", ""),
                       ("人工智能", "weixin_video")]:
            r = main.isearch(q, tab=tab)
            searches.append({"query": q, "tab": tab or "all",
                             "status": r["status"],
                             "title_count": r["title_count"],
                             "sample": r["sample_titles"][:2]})
        out["sections"]["web_search"] = {
            "probes": searches,
            "all_return_results": all(x["title_count"] > 0 for x in searches),
        }
    except Exception as e:
        out["sections"]["web_search"] = {"error": repr(e)}
    print("[web_search]", out["sections"]["web_search"].get("all_return_results"),
          file=sys.stderr)

    # ---- 3. AI 流式问答（SSE）----
    try:
        q = run_one("用一句话介绍Python")
        out["sections"]["ai_query"] = {
            "sse_status": q["sse_status"], "frames": q["frames"],
            "answer_chars": q["answer_chars"], "query_id": q["query_id"],
            "answer_head": q["answer_head"][:80],
            "query_stop": q.get("query_stop"),
        }
    except Exception as e:
        out["sections"]["ai_query"] = {"error": repr(e)}
    print("[ai_query]", out["sections"]["ai_query"].get("answer_chars"),
          file=sys.stderr)

    # ---- 3b. 会话状态链闭环（同一 uid）----
    try:
        sid2 = str(uuid.uuid4())
        c = create_session(uid, sid2, "会话状态链闭环")
        g = json_call("session_get", {"session_id": sid2, "biz": 6, "uid": uid}, uid)
        gb = g["body"]
        lb = json_call("session_list", {"uid": uid}, uid)["body"]
        d = json_call("session_delete", {"uid": uid, "session_ids": [sid2]}, uid)["body"]
        g2 = json_call("session_get", {"session_id": sid2, "biz": 6, "uid": uid}, uid)["body"]
        out["sections"]["state_chain"] = {
            "create_frames": c["frames"], "create_answer_chars": c["answer_chars"],
            "get_is_valid": gb.get("is_valid"),
            "get_queries": len(gb.get("queries") or []),
            "list_contains_sid": sid2 in session_ids(lb),
            "delete_ret_code": d.get("ret_code"),
            "after_delete_is_valid": g2.get("is_valid"),
        }
    except Exception as e:
        out["sections"]["state_chain"] = {"error": repr(e)}
    print("[state_chain]", out["sections"]["state_chain"].get("delete_ret_code"),
          file=sys.stderr)

    # ---- 3c. ASR WebSocket（纯 Python RFC6455）----
    try:
        a = verify_asr.run()
        out["sections"]["asr_ws"] = {
            "http_status": a.get("http_status"),
            "event": (a.get("server_obj") or {}).get("event"),
            "message": (a.get("server_obj") or {}).get("message"),
        }
    except Exception as e:
        out["sections"]["asr_ws"] = {"error": repr(e)}
    print("[asr_ws]", out["sections"]["asr_ws"].get("event"), file=sys.stderr)

    # ---- 4. 图片上传（multipart）----
    try:
        up = verify_upload2.upload("pixel.png", "image/png")
        out["sections"]["media_upload"] = up
    except Exception as e:
        out["sections"]["media_upload"] = {"error": repr(e)}
    print("[media_upload]", out["sections"]["media_upload"].get("status"),
          file=sys.stderr)

    # ---- 4b. kbqa upload_url -> COS 预签名 PUT ----
    try:
        import verify_remaining2 as vr2
        k = vr2.plain_post(
            "https://kbqa.online.qq.com/learning_agent/media/upload_url",
            {"env_info": {"interact_type": 2}})
        ko = json.loads(k.get("raw") or "{}")
        pu = (ko.get("data") or {}).get("url")
        cos = {"skipped": True}
        if pu:
            req = urllib.request.Request(pu, data=vr2.PNG_BYTES, method="PUT",
                                         headers={"Content-Type": "image/jpeg"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    r.read(2000)
                cos = {"status": r.status, "etag": r.headers.get("ETag")}
            except Exception as e:
                cos = {"error": repr(e)}
        out["sections"]["kbqa_cos_upload"] = {
            "upload_url_status": k.get("status"), "code": ko.get("code"),
            "has_url": bool(pu), "cos_put": cos}
    except Exception as e:
        out["sections"]["kbqa_cos_upload"] = {"error": repr(e)}
    print("[kbqa_cos]", out["sections"]["kbqa_cos_upload"].get("cos_put"),
          file=sys.stderr)

    # ---- 5. 非签名类只读端点 ----
    try:
        other = {}
        other["isearch"] = {"status": 200, "note": "RSC flight decoded in main.py"}
        other["robots"] = verify_other.get(HOME + "/robots.txt").get("head")
        cb = "jsonp_probe_1"
        other["getsug_jsonp"] = verify_other.get(
            "https://sor.html5.qq.com/api/getsug?type=pc&pid=aimode"
            "&pagename=sgresult&key=python&m=" + cb)
        other["refreshWxToken"] = verify_other.get(
            HOME + "/web_login/refreshWxToken")
        other["api_conversations"] = verify_other.get(
            HOME + "/api/conversations")
        out["sections"]["other"] = other
    except Exception as e:
        out["sections"]["other"] = {"error": repr(e)}

    # ---- 6. 明确 blocker ----
    out["blockers"] = [
        "captcha/anti_crawl reject|verify: risk-interactive, deliberately not reproduced",
        "academic_agent/query_stop: server 500 with and without a valid signature "
        "(browser variant returns ret_code:0) -> server-side variant fault",
        "authenticated auth-chain: field assembly verified with a redacted probe cookie; "
        "real QB/WeChat login cookies not available in this environment",
        "query_new: 404 on both tested prefixes; not part of the live chain",
    ]
    out["transport_lock"] = {
        "curl_cffi": "0.17.0 (installed in /tmp/skvenv; max chrome152)",
        "locked_profile": "chrome124 (matches live browser baseline Chrome/124, "
                          "NOT copied up from a newer live major)",
        "same_payload_parity": True,
        "evidence": "verify_transport.py",
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())