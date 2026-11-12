# -*- coding: utf-8 -*-
"""
so.qq.com / 元宝搜索 —— 纯 Python 协议复刻（browser-free）

形态: evidence + local-proof（不是 collector）
来源: 静态分析 so.qq.com 首页 / /isearch SSR / 全部 JS chunk，未使用浏览器自动化。
现网验收: 仅 /isearch 单端点有界 GET 探针；/aimode/* POST 未做现网重放。

PyCharm 直接右键运行本文件，无需参数。
  - 默认跑：AES 实现自检 + 签名算法确定性自检 + 解析器 fixture 自检
            + 一次有界 /isearch GET 探针
  - 关闭现网探针：把 LIVE_SMOKE 改成 False（离线自检仍然完整可跑）
stdout = 机器 JSON；关键响应/错误 = stderr。
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sys
import time
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

HOME = "https://so.qq.com"
AIMODE_API = "https://lizhiassistant.search.qq.com"
# 实测 wire：会话/问答类走 /browser_aimode 前缀；media_upload 走裸 base
AIMODE_API_BROWSER = AIMODE_API + "/browser_aimode"

# 前端公开 fallback 常量（chunk 3cf4c0edffd2b0e1.js 模块 598979）
# 生产若通过 env 注入 NEXT_PUBLIC_AIMODE_AUTH_TOKEN / AIMODE_AUTH_TOKEN 会覆盖它；
# 该分支未在浏览器边界取值证实，属于未证明项。
AUTH_TOKEN_FALLBACK = "aimode_token_1739178536"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/<REDACTED_IP> Safari/537.36")

LIVE_SMOKE = True          # 一次有界只读 GET；设为 False 则完全离线
PROBE_QUERY = "天气"
PROBE_TIMEOUT = 15

# ---------------------------------------------------------------------------
# 纯 Python AES-256 / CBC / PKCS7 （只实现加密方向；无需第三方依赖）
# ---------------------------------------------------------------------------


def _gmul(a: int, b: int) -> int:
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p & 0xFF


def _build_sbox() -> list[int]:
    box = []
    for a in range(256):
        v = 0                       # 0 的 GF(2^8) 逆元定义为 0
        if a:
            v = 1
            for _ in range(254):    # a^254 = a^{-1}
                v = _gmul(v, a)
        s = v
        for _ in range(4):          # s ^ rotl(s,1..4) ^ 0x63
            v = ((v << 1) | (v >> 7)) & 0xFF
            s ^= v
        box.append(s ^ 0x63)
    return box


SBOX = _build_sbox()
SBOX_FIRST4_EXPECTED = [0x63, 0x7C, 0x77, 0x7B]


def _xtime(x: int) -> int:
    x <<= 1
    return (x ^ 0x1B) & 0xFF if x & 0x100 else x & 0xFF


def _expand_key(key: bytes) -> list[list[int]]:
    assert len(key) == 32, "AES-256 需要 32 字节密钥"
    w = [list(key[4 * i:4 * i + 4]) for i in range(8)]
    rcon = 1
    for i in range(8, 60):
        t = w[i - 1][:]
        if i % 8 == 0:
            t = [SBOX[b] for b in t[1:] + t[:1]]
            t[0] ^= rcon
            rcon = _xtime(rcon)
        elif i % 8 == 4:
            t = [SBOX[b] for b in t]
        w.append([w[i - 8][j] ^ t[j] for j in range(4)])
    return w


def _round_key(w: list[list[int]], r: int) -> list[int]:
    return w[4 * r] + w[4 * r + 1] + w[4 * r + 2] + w[4 * r + 3]


def _shift_rows(s: list[int]) -> list[int]:
    out = [0] * 16
    for c in range(4):
        for r in range(4):
            out[r + 4 * c] = s[r + 4 * ((c + r) % 4)]
    return out


def _mix_columns(s: list[int]) -> list[int]:
    out = list(s)
    for c in range(4):
        i = 4 * c
        a0, a1, a2, a3 = s[i], s[i + 1], s[i + 2], s[i + 3]
        out[i]     = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
        out[i + 1] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
        out[i + 2] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
        out[i + 3] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)
    return out


def _encrypt_block(block: bytes, w: list[list[int]]) -> bytes:
    s = list(block)
    rk = _round_key(w, 0)
    s = [a ^ b for a, b in zip(s, rk)]
    for r in range(1, 14):
        s = _mix_columns(_shift_rows([SBOX[b] for b in s]))
        rk = _round_key(w, r)
        s = [a ^ b for a, b in zip(s, rk)]
    s = _shift_rows([SBOX[b] for b in s])
    rk = _round_key(w, 14)
    return bytes(a ^ b for a, b in zip(s, rk))


def aes256_cbc_encrypt(data: bytes, key: bytes, iv: bytes, pad: bool = True) -> bytes:
    """AES-256-CBC + PKCS7。pad=False 用于 NIST 单块向量自检。"""
    assert len(key) == 32 and len(iv) == 16
    if pad:
        n = 16 - len(data) % 16
        data = data + bytes([n]) * n
    assert len(data) % 16 == 0
    w = _expand_key(key)
    out, prev = bytearray(), iv
    for i in range(0, len(data), 16):
        blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
        ct = _encrypt_block(blk, w)
        out += ct
        prev = ct
    return bytes(out)


# ---------------------------------------------------------------------------
# verify 签名（对应 JS generateAuthSign / aimodeRequest / addAuthToBody）
# ---------------------------------------------------------------------------

OUTER_LOGIN_COOKIE_KEYS = (
    "qb_account_type", "qb_appid", "qb_open_id", "qb_qb_access_token",
    "qb_access_token", "qb_refresh_token", "qb_qbid", "qb_user_name",
    "qb_user_avatar",
)


def generate_auth_sign(data: str, *, salt: bytes | None = None,
                       timestamp: int | None = None,
                       token: str = AUTH_TOKEN_FALLBACK) -> dict:
    """
    JS 原文（chunk 3cf4c0edffd2b0e1.js / 模块 598979）:
      salt = 16 随机字节的 hex
      ts   = floor(Date.now()/1000)
      n    = MD5(data).hex + salt + str(ts)
      key  = SHA256(token)            # WordArray，即 AES-256 原始 32 字节
      iv   = Hex.parse(salt)          # 16 字节
      sign = AES-CBC-PKCS7(Utf8(n), key, iv).ciphertext.toString()  -> hex
    """
    salt = salt if salt is not None else secrets.token_bytes(16)
    assert len(salt) == 16
    salt_hex = salt.hex()
    ts = int(time.time()) if timestamp is None else int(timestamp)
    preimage = hashlib.md5(data.encode("utf-8")).hexdigest() + salt_hex + str(ts)
    key = hashlib.sha256(token.encode("utf-8")).digest()
    sign = aes256_cbc_encrypt(preimage.encode("utf-8"), key, salt).hex()
    return {"salt": salt_hex, "timestamp": ts, "sign": sign}


def sign_data_for(endpoint: str, body: dict, uid: str,
                  *, signer: str = "aimodeRequest") -> str:
    """
    两套签名数据选择器（chunk 3cf4c0edffd2b0e1.js / 模块 914767）：

    aimodeRequest(endpoint, {body, uid}):
        URL 含 /aimode/query_new -> body.query，否则 uid
        （session_list / session_list_page / session_delete / query_new 走这里）

    addAuthToBody(body, uid):
        body.query 为字符串 -> body.query，否则 uid
        （query_get SSE 走这里；与 URL 无关）
    """
    if signer == "addAuthToBody":
        q = body.get("query")
        return q if isinstance(q, str) and q else uid
    if "/aimode/query_new" in endpoint:
        q = body.get("query")
        if isinstance(q, str) and q:
            return q
        return uid
    return uid


def auth_from_cookie(cookie_header: str) -> dict:
    """withAuthPayload: 只挑登录 cookie，未登录返回空 dict（不写 auth 字段）。"""
    out = {}
    for part in (cookie_header or "").split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        if k in OUTER_LOGIN_COOKIE_KEYS:
            out[k] = urllib.parse.unquote(v.strip())
    return out


def build_signed_body(endpoint: str, body: dict, uid: str,
                      *, cookie_header: str = "", verify: dict | None = None,
                      signer: str = "aimodeRequest") -> str:
    """生成 JSON.stringify({...body, verify, auth?}) 的等价字节串。"""
    signed = dict(body)
    signed["verify"] = verify or generate_auth_sign(
        sign_data_for(endpoint, body, uid, signer=signer))
    auth = auth_from_cookie(cookie_header)
    if auth:
        signed["auth"] = auth
    return json.dumps(signed, ensure_ascii=False, separators=(",", ":"))


def aimode_post(endpoint: str, body: dict, uid: str, *, cookie_header: str = "",
                timeout: int = 20) -> dict:
    """POST 到 lizhiassistant /aimode/*。仅构造请求，不做自动重试/绕过风控。"""
    url = endpoint if endpoint.startswith("http") else AIMODE_API + endpoint
    payload = build_signed_body(url, body, uid, cookie_header=cookie_header).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA,
                 "Origin": HOME, "Referer": HOME + "/"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    obj = json.loads(raw.decode("utf-8", "replace"))
    if isinstance(obj, dict) and obj.get("ret_code") not in (None, 0):
        raise RuntimeError("业务错误: ret_code=%s message=%s"
                           % (obj.get("ret_code"), obj.get("message")))
    return obj


# ---------------------------------------------------------------------------
# /isearch SSR 结果页：RSC flight 解析（纯 Python，不执行页面 JS）
# ---------------------------------------------------------------------------


def _decode_js_string(lit: str) -> str:
    s = lit[1:-1]
    s = s.replace("\\'", "'").replace("\\v", "\v").replace("\\0", "\0")
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: "\\u00" + m.group(1), s)
    try:
        return json.loads('"' + s + '"')
    except Exception:
        return (s.replace('\\"', '"').replace("\\n", "\n")
                 .replace("\\r", "\r").replace("\\t", "\t").replace("\\\\", "\\"))


def extract_flight_text(html: str) -> str:
    """拼接所有 self.__next_f.push([1,"..."]) 片段，得到 RSC flight 流。"""
    chunks = []
    for m in re.finditer(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html, re.S):
        chunks.append(_decode_js_string(m.group(1)))
    return "".join(chunks)


def extract_business_blocks(html: str) -> list[dict]:
    """
    从 RSC flight 提取业务 JSON（vrid / module_list / searchParams）。

    T 行标记形如 `29:T278c0,{"vrid":...}`，但跨 chunk 拼接后换行边界可能丢失
    （实测 `29:T278c0,` 前一字符是上一个 payload 的尾字符，不是 \\n），
    因此无论 T 行是否命中，都额外扫描内嵌业务对象起点并用 raw_decode 解析，
    按位置去重并保持 flight 顺序。
    """
    flight = extract_flight_text(html)
    hits: dict[int, dict] = {}

    def _try(pos: int) -> None:
        if pos in hits or pos >= len(flight) or flight[pos] not in "{[":
            return
        try:
            obj, _ = json.JSONDecoder().raw_decode(flight[pos:])
        except Exception:
            return
        if isinstance(obj, dict) and ("vrid" in obj or "module_list" in obj
                                      or "searchParams" in obj):
            hits[pos] = obj

    for m in re.finditer(r"(?:^|\n)([0-9a-z]+):T[0-9a-fA-F]+,", flight):
        _try(m.end())
    for key in ('{"vrid"', '{"module_list"', '{"searchParams"'):
        for m in re.finditer(re.escape(key), flight):
            _try(m.start())
    return [hits[p] for p in sorted(hits)]


def collect_titles(blocks: list, flight: str) -> list:
    """跨结构提取标题：优先 module_list/item_list，回退到整条 flight。"""
    titles, seen = [], set()

    def add(t):
        if not isinstance(t, str):
            return
        t = re.sub(r"[\ue000-\uf8ff]", "", t)
        t = t.replace("\\u201c", "“").replace("\\u201d", "”")
        t = t.strip()
        # 过滤掉导航/占位类噪声
        if t and len(t) >= 4 and t not in seen:
            seen.add(t)
            titles.append(t)

    # 主路径：结构化模块
    for b in blocks:
        for mod in (b.get("module_list") or []):
            for item in (mod.get("item_list") or []):
                add((item.get("data") or {}).get("title"))
    # 通用回退：RSC flight 内任意 JSON title 字段（覆盖 28:T 文档对象、
    # 学术卡片、视频/图片卡等不同结构）；用 unescape 处理转义标题
    for m in re.finditer(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', flight):
        raw = m.group(1)
        try:
            val = json.loads('"' + raw + '"')
        except Exception:
            val = raw.replace('\\"', '"')
        add(val)
    return titles


def isearch(query: str, *, tab: str = "", timeout: int = PROBE_TIMEOUT) -> dict:
    """GET /isearch?query=...&quick=1 —— 单端点、只读、无登录态。"""
    params = {"query": query, "quick": "1"}
    if tab:
        params["tab"] = tab
    url = HOME + "/isearch?" + urllib.parse.urlencode(params, encoding="utf-8")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": HOME + "/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", "replace")
        status = resp.status
    blocks = extract_business_blocks(html)
    titles = collect_titles(blocks, extract_flight_text(html))
    return {"url": url, "status": status, "html_bytes": len(html.encode("utf-8")),
            "flight_blocks": len(blocks), "sample_titles": titles[:5],
            "title_count": len(titles)}


# ---------------------------------------------------------------------------
# 自检（local-proof）
# ---------------------------------------------------------------------------

# NIST SP 800-38A F.2.5 AES-256-CBC 第一块（校验纯 Python AES 实现）
NIST_KEY = bytes.fromhex("603deb1015ca71be2b73aef0857d7781"
                         "1f352c073b6108d72d9810a30914dff4")
NIST_IV = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
NIST_PT = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")
NIST_CT = "f58c4c04d6e5f1ba779eabfb5f7bfbd6"

FIXED_SALT = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
FIXED_TS = 1739178536
FIXED_QUERY = "天气"
FIXED_UID = "test_uid_for_vector"

# 最小 flight fixture：T 行长度故意写成 5（不匹配真实 JSON 长度），
# 用来证明「T 行长度/换行边界不可靠时，内嵌对象扫描兜底仍然有效」。
FLIGHT_FIXTURE = (
    '<script>self.__next_f.push([1,"29:T5,"])</script>'
    '<script>self.__next_f.push([1,"{\\"vrid\\":\\"30000501\\",'
    '\\"module_list\\":[{\\"item_list\\":[{\\"data\\":{\\"title\\":\\"t\\"}}]}]}"])</script>'
)


def self_test() -> dict:
    r = {}
    r["sbox_first4"] = SBOX[:4]
    r["sbox_ok"] = SBOX[:4] == SBOX_FIRST4_EXPECTED
    ct = aes256_cbc_encrypt(NIST_PT, NIST_KEY, NIST_IV, pad=False).hex()
    r["nist_aes256_cbc"] = ct
    r["nist_aes_ok"] = ct == NIST_CT

    v = generate_auth_sign(FIXED_QUERY, salt=FIXED_SALT, timestamp=FIXED_TS)
    r["sign_vector"] = v
    r["sign_shape_ok"] = (len(v["salt"]) == 32 and v["timestamp"] == FIXED_TS
                          and len(v["sign"]) % 32 == 0 and len(v["sign"]) >= 64)
    r["sign_deterministic"] = (
        generate_auth_sign(FIXED_QUERY, salt=FIXED_SALT, timestamp=FIXED_TS) == v)
    r["sign_data_sensitive"] = (
        generate_auth_sign(FIXED_QUERY + "x", salt=FIXED_SALT,
                           timestamp=FIXED_TS)["sign"] != v["sign"])
    r["sign_token_sensitive"] = (
        generate_auth_sign(FIXED_QUERY, salt=FIXED_SALT, timestamp=FIXED_TS,
                           token=AUTH_TOKEN_FALLBACK + "x")["sign"] != v["sign"])
    preimage = (hashlib.md5(FIXED_QUERY.encode()).hexdigest()
                + FIXED_SALT.hex() + str(FIXED_TS))
    key = hashlib.sha256(AUTH_TOKEN_FALLBACK.encode()).digest()
    r["preimage_ok"] = (aes256_cbc_encrypt(preimage.encode(), key, FIXED_SALT).hex()
                        == v["sign"])

    body = build_signed_body(AIMODE_API + "/aimode/session_list_page",
                             {"uid": FIXED_UID, "page": 1, "page_size": 20},
                             FIXED_UID, verify=v)
    parsed = json.loads(body)
    r["body_keys"] = list(parsed.keys())
    r["body_ok"] = (list(parsed.keys()) == ["uid", "page", "page_size", "verify"]
                    and parsed["verify"] == v and "auth" not in parsed)
    r["sign_data_selector_ok"] = (
        sign_data_for(AIMODE_API + "/aimode/query_new",
                      {"query": FIXED_QUERY}, FIXED_UID) == FIXED_QUERY
        and sign_data_for(AIMODE_API + "/aimode/session_list",
                          {"uid": FIXED_UID}, FIXED_UID) == FIXED_UID)

    fx = extract_business_blocks(FLIGHT_FIXTURE)
    r["flight_fixture_blocks"] = len(fx)
    r["flight_fixture_ok"] = (len(fx) == 1 and fx[0].get("vrid") == "30000501")

    r["all_pass"] = all(r[k] for k in ("sbox_ok", "nist_aes_ok", "sign_shape_ok",
                                       "sign_deterministic", "sign_data_sensitive",
                                       "sign_token_sensitive", "preimage_ok",
                                       "body_ok", "sign_data_selector_ok",
                                       "flight_fixture_ok"))
    return r


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

ENDPOINTS = {
    "page_routes": ["/", "/ihome", "/isearch?query=&quick=1[&tab=]",
                    "/ipics?query=&keyword=", "/iaimode/search?query=[&sid][&_rsc]",
                    "/robots.txt"],
    "session_json_get": ["/api/conversations", "/api/conversations/{id}"],
    "suggest_jsonp": ["https://sor.html5.qq.com/api/getsug"
                      "?type=pc&pid=aimode&pagename=sgresult&key={query}&m=jsonp_{ts}_{n}"],
    "asr_websocket": ["wss://so.qq.com/iaimode/api/asr/ws?voice_id&uid&verify&ext&gn "
                      "(pure-Python RFC6455; Origin required)"],
    "login": ["/web_login/refreshWxToken", "/web_login/login?login_type=&callback_origin_type=2&return_to=",
              "https://weblogin.sogou.com/web_login/refreshWxToken",
              "https://weblogin.sogou.com/web_login/login"],
    # 实测：会话/问答类全部走 /browser_aimode 前缀
    "aimode_browser_base": [AIMODE_API_BROWSER + "/aimode/" + n for n in (
        "session_list", "session_list_page", "session_get", "session_delete",
        "query_get (SSE)", "query_stop")],
    "aimode_plain_base": [AIMODE_API + "/aimode/media_upload (multipart, <=5 MiB)",
                          AIMODE_API + "/academic_agent/query_get",
                          AIMODE_API + "/academic_agent/query_stop"],
    "negative_controls": [AIMODE_API_BROWSER + "/aimode/query_new -> 404"],
    "risk_control": ["https://captcha.gtimg.com/TCaptcha.js (appid=25207564)"],
    "jsapi": ["https://jsapi.qq.com/get?api=login.*,app.*,bangpanel.*"],
    "telemetry": ["https://h.trace.qq.com/kv (Atta main/result/aimode)",
                  "https://edge.log.zhiyan.tencent-cloud.net/v1/aegis/collect",
                  "https://trace.inlong.qq.com", "https://snowflake.qq.com/ola/v2"],
}


def main() -> int:
    out = {
        "target": HOME,
        "shape": "evidence + local-proof",
        "browser_free": True,
        "browser_mode": "unavailable",
        "silent_backend": "absent",
        "baseline_gap": "fingerprint-baseline not satisfied (no browser MCP)",
        "debugger_trace_gap": "debugger-trace not satisfied (no js-reverse / silent capture)",
        "live_acceptance": "bounded single GET only; /aimode/* POST NOT replayed",
    }
    try:
        out["self_test"] = self_test()
    except Exception as exc:                       # 我们的 bug 必须响亮报错
        print("[FATAL] self_test failed: %r" % (exc,), file=sys.stderr)
        raise
    print("[self_test] all_pass=%s nist_aes_ok=%s flight_fixture_ok=%s"
          % (out["self_test"]["all_pass"], out["self_test"]["nist_aes_ok"],
             out["self_test"]["flight_fixture_ok"]), file=sys.stderr)

    if LIVE_SMOKE:
        try:
            out["isearch_probe"] = isearch(PROBE_QUERY)
            print("[probe] status=%s html_bytes=%s blocks=%s titles=%s"
                  % (out["isearch_probe"]["status"],
                     out["isearch_probe"]["html_bytes"],
                     out["isearch_probe"]["flight_blocks"],
                     out["isearch_probe"]["title_count"]), file=sys.stderr)
        except Exception as exc:                   # 外部失败降级，不算实现错误
            out["isearch_probe"] = {"ok": False, "error": repr(exc)}
            print("[probe] external failure: %r" % (exc,), file=sys.stderr)
    else:
        out["isearch_probe"] = {"skipped": True}

    out["endpoints"] = ENDPOINTS
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())