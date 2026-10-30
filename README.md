# SSQ Lab

**SSQ Lab — 双色球数据分析与智能选号实验室**

一个本地运行的双色球数据分析工具：自动同步公开开奖数据、SQLite 持久化、冷热与遗漏统计、随机组合生成、历史 walk-forward 策略回测。

> 彩票开奖结果具有随机性。历史频次、冷热号、遗漏值和回测结果不能预测未来开奖，也不会提高单注理论中奖概率。本项目仅供数据分析、编程学习与理性娱乐，不构成投注建议。

## 功能

- **官方数据同步**：从中国福利彩票发行管理中心公开开奖接口获取数据；首次尝试全量同步，之后按最近 45 天增量同步。
- **数据校验**：校验期号、开奖日期、6 个不重复红球（01–33）和 1 个蓝球（01–16）；异常数据不会写入数据库。
- **SQLite 本地数据库**：按期号唯一键 upsert，重复同步不会重复插入；数据保存在 `data/ssq_lab.db`。
- **统计分析**：红蓝球频次、冷热排行、当前遗漏、和值、奇偶比、三区比、跨度。
- **组合生成**：均匀随机、均衡参考、热号参考、冷号参考；支持和值、奇偶、三区筛选。
- **历史回测**：walk-forward 回测，每期只使用该期之前的数据生成号码，减少未来数据泄漏；统计各奖级命中次数。
- **号码管理**：保存个人号码到浏览器本地，并与数据库中的最新一期开奖对比。
- **CSV 导入/导出**：支持本地备份与数据迁移。

## 环境要求

- Python 3.11 或更新版本（推荐）
- Windows 10/11、Ubuntu 22.04+ 或 macOS
- 首次安装依赖需要网络；数据同步需要能访问 `www.cwl.gov.cn`

## Windows 快速启动

1. 安装 Python 3.11+，安装时勾选 `Add Python to PATH`。
2. 双击 `start.bat`。
3. 浏览器访问 `http://127.0.0.1:8765`。
4. 首次启动会尝试从中国福彩网同步历史数据；之后超过 24 小时未同步时会自动进行增量同步。

## Linux / macOS 启动

```bash
./start.sh
```

或手动启动：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器访问 `http://127.0.0.1:8765`。

## 数据同步

网页右上角点击「同步开奖数据」即可。

也可以在项目根目录执行：

```bash
# 首次全量同步（请求官方接口自 2003-01-01 起可查询的记录）
python scripts/sync_data.py --full

# 已有数据库时增量同步
python scripts/sync_data.py
```

### 数据源说明

主数据源为中国福利彩票发行管理中心的公开开奖公告页面及其页面调用的数据接口：

- 页面：<https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/>
- 接口：`https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice`

接口可能受会话 Cookie、反爬策略、访问频率或网站调整影响。程序会先访问官方页面建立会话，再请求 JSON 接口；失败会显示原因，不会伪造数据或清空已有数据库。接口实际返回的历史范围以官方服务为准。若官方服务暂时不可访问，可以稍后重试，或通过「历史数据」导入符合格式的 CSV。

建议不要高频请求。日常使用每天同步一次即可。

## CSV 格式

支持以下列：

```csv
issue,draw_date,red1,red2,red3,red4,red5,red6,blue
2026123,2026-10-27,04,05,20,21,26,30,12
```

导入会检查期号、日期、红球数量/范围/重复值、蓝球范围。任一记录校验失败时，整批导入会被拒绝。

## 数据库位置

默认位置：`data/ssq_lab.db`。

可通过环境变量 `SSQ_DB_PATH` 指定其他 SQLite 文件路径。

个人号码保存在当前浏览器的 `localStorage`，不会上传到服务器。若清理浏览器站点数据，个人号码可能丢失；建议自行备份。

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/status` | 数据库状态、最新一期、同步时间 |
| GET | `/api/draws` | 查询历史开奖 |
| POST | `/api/sync?mode=full` | 全量同步 |
| POST | `/api/sync?mode=incremental` | 增量同步 |
| GET | `/api/analysis?window=50` | 统计分析 |
| GET | `/api/backtest?window=50&warmup=100` | 历史回测 |
| POST | `/api/picks` | 生成号码组合 |
| GET | `/api/export.csv` | 导出 CSV |
| POST | `/api/import` | 导入 JSON 开奖记录 |

FastAPI 文档：<http://127.0.0.1:8765/docs>

## 测试

```bash
python -m unittest discover -s tests -v
```

测试中的合成记录只用于验证代码逻辑，不会作为真实开奖数据写入应用数据库。

## 项目结构

```text
ssq-lab/
├── app/
│   ├── main.py              # FastAPI 路由
│   ├── database.py          # SQLite 持久化
│   ├── analysis.py          # 统计、选号与回测
│   ├── sources/cwl.py       # 中国福利彩票数据源适配器
│   └── static/              # 前端页面、样式和脚本
├── scripts/sync_data.py     # 命令行同步工具
├── tests/                   # 单元测试
├── data/                    # 本地数据库（自动创建，不提交 Git）
├── start.bat
├── start.sh
├── requirements.txt
└── README.md
```

## License

MIT


## EdgeOne Makers 部署（预览环境）

仓库同时包含 EdgeOne Makers 版本，保留本地 FastAPI + SQLite 版本。Makers 使用根目录静态页面和 Python Cloud Functions，不在函数实例中写 SQLite。

### 部署方式

1. 登录 [EdgeOne Makers 控制台](https://pages.edgeone.ai/) 并选择导入 Git 仓库。
2. 选择 GitHub 仓库：`nirvana9/ssq-lab`。
3. 将 `main` 作为 Production 分支；功能分支（包括 `feat/edgeone-makers-deploy`）用于 Preview 环境。
4. 构建根目录使用仓库根目录 `./`，静态输出目录使用 `./`，无需前端构建命令。
5. Python Cloud Functions 运行时选择 Python 3.10。Makers 会自动识别 `cloud-functions/api/index.py` 并映射为 `/api` 路由。
6. 部署完成后，在 Preview 环境打开生成的预览域名。

官方文档：
- [导入 Git 仓库](https://pages.edgeone.ai/document/importing-a-git-repository)
- [Python Cloud Functions](https://pages.edgeone.ai/document/python)
- [构建配置](https://pages.edgeone.ai/document/build-guide)

### Makers 版本的 API

| 方法 | 外部路径 | 用途 |
|---|---|---|
| GET | `/api/status` | 数据状态、最新开奖和数据更新时间 |
| GET | `/api/draws` | 查询历史开奖 |
| POST | `/api/sync` | 重新读取当前已部署数据版本；不直接抓取官网 |
| GET | `/api/analysis` | 统计分析 |
| GET | `/api/backtest` | 历史回测 |
| POST | `/api/picks` | 生成号码组合 |
| GET | `/api/export.csv` | 导出历史数据 |

Makers 会自动剥离文件系统路由前缀 `/api`，因此 FastAPI 内部路由定义为 `/status`、`/draws` 等相对路径。

Makers 云端版本的历史数据为只读；CSV 导入和 SQLite 持久化仍在本地版使用。个人号码保存在浏览器 localStorage。

### 自动同步开奖数据

GitHub Actions 工作流：`.github/workflows/sync-edgeone-data.yml`

- 每天北京时间 22:30 自动检查中国福彩网数据（GitHub 定时任务可能延迟）。
- 支持 Actions 页面手动触发；勾选 full_sync 可执行全量同步。
- 首次空数据时自动全量抓取，后续按最近 45 天增量抓取。
- 按期号去重并校验红球、蓝球和开奖日期。
- 只有数据发生变化时才提交 `cloud-functions/draws_data.py`；同步失败不会覆盖旧数据。
- 数据提交后，已连接 GitHub 的 Makers 项目会按分支自动重新部署。

当前数据包初始为空，首次真实历史数据需要等待数据同步工作流成功。不要将测试夹具当作真实开奖记录。

### 本地检查 Makers 版本

```bash
python -m unittest discover -s tests -v
python -m compileall -q app cloud-functions scripts
```
