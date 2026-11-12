# so.qq.com 纯 Python 协议复现

> 面向协议学习与互操作性研究的**浏览器-free**参考实现（纯 Python 标准库 HTTP + `socket/ssl`）。
> 非官方项目，与腾讯、搜狗及其关联方无任何隶属、授权或背书关系。

**请先阅读 [DISCLAIMER.md](DISCLAIMER.md) 再使用本项目。**

| | |
|---|---|
| 许可证 | [MIT](LICENSE) |
| 免责声明 | [DISCLAIMER.md](DISCLAIMER.md) |
| 第三方归属 | [NOTICE.md](NOTICE.md) |
| 贡献指南 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 安全报告 | [SECURITY.md](SECURITY.md) |
| 完整分析 | [report.md](report.md)（已脱敏） |

---

## 这个项目是什么

把 `so.qq.com`（元宝搜索）的前端协议，还原成**不依赖浏览器运行时**的 Python 请求与解析代码：

- 签名门：`AES-256-CBC(MD5(data) + salt + ts)`，密钥 `SHA256(AUTH_TOKEN)`
- 会话接口：`session_list` / `session_list_page` / `session_get` / `session_delete`
- AI 流式问答：`query_get` 的 SSE（Server-Sent Events）POST
- 网页搜索：`/isearch` 的 RSC flight 内嵌 JSON 解码（含 tab 变体）
- 语音识别：手写 RFC6455 WebSocket 客户端
- 图片上传：multipart 与 COS 预签名 PUT
- 搜索建议：JSONP 回调解析
- 传输身份：可选的 `curl_cffi` 同 payload 对照

**不包含**：浏览器自动化、Playwright、Selenium、CDP、浏览器 profile、验证码绕过、批量采集、风控规避。

---

## 快速开始

需要 Python 3.10+（开发与验证环境为 3.14.5），无第三方必装依赖。

```bash
python3 main.py            # 自检 + 有界搜索探针
python3 collector.py       # 一次跑完全部能力（推荐）
python3 check_search.py    # 多关键词 / tab / 联想词搜索验收
python3 compare_parity.py  # Node 原生 crypto 交叉验证（需要 node）
```

可选：传输身份对照需要 `curl_cffi`

```bash
uv venv /tmp/skvenv
uv pip install --python /tmp/skvenv/bin/python curl_cffi
/tmp/skvenv/bin/python verify_transport.py
```

> 所有脚本均为**有界**运行：单次请求、有限重试、不并发、不写入目标站点业务数据（除显式说明的最小 1×1 PNG 上传与单条测试会话）。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `main.py` | AES/MD5/SHA256 签名核心、两套签名数据选择器、RSC flight 解码、自检、端点清单 |
| `collector.py` | 最终入口（PyCharm 右键可运行，无必需参数，stdout 为机器 JSON） |
| `replay_query.py` | `query_get` SSE 端到端 + `query_stop` |
| `state_chain.py` | 同一 `uid` 下 create → get → list → delete → 复核 |
| `verify_asr.py` | 纯 Python RFC6455 WebSocket 客户端 |
| `verify_transport.py` | `curl_cffi chrome124` ↔ 标准库同 payload 对照 |
| `verify_*.py` | 会话类 / 只读类 / multipart / 学术变体 / COS / 剩余项验收 |
| `parity.js` + `compare_parity.py` | Node ↔ Python 固定向量逐字段比对 |
| `check_search.py` | 搜索接口多关键词 + tab + 负对照 |
| `report.md` | 完整分析报告（IP / uuid / cuid / traceId 已占位符化） |

---

## 验证状态

| 门槛 | 结果 |
|---|---|
| 固定输入自检 | 10/10（含 NIST SP 800-38A AES-256-CBC 向量） |
| Node ↔ Python 签名 parity | 逐字段 MATCH |
| 浏览器真实 wire ↔ Python 金样本 | `sign` 逐字节 MATCH |
| 重复现网重放 | 会话 3/3、问答 3/3 |
| 状态链闭环 | create → get(`is_valid=true`) → list → delete → 复核(`false`) |
| ASR WebSocket | `101 Switching Protocols` → `asr.started / success` |
| 上传 / COS | `ret_code:0` / `200 + ETag` |
| 传输身份锁定 | `chrome124` 同 payload 与 stdlib 响应一致 |

> 「验证通过」仅表示上述有界请求在**验证当时**被接受；目标站点可随时变更接口、签名或风控策略，本项目不保证持续可用。

---

## 隐私与合规边界

- `AUTH_TOKEN_FALLBACK` 是目标站点**公开前端 JS** 中的固定回退常量，不是账号凭证；仓库不含登录 cookie、私钥、真实 token、用户数据。
- 不包含目标站点 JS bundle、SSR HTML 快照、HAR/抓包原始数据（版权与隐私原因）。
- 所有敏感标识（IP / uuid / cuid / traceId / 预签名 URL）在发布前已替换为占位符；`audit_public.py` 可复扫。
- 目标站点 `robots.txt` 为 `Disallow: /`。**使用前请自行取得必要授权并遵守服务条款与适用法律**，详见 [DISCLAIMER.md](DISCLAIMER.md)。

---

## 许可证

代码采用 [MIT License](LICENSE)。第三方材料与商标归属见 [NOTICE.md](NOTICE.md)。
许可证**不覆盖**目标站点的服务、内容、商标或可能适用的第三方权利；也不免除使用者的合规义务。