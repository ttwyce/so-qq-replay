# so.qq.com 纯 Python 协议复现

> 本项目为协议逆向研究的教学/参考实现，浏览器-free（纯标准库 HTTP + socket/ssl）。

## 内容

- `main.py` — 纯 Python AES-256-CBC / MD5 / SHA256 签名核心、两套签名数据选择器、RSC flight 解码、自检
- `collector.py` — 最终入口（右键可运行，无必需参数）
- `replay_query.py` / `state_chain.py` — SSE 流式问答 / 同 uid 会话状态链
- `verify_asr.py` — 纯 Python RFC6455 WebSocket 客户端
- `verify_*.py` / `parity.js` / `compare_parity.py` — 各接口验收与独立实现交叉验证
- `check_search.py` — 多关键词 + tab 变体 + 联想词搜索验收
- `report.md` — 完整分析报告（已脱敏）

## 运行

```bash
python3 collector.py
python3 check_search.py
python3 compare_parity.py   # 需要 node
```

`verify_transport.py` 需要 `curl_cffi`（可选）：

```bash
uv venv /tmp/skvenv && uv pip install --python /tmp/skvenv/bin/python curl_cffi
/tmp/skvenv/bin/python verify_transport.py
```

## 说明

- `AUTH_TOKEN_FALLBACK` 是目标站点**公开前端 JS** 中的固定回退常量，不是账号凭证；
  仓库不含任何登录 cookie、私钥、真实 token 或用户数据。
- 不包含目标站点 JS bundle、SSR HTML 快照或抓包原始数据（版权与隐私原因）；
  报告中的 IP / uuid / cuid / traceId 均已替换为占位符。
- 所有验收均为**有界只读**请求；不含验证码绕过、批量采集或风控规避逻辑。
- 使用前请遵守目标站点的服务条款与 robots.txt，并自行承担合规责任。

## 状态

`collector` 交付门已闭合：自检 10/10、Node ↔ Python parity、浏览器金样本 ↔ Python
逐字节 MATCH、会话 3/3、问答 3/3、状态链闭环、ASR 握手、上传、COS、传输身份锁定。
