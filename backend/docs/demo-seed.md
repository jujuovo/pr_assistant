# 共享开发账号 seed（Windows / Mac）

仅用于本地 SQLite 开发副本。脚本不依赖 shell 语法，不依赖历史数据库快照、不自动重置已有账号、默认不创建规则；不创建志愿政策或伪造审核成绩。首次prepare已自动加载账号、规则和日期。以下命令用于已有库显式同步共享配置，在项目根目录运行。

Mac：
```sh
.venv-mac/bin/python backend/tools/seed_demo.py --database-file .local-mac/app.db --all
```

Windows（原 start-local.ps1 -PrepareOnly 准备完成后）：
```powershell
.\.venv\Scripts\python.exe backend/tools/seed_demo.py --database-file backend/instance/certificate-local.db --all
```

| 账号 | 密码（仅开发测试） | 姓名 | 角色 |
|---|---|---|---|
| student001 | demo123 | 演示同学 | 学生 |
| teacher001 | demo123 | 演示教师 | 教师 |
| admin001 | demo123 | 演示管理员 | 管理员 |

使用真实登录页生成的验证码，不使用 mock 的固定 1234。

三者均关联信息学院→计算机系→软件工程专业。姓名、邮箱 demo@example.com、电话 13800000000 来自 frontend/src/demo/mock.js。学生学号 student001，性别女，GPA 3.8、学业成绩76、四级580、六级550来自演示资料。教师和管理员不绑定学生学号；原 mock 把 student001 放在所有角色上，后端不能照搬这一关联。管理员绑定学院以满足新接口权限。系/专业名称按用户要求，未照搬 mock 的“计算机科学与技术系/软件工程”。

未写入演示中的虚构已批准申请、加分总计、排名；这些应由真实业务产生。重复执行保留已有密码及成绩；资料/角色/归属冲突时全事务回滚，需人工核实，不能静默覆盖。

如需明确重置三个开发账号的密码，在命令末尾追加 --reset-password。不要对生产数据库使用该工具。工具仅接收已存在的 SQLite 文件，不默认连接 config.py 中的数据库，也拒绝直接操作旧路径 gradpush.db。

验证：python -B -m pytest backend/tests/test_seed_demo.py -q -p no:cacheprovider。

## 共享配置：唯一来源

`backend/seed/demo.json` 保存组织、三角色账号、学生资料、竞赛规则以及固定年度/日期；Mac 和 Windows 均读取这一文件。上述 `--all` 命令加载整套共享数据，不是只给 Mac 配置。

- 新建账号使用配置中的开发密码；已有账号保留密码，显式 --reset-password 才恢复。
- 测试规则只新增缺失项，不覆盖管理员修改的同名规则，不改其他学院。
- 系统年度/起止日期应用配置中的绝对值；重复执行不会再次顺延，其他系统设置保留。
- 当前年度2025、开始2026-10-01、截止2027-01-27（时分秒保留），2026-10-14已处于该申请期内；如需变更，先更新共享 JSON，再两端执行 --all。
- 志愿政策为 null，表示尚未确定，seed 不擅自写入。

各机器的运行数据库分别保存在本机，不通过 Git 同步运行中的数据库文件。共享的是配置与生成脚本，把这些文件提交到仓库后，其他同学拉取并运行同一命令即可生成测试环境。当前脚本支持显式 SQLite 测试副本；生产 PostgreSQL 不在该命令范围内。
