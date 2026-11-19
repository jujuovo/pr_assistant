# 推免加分系统

> GitHub 提交与合并步骤见 [提交说明](docs/GITHUB-SUBMISSION.md)。当前为开发整合版本，三角色审计发现的产品化缺口和最终验收仍待完成，详见 [审计收尾](openspec/changes/align-three-role-core-workflows/evidence/9.1-audit-closeout.md)。源码、迁移、测试和文档入库，本地数据库、上传材料、日志及模型不入库。

Vue 3 / Vite 前端、Flask 后端与独立 OCR worker。源码目录固定为 `frontend` 和 `backend`。以下命令均从**仓库根目录**开始执行，路径中有空格时使用引号。

## 环境与功能范围

- Python **3.12**；Node.js `^20.19.0` 或 `>=22.12.0`，建议团队统一 Node 22；npm。
- 本地开发使用 SQLite，无需先装 PostgreSQL。首次安装 Python/npm 依赖和 OCR 模型需要网络。
- 后端端口5001，前端5173；Vite代理 `/api` 与 `/uploads`。浏览器统一使用 `http://localhost:5173`，真实联调不要运行 `npm run demo`。
- 正式竞赛：上传→七类适配中的OCR预览→学生核对并保存材料事实→提交→教师对照原件审核→按固定规则计分。OCR不认定真实性或批准加分。
- 支持蓝桥杯、计算机设计大赛、中国软件杯、挑战杯、CSP、社会实践和其他证明的图片识别。目录外材料及显式不申请计分材料走人工核验；学业成绩、外语、荣誉尚无OCR适配器，仍明确返回501。志愿工时保留既有后端接口。

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

Windows 本地数据库为 `backend/instance/gradpush-dev.db`，模型为 `backend/ocr-models`。均不提交Git。

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

打开 `http://localhost:5173`。Mac数据、模型和会话在 `.local-mac`；重启不必重复安装或准备。各窗口按 Ctrl+C 结束。详见上文「macOS 首次准备」。

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
.\.venv\Scripts\python.exe -B backend/tools/seed_demo.py --database-file backend/instance/gradpush-dev.db --all
```

```sh
# Mac
.venv-mac/bin/python -B backend/tools/seed_demo.py --database-file .local-mac/gradpush-dev.db --all
```

只有明确需要重置三个开发密码时增加 `--reset-password`。开发账号不得用于生产。完整说明见 [demo-seed](docs/demo-seed.md)。

## OCR及材料验收

1. 以学生账号登录，从“学业竞赛”进入正式竞赛，或从“我的材料→其他证书识别与核验”进入人工材料。
2. 选择识别项目、上传清晰图片，核对识别结果后明确点击使用建议；填写缺失日期、赛事年份、级别及团队字段。CSP百分位须另行提供，不从总分推算。
3. 正式目录内且符合级别要求的材料保存后提交；目录外中国软件杯或仅核验的证明保存至人工通道。省级蓝桥杯样本不能冒充正式目录的国家级材料。
4. 以教师登录，核对原图、原始识别和学生确认字段并审核。正式竞赛通过后按固定规则计分；人工材料核验不入分。
5. 学生查看材料和计分反馈，管理员查看规则包、人工核验记录和授权成绩。已发布规则及排名保持审计历史。

旧 `/api/certificates/previews` 默认停止新建，返回409及新入口提示；历史预览与审核继续兼容。完整接口见[本次整合说明](docs/ocr-main-integration.md)。

原开发库 `backend/instance/certificate-local.db` 和Mac `.local-mac/app.db` 保留，新的默认开发库独立准备2028周期及28项正式竞赛目录。原库不会被默认初始化工具替换。

## 前端页面与运行方式

浏览器统一访问 `http://localhost:5173`（见上文）。真实联调用 `npm run dev`，Vite 把 `/api` 与 `/uploads` 代理到后端 5001；`npm run demo` 仅用于页面演示，使用 hash 路由与浏览器内置演示数据，不运行真实 OCR，也不需要后端。

演示模式（`npm run demo`）入口：学生端 `/#/student`、教师端 `/#/teacher`、管理员端 `/#/admin`、登录页 `/#/login`。切换角色时打开对应地址并刷新页面，以重新初始化该角色账号；演示数据保存在当前浏览器中。显示 `Local: http://127.0.0.1:5173/` 后即可在浏览器打开，期间保持终端运行。

前端目录约定：

```text
frontend/
├── index.html                 # 唯一 HTML 入口
├── public/                    # 图片等静态资源
├── src/
│   ├── main.js / App.vue      # 应用初始化、路由出口
│   ├── pages/                 # 按角色：student / teacher / admin / common
│   ├── components/            # 可复用组件（common、student、admin/rules）
│   ├── assets/styles/         # 全局、布局、页面、组件、共享样式
│   ├── composables/           # 可复用响应式逻辑
│   ├── config/                # 导航配置
│   ├── services/              # 后端 API 与文件 URL 处理
│   ├── stores/                # Pinia 状态（登录、申请、文件、提示）
│   ├── router/                # 三端路由及权限守卫
│   └── demo/                  # 演示数据与工具
├── tests/
├── jsconfig.json              # @/* → src/* 别名
├── vite.config.js             # 开发与正式构建
└── vite.homepage.config.js    # 演示主页构建
```

脚本（在 `frontend` 目录执行，或用 `npm --prefix frontend`）：`npm ci`、`npm run dev`、`npm run demo`、`npm run build`、`npm run build:demo`、`npm run build:homepage`、`npm run format`、`npm run format:check`。

维护约定：新页面放入 `pages/<角色>/<功能>/` 并使用 PascalCase；复用组件放入 `components/`，多页共用放入 `components/common/`；页面 CSS 放入 `assets/styles/pages/` 对应路径并保持 scoped；源码内统一用 `@/` 引用 `src/`；接口继续复用 `services/`，改动接口须单独联调后端。仅交付源码时不要携带 `node_modules`（历史交付中的该目录可能是指向相邻目录的软链接，独立安装前先删除链接本身再 `npm ci`）。

## 测试与生产构建

使用本机虚拟环境的python执行（Windows为 `.venv/Scripts/python.exe`，Mac为 `.venv-mac/bin/python`）：

```sh
python -B -m pytest backend/tests -q -p no:cacheprovider
node --test frontend/tests/material-api.test.mjs
npm --prefix frontend run build
```

普通测试跳过真实模型测试；真实OCR测试详见 [证书说明](docs/certificate-ocr.md)。GitHub Actions提供Windows/macOS安装、建库、回归与构建检查，推送后查看Actions结果；CI不替代浏览器手工验收。

当前已验证Mac ARM64真实OCR及隔离库申报审核。Windows修改后尚未实机运行，不能声称两端均已完整验收。前端构建仍有大包提示；后端有既有SQLAlchemy/Flask-Session告警。

## 项目结构与提交范围

- `frontend`：Vue 3 前端单页应用，仅保留源码（`src`）、静态资源、测试与构建配置；不再单独放置 README 或 docs，说明文档统一在仓库根 `docs/`。
- `backend/blueprints`、`services`：接口与业务；`models.py`及其他models文件：数据结构。
- `backend/seed`、`tools`：共享数据和初始化/模型准备工具。
- `backend/tests`、`frontend/tests`：测试；`backend/migrations`：保留的迁移历史。
- `backend/third_party`：第三方算法及许可证，必须保留。
- `.github/workflows`：跨平台回归；`docs`：除 README 外的全部说明文档集中存放，发布检查见 `docs/RELEASE-CHECKLIST.md`。

不要提交虚拟环境、node_modules、dist、模型、数据库、上传原件、日志、会话、密钥或.env。`.gitignore`已覆盖；测试样本、依赖锁文件、源码和seed必须保留。

生产部署另行配置 `DATABASE_URL` 和稳定的 `SECRET_KEY` 环境变量，并配置Web/worker相同存储及数据库。程序不会自动读取.env。不要在源码中写真实凭据，不要在已有仓库重新执行 `flask db init` / 自动生成迁移。本文本地SQLite建表流程不等于生产PostgreSQL迁移验收。

更多接口：[证书OCR](docs/certificate-ocr.md)、[志愿工时](docs/volunteer-automation.md)、[五类材料](docs/material-interfaces.md)、[前端对接](docs/material-api-integration.md)。
