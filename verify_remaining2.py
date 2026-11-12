# -*- coding: utf-8 -*-
"""
收尾复现：
  A) academic_agent/query_stop 带签名（aimodePost 等价）+ 读取 HTTPError 500 的 body
  B) kbqa upload_url -> COS 预签名 PUT 上传（纯 Python）
  C) browser query_stop 带签名的正对照
"""
import json
import sys
import urllib.error
import urllib.request
import uuid

import main
from replay_query import get_uid

PLAIN = "https://lizhiassistant.search.qq.com"
BROWSER = PLAIN + "/browser_aimode"
UA = main.UA
BASE_HEADERS = {"User-Agent": UA, "Origin": "https://so.qq.com",
                "Referer": "https://so.qq.com/",
                "Content-Type": "application/json"}


def signed_post(url, body, uid, timeout=20):
    payload = main.build_signed_body(url, body, uid).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers=BASE_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": r.status,
                    "raw": r.read(20000).decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        return {"status": e.code,
                "raw": e.read(20000).decode("utf-8", "replace")}
    except Exception as e:
        return {"error": repr(e)}


def plain_post(url, body, timeout=20, headers=None):
    req = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False,
                             separators=(",", ":")).encode(),
        method="POST", headers={**BASE_HEADERS, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": r.status,
                    "raw": r.read(200000).decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        return {"status": e.code,
                "raw": e.read(20000).decode("utf-8", "replace")}
    except Exception as e:
        return {"error": repr(e)}


PNG = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
       "AAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")
import base64
PNG_BYTES = base64.b64decode(PNG)


def main_entry():
    uid = get_uid()
    sid = str(uuid.uuid4())
    out = {"uid": uid, "sid": sid}

    stop_body = {"session_id": sid, "query_id": 1, "uid": uid,
                 "partial_text": "测试停止"}

    # A) academic_agent/query_stop 带签名
    a = signed_post(PLAIN + "/academic_agent/query_stop", stop_body, uid)
    out["academic_stop_signed"] = {"status": a.get("status"),
                                   "raw": (a.get("raw") or "")[:400]}
    print("[A academic signed]", a.get("status"), (a.get("raw") or "")[:200],
          file=sys.stderr)

    # A2) 同 URL 无签名对照
    a2 = plain_post(PLAIN + "/academic_agent/query_stop", stop_body)
    out["academic_stop_unsigned"] = {"status": a2.get("status"),
                                     "raw": (a2.get("raw") or "")[:300]}
    print("[A2 academic unsigned]", a2.get("status"),
          (a2.get("raw") or "")[:150], file=sys.stderr)

    # C) browser query_stop 带签名正对照
    c = signed_post(BROWSER + "/aimode/query_stop", stop_body, uid)
    out["browser_stop_signed"] = {"status": c.get("status"),
                                  "raw": (c.get("raw") or "")[:300]}
    print("[C browser signed]", c.get("status"), (c.get("raw") or "")[:150],
          file=sys.stderr)

    # B) kbqa upload_url -> COS PUT
    k = plain_post("https://kbqa.online.qq.com/learning_agent/media/upload_url",
                   {"env_info": {"interact_type": 2}})
    try:
        ko = json.loads(k["raw"])
    except Exception:
        ko = {}
    data = ko.get("data") or {}
    put_url = data.get("url")
    file_id = data.get("file_id")
    out["kbqa_upload_url"] = {"status": k.get("status"), "code": ko.get("code"),
                              "has_url": bool(put_url),
                              "has_file_id": bool(file_id),
                              "file_id_prefix": str(file_id)[:24]}
    print("[B kbqa]", k.get("status"), ko.get("code"), bool(put_url),
          file=sys.stderr)

    if put_url:
        # 预签名 PUT：ContentType 需与签名一致，先试 image/jpeg（.jpg）
        req = urllib.request.Request(put_url, data=PNG_BYTES, method="PUT",
                                     headers={"Content-Type": "image/jpeg"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read(2000).decode("utf-8", "replace")
            out["cos_put"] = {"status": r.status, "body": body[:200],
                              "etag": r.headers.get("ETag")}
        except urllib.error.HTTPError as e:
            out["cos_put"] = {"status": e.code,
                              "body": e.read(2000).decode("utf-8", "replace")[:400]}
        except Exception as e:
            out["cos_put"] = {"error": repr(e)}
        print("[B cos put]", out["cos_put"].get("status"), file=sys.stderr)
    else:
        out["cos_put"] = {"skipped": True}

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())