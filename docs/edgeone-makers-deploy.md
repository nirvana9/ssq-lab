# EdgeOne Makers 部署与验证

## 1. 当前项目结构

- 根目录 index.html、static/：Makers 静态前端。
- cloud-functions/api/index.py：FastAPI ASGI 函数入口，对外映射到 /api。
- cloud-functions/analysis.py：云端统计、选号和回测逻辑。
- cloud-functions/draws_data.py：随函数包部署的只读开奖数据。
- scripts/sync_edgeone_data.py：从中国福彩网同步数据并原子生成 draws_data.py。
- app/：原本地 FastAPI + SQLite 程序，保持不变。

## 2. 从 GitHub 导入

1. 登录 EdgeOne Makers 控制台。
2. 首次使用时启用 Makers，并连接 GitHub、授权访问 nirvana9/ssq-lab。
3. 导入仓库 https://github.com/nirvana9/ssq-lab。
4. Production 环境使用 main 分支；Preview 环境使用非生产分支。当前适配分支为 feat/edgeone-makers-deploy。
5. 确认 Git 自动部署已开启。

官方指南：[Importing a Git Repository](https://pages.edgeone.ai/document/importing-a-git-repository)。

## 3. 构建配置

本项目是原生 HTML + Python Cloud Functions，不需要 Node 前端构建：

| 配置项 | 值 |
|---|---|
| Root Directory | ./ |
| Build Command | 留空 |
| Output Directory | ./ |
| Python Cloud Functions Runtime | Python 3.10 |
| Function dependencies | cloud-functions/requirements.txt |

Makers 会自动识别 cloud-functions/api/index.py。该文件路径对应外部 /api，平台会剥离 /api 前缀后再交给 FastAPI，因此函数内部只定义 /status、/draws、/analysis 等路由。

官方文档：[Python Cloud Functions](https://pages.edgeone.ai/document/python)、[Build Guide](https://pages.edgeone.ai/document/build-guide)。

## 4. 部署后检查

依次检查：

- /：页面和静态资源可加载。
- /api/health：返回 status=ok。
- /api/status：返回 draw_count、latest、last_sync 和 source。
- /api/draws?limit=10&order=desc：返回历史开奖列表。
- /api/analysis?window=50：返回频次、遗漏和结构统计。
- /api/backtest?window=50&warmup=100：历史数据足够时返回策略回测。
- /api/picks：有历史数据时生成号码；无数据时返回 409 和明确提示。
- /api/export.csv：返回 CSV。

## 5. 数据同步

GitHub Actions 工作流为 .github/workflows/sync-edgeone-data.yml。

- 定时：每天 14:30 UTC（北京时间 22:30）。
- 手动：GitHub 仓库 Actions → Sync SSQ history for EdgeOne Makers → Run workflow。
- 首次空数据会自动选择全量同步；也可以手动勾选 full_sync。
- 增量同步向前回看 45 天，并按期号合并。
- 只有数据变化才会提交新的 draws_data.py。
- 优先使用中国福彩网官方接口；若 GitHub Actions 出口被官方站点返回 403，则切换到 500.com 第三方历史数据源。
- 两个数据源都失败或返回无效数据时，工作流失败，不覆盖已有数据；每期记录保留实际 source 字段。

工作流提交数据后，Makers 若已连接该分支，会自动触发对应环境重新部署。GitHub 定时任务可能延迟，不保证开奖后实时更新。

## 6. 数据持久化边界

Makers 云端 API 不使用 SQLite，也不写函数实例的临时文件系统。开奖历史通过 Python 模块随部署包发布；个人号码仍保存在浏览器 localStorage。云端 CSV 导入被禁用，本地版仍支持 CSV 导入和 SQLite 持久化。

## 7. 本地验证命令

运行以下命令：

    python -m unittest discover -s tests -v
    python -m compileall -q app cloud-functions scripts

GitHub Actions 的 EdgeOne Makers verification 工作流会使用 Python 3.10 执行测试和编译检查。

## 8. 尚需账户授权的步骤

本仓库的代码适配、GitHub CI 和数据同步工作流不需要 EdgeOne 账号凭据。真正创建 Makers 项目、授权 GitHub 仓库和取得 Preview URL，需要项目所有者在 EdgeOne Makers 控制台完成一次授权。没有这一步，不应声称网站已上线。
