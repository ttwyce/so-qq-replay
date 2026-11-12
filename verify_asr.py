# -*- coding: utf-8 -*-
"""
纯 Python RFC6455 WebSocket 客户端（最小实现，仅标准库）
验证 so.qq.com ASR 端点：wss://so.qq.com/iaimode/api/asr/ws

握手参数与前端一致：voice_id / uid / verify(JSON) / ext / gn
verify = generateAuthSign(uid)，签名数据固定 uid。
"""
from __future__ import annotations

import base64
import json
import os
import socket
import ssl
import struct
import sys
import urllib.parse
import uuid

import main
from replay_query import get_uid

HOST = "so.qq.com"
PORT = 443
PATH = "/iaimode/api/asr/ws"


def ws_url(uid: str) -> str:
    v = main.generate_auth_sign(uid)
    q = urllib.parse.urlencode({
        "voice_id": str(uuid.uuid4()),
        "uid": uid,
        "verify": json.dumps(v, separators=(",", ":")),
        "ext": "{}",
        "gn": "",
    })
    return "wss://" + HOST + PATH + "?" + q


def handshake(sock: ssl.SSLSocket, path_query: str, key: str) -> dict:
    req = (
        "GET " + path_query + " HTTP/1.1\r\n"
        "Host: " + HOST + "\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: " + key + "\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Origin: https://so.qq.com\r\n"
        "User-Agent: " + main.UA + "\r\n"
        "\r\n"
    )
    sock.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf and len(buf) < 16384:
        c = sock.recv(1)
        if not c:
            break
        buf += c
    head, _, rest = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = lines[0] if lines else ""
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return {"status": status, "headers": headers, "rest": rest}


def send_text(sock: ssl.SSLSocket, text: str) -> None:
    data = text.encode("utf-8")
    mask = os.urandom(4)
    n = len(data)
    out = bytearray([0x81])
    if n < 126:
        out.append(0x80 | n)
    elif n < 65536:
        out.append(0x80 | 126)
        out += struct.pack(">H", n)
    else:
        out.append(0x80 | 127)
        out += struct.pack(">Q", n)
    out += mask
    out += bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    sock.sendall(bytes(out))


def read_exact(sock: ssl.SSLSocket, n: int) -> bytes:
    out = b""
    while len(out) < n:
        c = sock.recv(n - len(out))
        if not c:
            raise EOFError("ws closed")
        out += c
    return out


def read_frame(sock: ssl.SSLSocket) -> dict:
    b1, b2 = read_exact(sock, 2)
    fin, opcode = b1 & 0x80, b1 & 0x0F
    masked, n = b2 & 0x80, b2 & 0x7F
    if n == 126:
        n = struct.unpack(">H", read_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack(">Q", read_exact(sock, 8))[0]
    mask = read_exact(sock, 4) if masked else None
    payload = read_exact(sock, n)
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return {"fin": bool(fin), "opcode": opcode, "len": n,
            "text": payload.decode("utf-8", "replace") if opcode == 1 else None,
            "close_code": struct.unpack(">H", payload[:2])[0]
            if opcode == 8 and n >= 2 else None}


def run() -> dict:
    uid = get_uid()
    url = ws_url(uid)
    q = urllib.parse.urlsplit(url)
    path_query = q.path + ("?" + q.query if q.query else "")
    key = base64.b64encode(os.urandom(16)).decode()

    ctx = ssl.create_default_context()
    raw = socket.create_connection((HOST, PORT), timeout=12)
    sock = ctx.wrap_socket(raw, server_hostname=HOST)
    sock.settimeout(12)
    out = {"uid": uid, "url_host": HOST, "path": PATH}

    try:
        hs = handshake(sock, path_query, key)
        out["http_status"] = hs["status"]
        out["upgrade"] = hs["headers"].get("upgrade")
        out["accept"] = hs["headers"].get("sec-websocket-accept")
        if "101" not in hs["status"]:
            out["error"] = "handshake failed"
            return out

        voice_id = dict(urllib.parse.parse_qsl(q.query)).get("voice_id")
        start = {"event": "asr.start", "voice_id": voice_id,
                 "audio": {"format": "pcm", "sample_rate": 16000, "channel": 1}}
        send_text(sock, json.dumps(start, ensure_ascii=False,
                                   separators=(",", ":")))
        out["sent"] = start

        frames = []
        for _ in range(3):
            try:
                f = read_frame(sock)
            except Exception as e:
                frames.append({"read_error": repr(e)})
                break
            frames.append({k: f[k] for k in ("opcode", "len", "text", "close_code")})
            if f["opcode"] in (1, 8):
                break
        out["frames"] = frames
        out["server_obj"] = None
        for f in frames:
            if f.get("text"):
                try:
                    out["server_obj"] = json.loads(f["text"])
                except Exception:
                    pass
                break
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return out


if __name__ == "__main__":
    result = run()
    print("[asr]", result.get("http_status"),
          (result.get("server_obj") or {}).get("event"), file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2))