# SSQ Lab EdgeOne Makers 部署适配设计

## 目标

将现有 SSQ Lab（本地 FastAPI + SQLite）增加一个 EdgeOne Makers 可部署版本，保留本地运行方式，并提供可自动更新的开奖数据集，使 Makers 环境无需依赖函数临时文件系统保存历史数据。

## 用户与成功标准

- 用户从 GitHub 导入仓库后，可以在 EdgeOne Makers 预览环境打开 SSQ Lab。
- 页面能够通过 Makers Python Cloud Functions 获取状态、历史开奖、统计、回测和选号结果。
- 历史数据由 GitHub Actions 定时从中国福彩网同步并提交到仓库；接口失败时保留上一次数据。
- 原有 Windows / Linux 本地 FastAPI + SQLite 使用方式不被破坏。

## 范围

### 目标内

- 增加 Makers 静态站点入口和 Cloud Functions FastAPI 入口。
- 增加只读开奖数据模块，作为函数部署包的一部分。
- 增加数据同步脚本及 GitHub Actions 定时/手动工作流。
- 增加 Makers 部署说明和 API / 数据模块自动测试。
- 保留现有本地应用、SQLite 和 CSV 导入能力。

### 非目标

- 不在 Makers 函数临时文件系统中写 SQLite 或保存用户数据。
- 不在本次实现账号登录、云端投注单保存或付费功能。
- 不宣称历史冷热、遗漏、回测可以提高中奖概率。
- 不在没有用户 EdgeOne 账号授权的情况下声称已完成账户内正式部署。

## 方案比较

1. **将现有 FastAPI + SQLite 原样部署**：代码改动少，但 Serverless 实例文件系统不适合作为持久数据库；扩缩容和冷启动后数据可能不一致，不采用。
2. **Makers 静态前端 + Python Cloud Functions 只读 API + GitHub Actions 数据同步**：复用现有 FastAPI 分析与选号逻辑，历史开奖以 Python 数据模块打包；不依赖运行时可写磁盘。选择此方案。
3. **完全静态前端，在浏览器中实现全部分析**：部署简单，但需要重写现有 API 调用和回测逻辑，重复实现分析算法；本次不采用。

## 架构与决策

- 根目录 index.html、static/ 作为 Makers 静态站点入口，保留原有 UI。
- cloud-functions/api/index.py 暴露 FastAPI ASGI 应用。由于 Makers 会剥离文件系统路由前缀 /api，函数内部路由定义为 /status、/draws、/analysis、/backtest、/picks 等，不再重复 /api 前缀。
- cloud-functions/analysis.py 提供云函数侧的分析逻辑；cloud-functions/draws_data.py 保存由同步脚本生成的只读开奖数据常量。使用 Python 模块而非函数临时文件写入数据库，确保部署包包含数据。
- scripts/sync_edgeone_data.py 首次全量同步，后续以最近 45 天为窗口增量抓取，按期号合并、校验、排序，并原子写入 cloud-functions/draws_data.py。
- GitHub Actions 每日 22:30（Asia/Shanghai，对应 UTC 14:30）运行数据同步，并支持手动触发。仅在数据有变化时提交更新。
- Makers 端数据为只读；手动“刷新”仅重新读取当前已部署的数据版本。数据源同步由 GitHub Actions 完成。
- 原本的本地 FastAPI + SQLite 程序保持独立，不被 Makers 的只读约束影响。

## 约束与风险

- Makers Python Cloud Functions 运行时为 Python 3.10；函数单次执行有时间限制，数据同步不放在用户请求链路中。
- 官方开奖接口可能发生反爬、Cookie、参数或字段变化；同步失败时工作流失败并保留原数据，必须显示数据更新时间和来源。
- Makers GitHub 导入与账号内部署需要用户的 EdgeOne Makers 账号授权；本次可以完成仓库适配和 CI 验证，但不能冒充已经登录用户账户。
- GitHub Actions 的定时任务可能延迟；每日自动同步不是实时开奖推送。
