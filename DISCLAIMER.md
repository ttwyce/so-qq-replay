# 免责声明 / Disclaimer

**请在使用本项目前完整阅读本文件。使用、复制、修改或运行本项目即表示你已理解并接受下述条款。**

## 1. 非官方、无授权、无背书

本项目是独立的协议学习与技术验证成果，**不是**腾讯、搜狗或其任何关联方的官方项目；
与上述主体不存在隶属、代理、授权、合作、赞助或背书关系。
项目名称与 `so.qq.com` 字样仅用于客观指代被研究的目标，不构成商标或品牌声明。

## 2. 用途限制

本项目仅用于：

- 学习 HTTP / TLS / SSE / WebSocket / RSC 等公开 Web 协议机制；
- 理解签名、会话、解码等常见前端协议结构；
- 在**你自己拥有或已获得明确书面授权**的系统上进行互操作性测试。

**禁止**将本项目或其衍生代码用于（包括但不限于）：

- 绕过访问控制、验证码、风控、速率限制、付费墙或任何保护机制；
- 规避 `robots.txt`、服务条款或法律要求；目标站点当前 `robots.txt` 为 `Disallow: /`；
- 批量抓取、爬取、转载、商业化利用目标站点内容或生成式回答；
- 访问、收集、存储、推断或披露任何个人信息、账号数据或第三方内容；
- 对目标站点造成异常负载、干扰、损害或安全测试（除非有书面授权）；
- 任何违反适用法律的用途（含著作权、计算机信息系统安全、数据保护、反不正当竞争等）。

## 3. 不保证可用、不保证持续

- 所有「验证通过」只代表**验证当时**若干个有界请求被接受；接口、签名、密钥、风控与响应结构可随时变更。
- 作者不承诺维护、更新、修复或提供兼容性适配，也不承诺任何形式的可用性、稳定性或准确性。
- 报告中的固定向量与端点是历史观测结果，**不得**当作长期协议契约或生产依赖。

## 4. 风险与责任

- 运行脚本会向第三方域名发起真实网络请求。你可能因此暴露 IP、User-Agent、时间、网络环境等信息；请自行评估。
- 本项目**不含**任何登录凭证、cookie、token 或用户数据。任何由使用者自行注入凭证、扩大请求范围、修改重试/并发策略所产生的后果，由使用者独自承担。
- 因使用、无法使用、误用本项目导致的账号限制、IP 封禁、数据损失、业务中断、合规调查、第三方索赔或任何直接与间接损失，作者与贡献者**不承担任何责任**。
- 使用者应自行判断并确保其行为符合目标站点服务条款、`robots.txt`、所在地法律以及所在组织的合规政策；必要时先取得书面授权或法律意见。

## 5. 内容与第三方权利

- 仓库不含目标站点 JS bundle、SSR HTML 快照、HAR/抓包原始数据。
- 报告中 IP / uuid / cuid / traceId / 预签名 URL 等标识均已替换为占位符；若你发现疑似遗漏，请按 `SECURITY.md` 私下报告，不要公开传播具体内容。
- 目标站点名称、接口路径、协议字段名等仅为事实性描述；相关商标、内容、服务及可能的著作权归各自权利人所有，见 `NOTICE.md`。

## 6. 无安全测试授权

本项目**不是**渗透测试工具，也不构成对任何系统发起安全测试、漏洞扫描或压力测试的授权。
任何此类行为必须另行取得目标方的明确书面许可。

## 7. 可分割性

若本声明某条款被认定无效或不可执行，其余条款继续有效；MIT 许可证（见 `LICENSE`）与本声明分别适用、互不扩张彼此授权范围。

---

## English summary (non-binding)

Unofficial, unaffiliated research artifact for learning public web protocol
mechanics only. No authorization, endorsement, or warranty is provided. Do not
use it to bypass access controls, crawl at scale, violate `robots.txt` / ToS /
applicable law, collect personal data, or interfere with third-party services.
Contents were redacted before publication. All results are point-in-time and
may break at any moment. Users assume full legal and operational responsibility.
See `LICENSE` and `NOTICE.md` for scope boundaries.