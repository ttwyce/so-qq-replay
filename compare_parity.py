# -*- coding: utf-8 -*-
"""Node 原生 crypto 与 main.py 纯 Python 实现的固定向量交叉验证。"""
import json
import subprocess
import sys

import main

SALT = "000102030405060708090a0b0c0d0e0f"
TS = 1739178536
QUERY = "天气"

node_out = subprocess.check_output(["node", "parity.js"], text=True).strip()
a = json.loads(node_out)
b = main.generate_auth_sign(QUERY, salt=bytes.fromhex(SALT), timestamp=TS)

print(json.dumps({
    "node": a,
    "python": b,
    "match": a == b,
    "salt_match": a["salt"] == b["salt"],
    "timestamp_match": a["timestamp"] == b["timestamp"],
    "sign_match": a["sign"] == b["sign"],
}, ensure_ascii=False, indent=2))
sys.exit(0 if a == b else 1)