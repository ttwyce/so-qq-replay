# so.qq.com 接口全量分析与纯 Python 复现（最终报告 · v4）

> 技能 `spider-king` ｜ 形态：**`collector`（browser-free）**
> 工作区 `/operitapp/workspaces/元宝搜索/` ｜ 交付目录 `so_qq_evidence/`

---

## 0. 结论

**所有已发现、且在当前环境可现网复现的接口，均已用纯 Python 复现并通过现网验收。** `collector.py` 右键运行一次全绿（EXIT=0）。

剩余 4 项不是「没复现」，而是**服务端自身故障 / 有意不复刻 / 环境凭证不可得 / 判定为死路由**：

| 项 | 定性 | 证据 |
|---|---|---|
| `anti_crawl: verify\|reject` | risk-interactive，技能禁止把验证码平台放进采集运行时 | 所有真实请求首帧均为 `status:"pass"` |
| `academic_agent/query_stop` | **服务端变体故障** | 带签名/不带签名都 500 且空 body；browser 版同样参数 `ret_code:0` |
| 真实登录态 `auth` | 环境无 QB/微信凭证 | 已用受控假 cookie 验证字段拼接，服务端 `ret_code:0` |
| `query_new` | 死路由 | 两个已测前缀均 404；真实链路是 `query_get` |

---

## 1. Startup Gate（最终）

| 项 | 判定 |
|---|---|
| Intake | `continuation`（同目标，能力面变化后刷新） |
| 浏览器 | `browser` 包（Playwright MCP 风格），**`launch`** 单 host |
| `fingerprint-baseline` | ✅ 首页 wire + cookie/UA/storage 快照（实测 `Chrome/<REDACTED_IP>`，`webdriver=false`） |
| `debugger-trace` | ✅ 同 host 真实 wire + 源码关联 + 金样本固定向量 |
| 终端 | ✅ `super_admin:bash`（Python 3.14.5 / Node 24.18.1 / `uv`） |
| **curl impersonate** | ✅ 已装 `curl_cffi 0.17.0`（`/tmp/skvenv`），`max=chrome152`；**锁定 `chrome124`** 以匹配实测浏览器基线（不把更高 major 拷到更低 impersonate） |
| 交付形态 | `collector` |

---

## 2. 决定性证据链

1. 基线 wire：`POST /browser_aimode/aimode/session_list_page` → 200
2. 裸 body 负对照：`{"ret_code":-1,"message":"authentication failed"}` → 签名门存在
3. 金样本（点击历史记录）：
```json
{"uid":"cuid_<REDACTED>","page":1,"page_size":20,
 "verify":{"salt":"816a0cc5…","timestamp":1794405940,"sign":"c5d811f1…e98"}} → ret_code:0
```
4. Python 同输入重算 `sign` **逐字节 MATCH** → `AUTH_TOKEN = aimode_token_1739178536`（env 未覆盖）
5. 纯 Python 会话重放 3/3、AI 问答 3/3、状态链闭环、ASR 握手、COS 上传、传输 parity 全部通过

---

## 3. 签名协议

```
salt = 16 随机字节 hex(32)
ts   = floor(now/1000)          # 必须当前时间；历史 ts 会被判 authentication failed
n    = MD5(data).hex + salt + str(ts)
key  = SHA256(AUTH_TOKEN).digest()
iv   = bytes.fromhex(salt)
sign = AES-256-CBC-PKCS7(UTF8(n), key, iv).hex()
```

**三套 data 选择器**：

| 路径 | 调用 | data |
|---|---|---|
| `session_*` / `query_new` | `aimodeRequest` | URL 含 `query_new` → `body.query`，否则 `uid` |
| `query_get` SSE | `addAuthToBody` | **`body.query` 优先**（与 URL 无关），否则 `uid` |
| `media_upload` / ASR WSS | `generateAuthSign(uid)` | 固定 `uid` |

`auth` 仅在 `qb_*` cookie 存在时附加；`uid = "cuid_" + <首页 RSC flight 下发的 cuid>`，每次请求不同，同 session chain 内取一次即用。

---

## 4. 接口复现总表

| 接口 | 方法 | Python | 现网结果 |
|---|---|---|---|
| `/` `/ihome` `/robots.txt` | GET | ✅ | 200 |
| `/isearch?query=&quick=1[&tab=]` | GET | ✅ | 200；通用解码：`天气` 38 / `Python 教程` 33 / `腾讯 2026 财报` 16 条；tab：`xueshu` 3、`weixin_article` 9、`weixin_video` 55、`media` 16；空 query 负对照 0 条 |
| `/iaimode/search?...&_rsc=` | GET | ✅ | 200 `text/x-component` |
| `sor.html5.qq.com/api/getsug` JSONP | GET | ✅ | 200 联想词数组 |
| `/web_login/refreshWxToken` | GET | ✅ | `{"code":-1,...}` |
| `/api/conversations[/{id}]` | GET | ✅ | 200 HTML fallback |
| `session_list` / `session_list_page` | POST | ✅ | `ret_code:0` |
| `session_get` | POST | ✅ | 创建后 `is_valid:true / 1 query` |
| `session_delete` | POST | ✅ | 真删 `ret_code:0`，复核 `is_valid:false` |
| **`query_get` SSE** | POST | ✅ | `200 text/event-stream`，完整 AI 答案 + `query_id` |
| `query_get` 重生（`query_id=2`） | POST | ✅ | 200，219 帧 / 41KB |
| **`academic_agent/query_get`** | POST | ✅ | 200 SSE，45 帧 / 24KB |
| `query_stop`（browser 版） | POST | ✅ | `ret_code:0 success` |
| **`media_upload`** | POST multipart | ✅ | `ret_code:0`，CDN URL / `trace_id` |
| **`kbqa.../learning_agent/media/upload_url`** | POST | ✅ | `code:0`，预签名 COS URL + `file_id` |
| **COS 预签名 PUT** | PUT | ✅ | 200 + ETag |
| **ASR WebSocket** | WSS | ✅ | 纯 Python RFC6455 `101` → `asr.started / success` |
| 会话状态链闭环 | 组合 | ✅ | create → get → list → delete → 复核 |
| 裸 base `session_list` | POST | ✅ | `ret_code:0`（两个前缀都可用） |
| **传输身份锁定** | HTTP/2 | ✅ | `curl_cffi chrome124` 与 stdlib 同 payload 响应一致 |
| `academic_agent/query_stop` | POST | ❌ 服务端 500 | 带/不带签名都 500；非我方实现问题 |
| `query_new`（两个前缀） | POST | ✅ 负对照 | 404 死路由 |
| Atta / Aegis / snowflake 上报 | POST | ✅ 可达 | 只读探测 |

---

## 5. 关键修正史

| 早期结论 | 实测修正 |
|---|---|
| base = `/aimode/*` | `/browser_aimode/aimode/*`；裸 base 亦可用；`media_upload` 例外 |
| `uid` 未定 | `cuid_` + 首页 RSC `cuid` |
| `AUTH_TOKEN` env 可能覆盖 | 未覆盖（金样本 parity 证明） |
| 所有签名数据 = `uid` | `addAuthToBody` 用 `query`；否则 `authentication failed` |
| 主业务 = `query_new` | `query_get`（SSE POST）；`query_new` 404 |
| 页面 fetch hook 可抓 wire | 模块闭包持有原始 fetch → 用「页面自身触发 + network_requests + 金样本」 |
| ASR 不可用 | 缺 `Origin` 头 / 假 verify；真实 verify + `Origin` → 101 |
| `curl_cffi` 缺失 | 系统 Python 被 apk 保护 → `uv venv /tmp/skvenv` 安装；锁定 chrome124 |
| `固定历史 ts 可用于 parity` | 会被判 `authentication failed`；必须用当前 ts |
| `isearch` 只解析 `vrid/module_list` | 其他关键词把结果放在 `28:T` 文档对象 / 学术卡片等结构里 → 新增 `collect_titles()` 通用 flight 回退（任意 JSON `title` 字段，含高亮标记清洗） |

---

## 6. 交付文件

| 文件 | 职责 |
|---|---|
| **`collector.py`** | ⭐ 最终入口：右键可跑、无参数、一次跑完自检 + 会话类 + AI SSE + 状态链 + ASR + 上传 + kbqa/COS + 只读端点 |
| `main.py` | 纯 Python AES/签名核心、三套 data 选择器、RSC flight 解码、自检、端点清单 |
| `replay_query.py` / `state_chain.py` | SSE 端到端 / 同 uid 会话状态链闭环 |
| `verify_asr.py` | 纯 Python RFC6455 WebSocket 客户端 |
| `verify_transport.py` | curl_cffi chrome124 ↔ stdlib 同 payload 传输 parity（需 `/tmp/skvenv/bin/python`） |
| `verify_remaining2.py` | kbqa upload_url → COS PUT、academic_stop 定性 |
| `verify_variants.py` / `verify_all.py` / `verify_other.py` / `verify_upload2.py` | 学术/重生/裸 base、签名类、只读类、multipart 验收 |
| `parity.js` / `compare_parity.py` | Node ↔ Python 固定向量交叉验证 |
| `chunks/` | 41 个 JS chunk + 签名模块 Range 切片 |
| `isearch*.html` / `index.html` | SSR 样本与负对照 |

---

## 7. 交付门判定

| 门槛 | 状态 |
|---|---|
| Startup Gate 当前 | ✅ |
| `fingerprint-baseline` / `debugger-trace` | ✅ 单 host 完成 |
| 真实请求 / 规范篡改点 / 变化状态 | ✅ |
| 固定输入自检 | ✅ 10/10（含 NIST AES 向量） |
| Node ↔ Python parity / 浏览器金样本 ↔ Python | ✅ MATCH |
| 重复现网重放 | ✅ 会话 3/3、问答 3/3、状态链、ASR、上传、COS、采集器整跑 |
| **传输身份锁定** | ✅ chrome124 同 payload parity |
| 浏览器-free 最终路径 | ✅ 纯 `urllib` + `socket/ssl`；无 Playwright/CDP/profile/JS runtime |
| PyCharm 右键入口 | ✅ `collector.py` 无必需参数 |
| 敏感值 | ✅ 无真实 cookie/token 外泄 |

**`collector` 门闭合。**

---

## 8. 最小下一步（如需继续）

按一次一个原则：若有真实登录环境，抓一次带 `auth` 的 `query_get` wire 与 `build_signed_body(cookie_header=...)` 比对。防水墙挑战需要真实风险触发条件，不建议主动制造；`academic_agent/query_stop` 属服务端故障，不是可复现缺口。