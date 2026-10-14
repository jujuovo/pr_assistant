# 推免加分系统

Vue 3 / Vite 前端、Flask 后端与独立 OCR worker。源码目录固定为 `frontend` 和 `backend`。以下命令均从**仓库根目录**开始执行，路径中有空格时使用引号。

## 环境与功能范围

- Python **3.12**；Node.js `^20.19.0` 或 `>=22.12.0`，建议团队统一 Node 22；npm。
- 本地开发使用 SQLite，无需先装 PostgreSQL。首次安装 Python/npm 依赖和 OCR 模型需要网络。
- 后端端口5001，前端5173；Vite代理 `/api` 与 `/uploads`。浏览器统一使用 `http://localhost:5173`，真实联调不要运行 `npm run demo`。
- 蓝桥杯：上传→OCR预览→学生修改申报值→提交→教师对照原图与OCR审核。OCR不会自动认定真实性或批准加分。
- 志愿工时有后端和请求模块，但学生页面闭环尚未接入；五类材料有结构化核验接口，通用 `recognize` 返回501。不能把这些未完成功能视为操作系统兼容问题。

## Windows 首次准备与启动

在 PowerShell 中执行（先安装 Python 3.12 和 Node.js）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-ocr.txt
.\.venv\Scripts\python.exe -m pip check
npm.cmd ci --prefix frontend
.\start-local.ps1
```

脚本会准备数据库、共享账号和模型，然后启动 Web、worker、前端。模型首次准备较慢。若系统阻止执行项目脚本，可仅对当前 PowerShell 窗口执行 `Set-ExecutionPolicy -Scope Process Bypass` 后重试。不要修改全系统策略。

打开 `http://localhost:5173`。日志在 `backend/logs/local-web.*.log`、`local-worker.*.log`。按 Ctrl+C 退出；之后只需运行 `./start-local.ps1`。只准备数据库与模型可运行 `./start-local.ps1 -PrepareOnly`。

Windows 本地数据库为 `backend/instance/certificate-local.db`，模型为 `backend/ocr-models`。均不提交Git。

## macOS 首次准备

安装 Python 3.12 和符合版本要求的 Node.js；例如已使用 Homebrew 时安装 `python@3.12`。Apple Silicon 本机已验证；Intel Mac 尚未实机验证。

```sh
python3.12 -m venv .venv-mac
.venv-mac/bin/python -m pip install --upgrade pip
.venv-mac/bin/python -m pip install -r backend/requirements-ocr.txt
.venv-mac/bin/python -m pip check
npm ci --prefix frontend
.venv-mac/bin/python mac-local.py prepare
.venv-mac/bin/python mac-local.py models
```

之后打开三个终端，每个终端都先进入仓库根目录，分别运行：

```sh
# 终端 A：Web
.venv-mac/bin/python mac-local.py web
```

```sh
# 终端 B：前端
npm --prefix frontend run dev -- --host localhost --port 5173 --strictPort
```

```sh
# 终端 C：OCR worker
.venv-mac/bin/python mac-local.py worker
```

打开 `http://localhost:5173`。Mac数据、模型和会话在 `.local-mac`；重启不必重复安装或准备。各窗口按 Ctrl+C 结束。详见 [Mac 操作说明](MAC-运行指南.md)。

## 共享测试数据与登录

仓库**不分发旧数据库快照**。`backend/seed/demo.json` 是共享测试数据来源，准备命令从模型建表并加载seed。每个人生成自己的数据库，不会连接到同一台远程测试库。

| 角色 | 账号 | 开发测试密码 |
| --- | --- | --- |
| 学生 | student001 | demo123 |
| 教师 | teacher001 | demo123 |
| 管理员 | admin001 | demo123 |

使用真实登录页显示的验证码。三角色同属“信息学院→计算机系→软件工程专业”。包含一套信息学院竞赛测试规则；不伪造审核历史或排名。申请期为2026-10-01至2027-01-27（具体时分秒及年度见JSON）。超过截止时间后需团队明确修改共享设置。

重复prepare保留已有数据库、账号密码及设置；已有库需要同步共享日期时，手动执行：

```powershell
# Windows
.\.venv\Scripts\python.exe -B backend/tools/seed_demo.py --database-file backend/instance/certificate-local.db --all
```

```sh
# Mac
.venv-mac/bin/python -B backend/tools/seed_demo.py --database-file .local-mac/app.db --all
```

只有明确需要重置三个开发密码时增加 `--reset-password`。开发账号不得用于生产。完整说明见 [demo-seed](backend/docs/demo-seed.md)。

## 蓝桥杯验收

1. 三个服务运行后，以学生账号登录，刷新页面确认会话仍有效。
2. 新建科创竞赛申请，证书项目选择蓝桥杯，上传清晰图片；可用 `backend/tests/fixtures/lanqiao` 内测试样本。
3. 等待预览表格出现；核对OCR值，修改一个“学生申报值”，填写项目名称和获得日期，提交审核。
4. 以教师账号登录，在待审核申请详情查看OCR、学生申报值与原图，然后审核整份申请。
5. 学生查看审核结果。原OCR与原图应保留，不能被学生修改覆盖。

替换材料会创建新的识别草稿，未使用的旧草稿可在申请记录中处理。旧流程申请结果保留；验证新流程请新建申请。

## 测试与生产构建

使用本机虚拟环境的python执行（Windows为 `.venv/Scripts/python.exe`，Mac为 `.venv-mac/bin/python`）：

```sh
python -B -m pytest backend/tests -q -p no:cacheprovider
node --test frontend/tests/material-api.test.mjs
npm --prefix frontend run build
```

普通测试跳过真实模型测试；真实OCR测试详见 [证书说明](backend/docs/certificate-ocr.md)。GitHub Actions提供Windows/macOS安装、建库、回归与构建检查，推送后查看Actions结果；CI不替代浏览器手工验收。

当前已验证Mac ARM64真实OCR及隔离库申报审核。Windows修改后尚未实机运行，不能声称两端均已完整验收。前端构建仍有大包提示；后端有既有SQLAlchemy/Flask-Session告警。

## 项目结构与提交范围

- `frontend/src`：页面、组件、状态和API请求。
- `backend/blueprints`、`services`：接口与业务；`models.py`及其他models文件：数据结构。
- `backend/seed`、`tools`：共享数据和初始化/模型准备工具。
- `backend/tests`、`frontend/tests`：测试；`backend/migrations`：保留的迁移历史。
- `backend/third_party`：第三方算法及许可证，必须保留。
- `.github/workflows`：跨平台回归；`docs/RELEASE-CHECKLIST.md`：发布检查与当前边界。

不要提交虚拟环境、node_modules、dist、模型、数据库、上传原件、日志、会话、密钥或.env。`.gitignore`已覆盖；测试样本、依赖锁文件、源码和seed必须保留。

生产部署另行配置 `DATABASE_URL` 和稳定的 `SECRET_KEY` 环境变量，并配置Web/worker相同存储及数据库。程序不会自动读取.env。不要在源码中写真实凭据，不要在已有仓库重新执行 `flask db init` / 自动生成迁移。本文本地SQLite建表流程不等于生产PostgreSQL迁移验收。

更多接口：[证书OCR](backend/docs/certificate-ocr.md)、[志愿工时](backend/docs/volunteer-automation.md)、[五类材料](backend/docs/material-interfaces.md)、[前端对接](frontend/docs/material-api-integration.md)。
