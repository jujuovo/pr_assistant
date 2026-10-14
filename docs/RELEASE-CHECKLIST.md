# 发布整理记录（2026-10-14）

## 本次变更

- 删除已跟踪的Python缓存；历史SQLite快照及未使用的根目录Node依赖移出项目备份。frontend依赖锁文件、测试样本、迁移历史、第三方许可证保留。
- 不移动运行中的Mac虚拟环境、模型、上传材料或数据库；通过.gitignore排除。数据库有项目外一致性备份。
- requirements.txt统一UTF-8；移除配置中的硬编码连接密码/密钥。部署使用DATABASE_URL、SECRET_KEY；本地缺省密钥自动存入被忽略的文件。
- prepare_local从当前模型建表并加载共享seed，不依赖历史快照。已有数据库增量补齐，保留已存在密码和业务数据。显式seed --all才同步已有库日期。
- Windows仍用start-local.ps1；Mac仍用mac-local.py。Windows使用npm.cmd避免npm.ps1执行策略问题；Vite代理明确指向127.0.0.1:5001。
- README改为两平台首次安装、共享数据、启动、OCR验收和边界；旧部署说明标注历史资料。
- .github/workflows/verify.yml在Windows/macOS执行依赖检查、建库、回归、前端构建。

## 验证与限制

- Mac后端普通回归176通过、3项真实模型测试默认跳过。
- 前端请求测试7通过，生产构建通过；已移除根目录node_modules，构建不依赖它。
- pip check通过。中文带空格目录首次建库、重复准备保留密码和成绩均通过。
- 真实模型预览测试覆盖上传→识别→学生修改→教师查看原件→整份审核，独立数据库，不污染用户测试库。
- Windows实机和GitHub Actions尚未运行；推送后必须查看两端检查。无PostgreSQL生产迁移或Intel Mac验收结论。
- 既有SQLAlchemy/Flask-Session警告与前端大包警告未在本次作无关重构。
- 蓝桥杯已接入提交前识别。志愿工时页面、五类材料页面/通用OCR仍未完成，见README。

## 推送前后

1. 查看git diff和git status；缓存及旧数据库的删除是预期变更，记得将删除记录一起提交。
2. 只提交当前项目。不要上传旁边的“发布前备份”目录，不要强制添加已忽略文件。
3. 本次清理只清除当前文件；不会清除旧Git历史。如果历史硬编码凭据曾用于真实服务，应在对应服务轮换。
4. 推送后等待GitHub Actions两端通过，再按README完成三角色登录和真实OCR浏览器验收。
5. 修改共享规则/日期先更新backend/seed/demo.json，再各机执行seed --all。运行数据库不经Git共享。

当前未自动commit或push。
