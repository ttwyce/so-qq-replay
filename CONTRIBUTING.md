# 贡献指南 / CONTRIBUTING

感谢你考虑参与。请先阅读 [DISCLAIMER.md](DISCLAIMER.md) 与 [NOTICE.md](NOTICE.md)。

## 允许贡献什么

✅ 欢迎：

- 修复 Python 语法、边界条件、解析健壮性、可读性与文档错误；
- 增加**不扩大请求范围**的固定向量、负对照与自检；
- 改进脱敏、审计脚本（`audit_public.py`）与发布流程；
- 澄清协议结构、状态分类、交付门等分析性描述；
- 补充 `LICENSE` / `DISCLAIMER` / `NOTICE` / `SECURITY` 的措辞建议。

❌ 请勿提交：

- 任何真实 cookie、token、账号、私钥、IP、uuid、cuid、traceId、HAR / 抓包原文；
- 目标站点 JS bundle、SSR HTML 快照、页面内容、生成式回答或预签名 URL；
- 验证码/风控绕过、反检测、指纹伪装规避、批量抓取、并发压测、重试放大逻辑；
- 未经书面授权的安全测试、漏洞利用或压力测试代码；
- 把「验证当时通过」改写为「生产可用 / 官方支持 / 保证稳定」的表述。

## 提交前自检

```bash
python3 -m py_compile *.py
python3 audit_public.py        # 输出应为零敏感命中
python3 compare_parity.py      # 需要 node
```

提交信息请说明：改了什么、为什么、是否改变请求范围。若涉及真实网络行为，
请注明是**有界只读**还是写入，并说明最小值。

## 隐私与合规

- 不要求、也不接受任何账号凭证来「复现问题」；请只用公开、脱敏的最小样本。
- 若发现仓库里存在疑似敏感信息或权利问题，**不要开公开 issue**，按
  [SECURITY.md](SECURITY.md) 私下报告。
- 贡献即表示你确认所提交内容为你有权提供，并同意在 `LICENSE`（MIT）下发布；
  同时理解 `DISCLAIMER.md` 的用途限制仍然独立适用。

## 行为准则

保持技术、克制、互相尊重；不讨论绕过、滥用或规避合规的具体做法。