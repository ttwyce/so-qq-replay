# -*- coding: utf-8 -*-
"""media_upload 最终验证：合法 1x1 PNG（base64 解码，避免手写 hex 出错）。"""
import base64
import json
import sys
import uuid
import urllib.request

import main
from replay_query import get_uid

# 标准 1x1 透明 PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)
URL = "https://lizhiassistant.search.qq.com/aimode/media_upload"


def upload(filename: str, content_type: str) -> dict:
    uid = get_uid()
    v = main.generate_auth_sign(uid)
    b = "----soqq" + uuid.uuid4().hex

    def fld(k, val):
        return ("--" + b + "\r\n"
                + 'Content-Disposition: form-data; name="' + k + '"\r\n\r\n'
                + val + "\r\n").encode()

    head = ("--" + b + "\r\n"
            'Content-Disposition: form-data; name="file"; filename="'
            + filename + '"\r\n'
            + "Content-Type: " + content_type + "\r\n\r\n").encode()
    body = (head + PNG + b"\r\n"
            + fld("uid", uid)
            + fld("verify", json.dumps(v, separators=(",", ":")))
            + fld("media_type", "image")
            + fld("trace_id", str(uuid.uuid4()))
            + ("--" + b + "--\r\n").encode())
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "multipart/form-data; boundary=" + b,
        "User-Agent": main.UA,
        "Origin": "https://so.qq.com", "Referer": "https://so.qq.com/",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return {"status": r.status, "png_bytes": len(PNG),
                    "resp": r.read().decode("utf-8", "replace")[:600]}
    except Exception as e:
        return {"png_bytes": len(PNG), "error": repr(e)}


if __name__ == "__main__":
    out = upload("pixel.png", "image/png")
    print("[upload]", out.get("status") or out.get("error"), file=sys.stderr)
    print(json.dumps(out, ensure_ascii=False, indent=2))