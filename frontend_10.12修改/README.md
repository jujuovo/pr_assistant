# GradPush 前端（10.12 修改版）

本目录以 `frontend_10.12` 的页面内容为基础完成结构整理，使用 Vue 3、Vite、Pinia 和 Vue Router。

## 怎么打开网页

### 直接查看页面（推荐：演示模式）

```sh
npm run demo -- --port 5173 --strictPort
```

看到终端显示 `Local: http://127.0.0.1:5173/` 后，在浏览器打开以下地址：

| 页面     | 浏览器地址                                                         |
| -------- | ------------------------------------------------------------------ |
| 学生端   | [http://127.0.0.1:5173/#/student](http://127.0.0.1:5173/#/student) |
| 教师端   | [http://127.0.0.1:5173/#/teacher](http://127.0.0.1:5173/#/teacher) |
| 管理员端 | [http://127.0.0.1:5173/#/admin](http://127.0.0.1:5173/#/admin)     |
| 登录页   | [http://127.0.0.1:5173/#/login](http://127.0.0.1:5173/#/login)     |

演示模式不需要启动后端，直接访问三端地址会自动进入对应的演示账号。切换角色时，打开对应地址后刷新页面，以重新初始化该角色账号。演示数据保存在当前浏览器中。

**打开网页期间保持终端运行。** 关闭服务时，在终端按 `Control + C`；下次查看时重新执行上面的启动命令。不要直接双击 `index.html` 或 `.vue` 文件，源码需要通过 Vite 服务运行。

如果提示端口 `5173` 已占用，可改用下面的命令，并把上表地址中的 `5173` 全部换成 `5174`：

```sh
npm run demo -- --port 5174 --strictPort
```

### 首次运行或缺少依赖时

如果提示 `npm: command not found`，先安装符合下文版本要求的 Node.js，再重新打开终端。如果提示找不到 `vite` 或依赖包，在项目目录执行：

```sh
# 仅在 node_modules 是软链接时移除链接本身，不删除它指向的目录。
if [ -L node_modules ]; then unlink node_modules; fi
npm ci
npm run demo -- --port 5173 --strictPort
```

安装依赖需要联网；依赖已经可用时不必重复安装。

### 连接真实后端

需要使用真实账号和数据时，先启动原 GradPush 项目的后端，确保它运行在 `http://localhost:5001`，再在前端目录执行：

```sh
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

然后打开 [登录页](http://127.0.0.1:5173/login)，使用后端已有账号登录，系统会按角色进入对应页面。正式模式的地址不带 `#`。如果演示服务还在运行，先在它所在的终端按 `Control + C`，再启动正式模式。

## 目录约定

```text
frontend_10.12/
├── index.html                 # 唯一 HTML 入口
├── public/                    # 图片、独立演示说明页等静态资源
├── src/
│   ├── main.js                # 应用初始化
│   ├── App.vue                # 路由出口和全局提示
│   ├── pages/
│   │   ├── student/           # 学生端
│   │   │   ├── StudentLayout.vue
│   │   │   ├── home/          # 首页、条例、草稿、修改及反馈入口
│   │   │   ├── applications/  # 申请分类、成绩、表单、记录
│   │   │   └── statistics/    # 学生统计
│   │   ├── teacher/           # 教师端
│   │   │   ├── TeacherLayout.vue
│   │   │   └── reviews/       # 待审核及审核记录
│   │   ├── admin/             # 管理员端
│   │   │   ├── AdminLayout.vue
│   │   │   ├── users/
│   │   │   ├── organization/
│   │   │   ├── applications/
│   │   │   ├── scores/
│   │   │   ├── rules/
│   │   │   ├── files/
│   │   │   └── settings/
│   │   └── common/            # 登录、个人信息、公共统计页面
│   ├── components/            # 页面的可复用组成部分
│   │   ├── common/            # Header、Footer、Sidebar、Toast 等
│   │   ├── student/           # 学生导航
│   │   └── admin/rules/       # 规则弹窗及递归树节点
│   ├── assets/styles/
│   │   ├── global/            # 全局基础、首页及系统主题
│   │   ├── layouts/           # 教师/管理员共用布局样式
│   │   ├── pages/             # 对应 pages 的角色及功能目录
│   │   ├── components/        # 对应公共组件的样式
│   │   └── shared/            # 内容区域共用样式
│   ├── composables/           # 可复用响应式逻辑，例如时段问候语
│   ├── config/                # 导航配置
│   ├── services/              # 后端 API 和文件 URL 处理
│   ├── stores/                # 登录、申请、文件和提示状态
│   ├── router/                # 三端路由及权限守卫
│   └── demo/                  # 演示数据和演示工具
├── docs/file-mapping.json     # 整理前后源文件路径对照
├── .editorconfig             # 缩进、编码、换行约定
└── .prettierrc.json           # 统一格式化配置
```

Vue 页面里的 `<template>` 就是页面的 HTML 模板，因此按照三端组织 `.vue` 页面，保留单一 `index.html` 入口。页面专用的响应式逻辑保留在 `<script setup>` 中，避免机械拆分导致 props、事件或生命周期失效；跨页面逻辑放入 `composables`，接口、状态及配置各自集中管理。

## 开发与构建

使用 Node.js `^20.19.0 || >=22.12.0`。

```sh
npm ci
npm run dev             # 正式接口开发，代理到 http://localhost:5001
npm run demo            # 本地演示数据，不要求后端启动
npm run build           # 正式构建 → dist/
npm run build:demo      # 演示构建 → dist/（会替换前一次构建）
npm run build:homepage  # 相对资源路径的演示构建 → dist-homepage/
npm run format          # 统一格式
npm run format:check    # 检查格式
```

当前交付目录继承了原有 `node_modules` 软链接，指向相邻的 `frontend修改/node_modules`，不是源码的一部分。需要独立安装时，先删除这个软链接本身（不要删除其指向的目录），再运行 `npm ci`。Prettier 已登记在开发依赖和锁文件中，独立安装后即可使用格式命令。

正式模式保留 `/login`、`/student`、`/teacher`、`/admin` 路径，服务器应将这些路径回退到 `index.html`。演示模式使用 hash 路由，如 `/#/student`、`/#/teacher`、`/#/admin`；演示账户与原版本一致。

## 后续维护规则

- 新页面放入 `pages/<角色>/<功能>/`，页面组件使用 PascalCase 命名。
- 子组件放入 `components/`；多个页面共用的组件放入 `components/common/`。
- 页面 CSS 放入 `assets/styles/pages/` 的对应路径，通过 `<style scoped src="…">` 引入；不要把原本 scoped 的样式改成全局样式。
- 全局样式继续按 `homepage.css → main.css → system-theme.css` 的顺序加载，以保持覆盖关系。
- 源码内通过 `@/` 引用 `src/`，避免跨多层目录的相对路径。
- API 请求继续复用 `services/api.js`；修改接口行为时须单独联调后端。
- 导航文字和角色布局中的页面标识保持一致。当前页面切换仍沿用原版本的组件状态方式。
- 公共页眉使用 `Header.vue`；登录页版权使用 `Footer.vue`。三端工作台没有额外新增页脚，避免改变原布局。

本次以目录、复用及格式整理为主，保留页面文案、接口地址、表单字段、演示数据和权限判断。`vite.homepage.config.js` 的构建输出改到本目录 `dist-homepage/`，避免向父目录散落产物。
