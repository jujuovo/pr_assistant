# 阿里云 Ubuntu 测试环境

目标：4 vCPU、8GB RAM、40GB 系统盘、5Mbps 公网。使用 Docker Compose 隔离应用依赖；
Web 两进程，OCR 单独一个 worker，共享数据库与材料持久卷。数据库不暴露公网端口。
OCR镜像和模型较大，首次安装前确认磁盘余量。

1. 在服务器安装 Docker Engine 与 Compose 插件，将仓库放入服务器工作目录。
2. 将 deploy/.env.example 复制为 deploy/.env，填写不同的随机数据库密码与 SECRET_KEY。
   DATABASE_URL里的密码必须和POSTGRES_PASSWORD一致；URL特殊字符需要编码。
3. 把已验收的两个OCR模型放入 deploy/models/PP-OCRv5_mobile_det 和
   deploy/models/PP-OCRv5_mobile_rec（包含 inference.yml）。
4. 从仓库根目录执行 `docker compose -f deploy/compose.yaml config --quiet`，再执行
   `docker compose -f deploy/compose.yaml up -d --build`。
   migrate成功后才启动Web和worker；失败时先检查其日志，不能跳过迁移。
5. 此配置仅监听服务器127.0.0.1:8080。测试可通过SSH隧道访问；对外访问应由宿主HTTPS反向代理转发，
   配好证书后设置SESSION_COOKIE_SECURE=true并重建Web/worker容器。保持/api与页面同域。
6. 空库迁移只负责结构；还需要学院、三角色账号、活动周期和正式规则包。
   不能在生产库运行prepare_local或竞赛reset工具来代替初始化，不能沿用公开演示密码。
7. 查看 `docker compose -f deploy/compose.yaml logs --tail=100 migrate web worker`。
   OCR模型缺失会让worker启动失败，人工材料通道可独立工作。

部署尚待目标服务器实测。不要把本地SQLite或Compose配置校验当作Ubuntu/PostgreSQL运行验收。

## 持久化与恢复

postgres-data保存数据库；app-data保存所有材料、上传文件和会话；模型由宿主只读挂载。
备份必须同时保留数据库pg_dump、app-data卷和当前配置版本。先暂停写入及worker，再在同一窗口备份；
恢复到独立实例核对附件与记录后再切换。不要执行 `docker compose down -v`，它会删除数据卷。
升级前备份；回滚应用镜像不得擅自downgrade有业务数据的数据库。
