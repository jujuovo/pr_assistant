# GitHub 提交与合并

本次提交是开发进度整合，包含源码、迁移、测试、启动脚本、集中后的 docs 和 OpenSpec 记录，不是已通过最终验收的发布版。三角色审计已收尾；活动 change 的 9.1–9.8 仍未勾选，存在学生统计 500、加载和错误状态、弹窗焦点等已知缺口。以审计证据和 WORKFLOW-RECOVERY.md 为准。

## 提交范围

保留 backend、frontend、docs、openspec、依赖锁文件及启动脚本。已有文档迁移导致旧位置删除，应与新 docs 一并提交。忽略虚拟环境、node_modules、dist、数据库、日志、上传材料、OCR 模型、会话密钥、环境文件、测试临时目录及本地制作目录。忽略规则不会自动移除过去已跟踪的敏感文件，提交前仍需检查暂存区。

## PowerShell 操作

在仓库根目录执行。若分支名已存在，改用新的名称；不要用 reset 或强制推送覆盖历史。

```powershell
Set-Location 'D:\InteractionDesign\Myprogram'
git switch -c integration/three-role-workflows-20261119
git add -A
git diff --cached --stat
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check
git diff --cached --name-only
```

确认暂存内容包含预期源码和文档，没有数据库、日志、私密材料和密钥后：

```powershell
git commit -m "Integrate three-role workflows and audit documentation"
git fetch origin
git merge origin/main
git push -u origin integration/three-role-workflows-20261119
```

若 merge 报冲突，先解决冲突，再 git add 对应文件、git commit；检查通过后再 push。不要跳过冲突处理继续执行。

打开 https://github.com/jujuovo/pr_assistant/compare/main...integration/three-role-workflows-20261119 ，创建 PR，base 选 main，compare 选整合分支。检查 Files changed 和 Actions，通过团队要求后点击 Merge pull request；尚有已知验收缺口，应在 PR 中保留，不宣称生产可发布。

建议 PR 标题：Integrate three-role workflows and audit findings。

建议说明：整合材料、规则、计分、排名三角色流程及迁移、测试和审计文档；排除本地运行数据与临时产物。保留未完成的产品化修复和最终 fresh-database 验收任务。验证结果应填写本次实际执行结果，不能直接沿用历史测试数字。

网页合并后同步本地：

```powershell
git switch main
git pull --ff-only origin main
```

若选择不使用 PR、由有权限的维护者本地合并，则在整合分支已推送、工作区干净且检查通过后执行以下替代步骤（不要与网页合并重复操作）：

```powershell
git switch main
git pull --ff-only origin main
git merge --no-ff integration/three-role-workflows-20261119
git push origin main
```

GitHub 分支保护可能要求必须通过 PR，此时使用网页流程。SSH origin 已配置为 git@github.com:jujuovo/pr_assistant.git；push 需要该仓库写权限及本机 SSH 认证。
