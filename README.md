# NEWS FINANCE V2

V2 将官方日程、公司披露、市场价格和媒体叙事组合成可审计的前瞻研究报告。预测会被冻结，并按 NYSE 交易日机械验证。

## Windows 安装

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
```

填写 `.env` 中的模型与密钥。SEC 深度扫描要求 `SEC_USER_AGENT` 包含真实联系邮箱。

实时模式会抓取官方与媒体页面、读取跨资产行情、调用配置的 AI，并在非预览模式下通过 SMTP 发信。建议先使用离线模式和 `--preview` 验证配置；只有不带 `--preview` 才会发送邮件。

## 命令

```powershell
.\.venv\Scripts\python.exe news_finance_v2.py --self-test
.\.venv\Scripts\python.exe news_finance_v2.py --preview
.\.venv\Scripts\python.exe news_finance_v2.py --preview --full
.\.venv\Scripts\python.exe news_finance_v2.py --verify
.\.venv\Scripts\python.exe -m pytest -q
```

离线演示不会访问网络、AI 或 SMTP：

```powershell
$env:NEWS_FINANCE_OFFLINE='1'
.\.venv\Scripts\python.exe news_finance_v2.py --preview
```

V2 使用 `data/news_finance_v2.db`，不会覆盖旧版数据库。

## 自动邮件与 GitHub Pages

`.github/workflows/daily-report.yml` 在每周一至周五纽约时间 09:00 触发，并使用 NYSE 日历二次检查。周末和美股休市日不会抓取数据、调用 AI 或发送邮件；手动运行不受交易日限制。

交易日任务会依次完成测试、恢复历史预测、验证到期结果、生成报告、SMTP 发信、更新 `docs/index.html` 与当日归档，并部署 GitHub Pages。预测数据库保存在 GitHub Actions 缓存中，不提交进公开仓库。GitHub 定时任务可能因平台负载略有延迟。

仓库需配置以下 GitHub Actions Secrets：

- `OPENAI_API_KEY`
- `SEC_USER_AGENT`
- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_TO`

可选仓库 Variables：`AI_MODEL`、`PUBLIC_REPORT_URL`。密钥只放 Secrets，禁止提交 `.env`。

上传后在仓库的 **Settings → Pages** 中选择 **GitHub Actions** 作为发布来源，并在 **Actions** 页面启用工作流。公开仓库若连续 60 天没有活动，GitHub 可能自动停用定时任务。
