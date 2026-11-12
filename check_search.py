# -*- coding: utf-8 -*-
"""搜索接口现网实测：/isearch 多关键词 + tab 变体 + 联想词 + 负对照。"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

import main

HOME = "https://so.qq.com"


def raw_get(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={
        "User-Agent": main.UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": HOME + "/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def probe_isearch(query: str, tab: str = "") -> dict:
    try:
        r = main.isearch(query, tab=tab)
    except Exception as e:
        return {"query": query, "tab": tab or "all", "error": repr(e)}
    return {"query": query, "tab": tab or "all",
            "status": r["status"], "html_bytes": r["html_bytes"],
            "blocks": r["flight_blocks"], "title_count": r["title_count"],
            "sample_titles": r["sample_titles"]}


def probe_sug(key: str) -> dict:
    cb = "jsonp_probe_%d" % int(time.time() * 1000)
    url = ("https://sor.html5.qq.com/api/getsug?type=pc&pid=aimode"
           "&pagename=sgresult&key=" + urllib.parse.quote(key) + "&m=" + cb)
    try:
        status, text = raw_get(url)
        # GBK 编码，容错解码
        try:
            raw = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": main.UA}),
                timeout=15).read()
            text = raw.decode("gbk", "replace")
        except Exception:
            pass
        return {"key": key, "status": status, "bytes": len(text),
                "callback_ok": text.lstrip().startswith(cb),
                "head": text[:120]}
    except Exception as e:
        return {"key": key, "error": repr(e)}


def main_entry() -> int:
    out = {"searches": [], "sug": [], "ai_search": None}

    for q in ["天气", "Python 教程", "腾讯 2026 财报"]:
        r = probe_isearch(q)
        out["searches"].append(r)
        print("[isearch]", q, r.get("status"), r.get("title_count"),
              file=sys.stderr)
        time.sleep(0.5)

    for tab in ["xueshu", "weixin_article", "weixin_video", "media"]:
        r = probe_isearch("人工智能", tab)
        out["searches"].append(r)
        print("[tab]", tab, r.get("status"), r.get("title_count"),
              file=sys.stderr)
        time.sleep(0.5)

    # 负对照：空 query
    out["negative_empty_query"] = probe_isearch("")
    print("[neg]", out["negative_empty_query"].get("status"),
          out["negative_empty_query"].get("title_count"), file=sys.stderr)

    for k in ["python", "天气"]:
        r = probe_sug(k)
        out["sug"].append(r)
        print("[sug]", k, r.get("status"), r.get("callback_ok"),
              file=sys.stderr)

    # AI 模式搜索（SSE 问答）也确认可用
    try:
        from replay_query import run_one
        q = run_one("用一句话解释什么是搜索接口")
        out["ai_search"] = {"sse_status": q["sse_status"],
                            "frames": q["frames"],
                            "answer_chars": q["answer_chars"],
                            "answer_head": q["answer_head"][:80]}
        print("[ai_search]", q["answer_chars"], file=sys.stderr)
    except Exception as e:
        out["ai_search"] = {"error": repr(e)}

    ok = (all(x.get("status") == 200 and x.get("title_count", 0) > 0
              for x in out["searches"][:3])
          and all(x.get("callback_ok") for x in out["sug"])
          and (out["ai_search"] or {}).get("answer_chars", 0) > 0)
    out["all_usable"] = ok
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main_entry())