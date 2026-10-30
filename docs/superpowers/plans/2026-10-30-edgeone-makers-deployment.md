# EdgeOne Makers 部署适配实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 SSQ Lab 增加 EdgeOne Makers 可部署版本、只读开奖 API 和自动数据更新流水线。

**Architecture:** 保留本地 FastAPI + SQLite；新增 Makers 根目录静态入口和 cloud-functions/api/index.py FastAPI ASGI 入口。Makers API 读取打包在 Python 模块中的开奖数据，GitHub Actions 每日同步中国福彩网数据并更新该模块。

**Tech Stack:** Python 3.10、FastAPI、Pandas、Requests、GitHub Actions、EdgeOne Makers Cloud Functions。

**Spec:** docs/superpowers/specs/2026-10-30-edgeone-makers-deployment-design.md

## Global Constraints

- Makers Python 运行时按 Python 3.10 兼容。
- Makers API 内部路由不重复 /api 前缀，因为 cloud-functions/api/index.py 已映射到外部 /api。
- 不将 SQLite 写入函数临时文件系统。
- 数据文件必须只包含校验通过的真实来源开奖记录；不注入模拟开奖数据。
- 数据源请求失败时不得清空或覆盖上一版有效数据。
- 不把 EdgeOne API Token、GitHub Token 或任何凭据提交到仓库。

## Review Focus

- 空历史数据：API 返回空数据和可读状态，不抛出未处理异常。
- 官方接口返回错误/HTML/空列表：同步失败且不覆盖已存在数据。
- 重复期号或同一窗口重复抓取：按期号合并，不产生重复记录。
- Python 3.10 运行时：所有云函数代码可在 3.10 导入和编译。
- Cloud Function 无可写持久目录：API 仅读取打包数据，不依赖运行时写数据库。

---

### Task 1: Makers 只读数据模型与 API 测试

**Files:**
- Create: cloud-functions/draws_data.py
- Create: tests/test_edgeone_runtime.py
- Create: .github/workflows/edgeone-verify.yml

**Interfaces:**
- draws_data.DRAW_DATA 提供 schema_version、source、updated_at、latest_issue、draws。
- 每条 draw 记录提供 issue、draw_date、red、blue、sales、poolmoney、prizegrades、source。

- [ ] **Step 1: Write failing tests**：测试数据模块结构、空数据统计行为，以及 Makers FastAPI API 的必需路由。
- [ ] **Step 2: Run tests and confirm expected import/route failures**。
- [ ] **Step 3: Add minimal initial empty data module and Makers FastAPI entrypoint**。
- [ ] **Step 4: Run all unit tests and Python compile checks**。
- [ ] **Step 5: Commit task changes**。

### Task 2: Makers 分析模块和静态前端入口

**Files:**
- Create: cloud-functions/analysis.py
- Create: cloud-functions/api/index.py
- Create: index.html
- Create: static/app.js
- Create: static/style.css
- Modify: cloud-functions/requirements.txt

**Interfaces:**
- API: GET /api/status、GET /api/draws、POST /api/sync（只刷新已发布数据，不发起外部抓取）、GET /api/analysis、GET /api/backtest、POST /api/picks、GET /api/export.csv。
- Makers 内部 FastAPI 路由对应 /status、/draws、/sync、/analysis、/backtest、/picks、/export.csv。
- 云端 CSV 导入明确返回只读提示；本地版 CSV 导入保持原功能。
- 静态资源从根目录 index.html 加载 /static/app.js 和 /static/style.css。

- [ ] **Step 1: Add tests for empty history API responses and API route mapping**。
- [ ] **Step 2: Run tests and verify failure before implementation**。
- [ ] **Step 3: Implement read-only FastAPI endpoints backed by DRAW_DATA**。
- [ ] **Step 4: Copy and adapt existing UI for read-only hosted mode**。
- [ ] **Step 5: Run all tests and compile checks**。
- [ ] **Step 6: Commit task changes**。

### Task 3: Official data sync and GitHub Actions

**Files:**
- Create: scripts/sync_edgeone_data.py
- Create: .github/workflows/sync-edgeone-data.yml
- Modify: README.md

**Interfaces:**
- sync_edgeone_data.py supports --full; default is incremental.
- Successful run atomically replaces cloud-functions/draws_data.py.
- On empty/invalid source results or network errors, exit non-zero and leave existing data unchanged.
- Workflow runs on schedule (UTC 14:30 daily), manual dispatch, and relevant pushes to the deployment branch; it commits only when generated data changes.

- [ ] **Step 1: Write tests for merge-by-issue and safe atomic generation**。
- [ ] **Step 2: Run tests and verify expected failures**。
- [ ] **Step 3: Implement merge/validation/atomic generation**。
- [ ] **Step 4: Add scheduled and manual GitHub Actions workflow**。
- [ ] **Step 5: Run full tests and compile checks**。
- [ ] **Step 6: Commit task changes**。

### Task 4: Documentation and deployment verification

**Files:**
- Modify: README.md
- Create: docs/edgeone-makers-deploy.md

- [ ] **Step 1: Document Makers import settings, Preview branch behavior, Python runtime, and API endpoints**。
- [ ] **Step 2: Verify GitHub Actions workflow run and inspect logs**。
- [ ] **Step 3: Verify Makers build/deployment once an authorized EdgeOne deployment path is available; if account authorization is unavailable, report the exact remaining user action rather than claiming deployment succeeded**。
- [ ] **Step 4: Commit final documentation**。

