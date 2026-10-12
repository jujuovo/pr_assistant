# 快速启动指南

## 启动后端
使用PowerShell的语法设置环境变量并启动Flask服务：
```powershell
cd backend
venv\Scripts\activate
python app.py
```

## 启动前端
在frontend目录下启动Vue前端服务：
```powershell
cd frontend
npm run dev
```

# 推免加分系统

一个基于Vue 3和Python Flask的推免加分管理系统。

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## 前端设置

### 进入前端目录
```bash
cd frontend
```

### 安装依赖
```bash
npm install
```

### 开发模式启动
```bash
npm run dev
```

### 构建生产版本
```bash
npm run build
```

### 预览生产版本
```bash
npm run preview
```

## 后端设置

### 环境配置

1. 进入后端目录
```bash
cd backend
```

2. 激活虚拟环境
```bash
# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

### 数据库配置

#### PostgreSQL配置
确保PostgreSQL已安装并运行，然后创建数据库：
```sql
CREATE DATABASE gradpush;
```

更新`backend/config.py`中的数据库连接信息（默认使用PostgreSQL）：
```python
# PostgreSQL配置
SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:your_password@localhost:5432/gradpush?client_encoding=utf8'
```

**注意**：项目默认使用PostgreSQL数据库，如果需要切换到SQLite，可以将配置修改为：
```python
# SQLite配置
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
```

项目根目录下的`app.db`文件是SQLite数据库文件，如果使用PostgreSQL可以忽略或删除该文件。

### 初始化数据库

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 运行后端服务器

```bash
python app.py
```

## API接口

### 认证接口
- `POST /api/login` - 用户登录
- `POST /api/register` - 用户注册
- `POST /api/reset-password` - 密码重置

### 申请接口
- `GET /api/applications` - 获取所有申请（支持筛选：studentId, status, applicationType）
- `GET /api/applications/<int:id>` - 获取单个申请详情
- `POST /api/applications` - 创建申请（支持文件上传）
- `PUT /api/applications/<int:id>` - 更新申请
- `POST /api/applications/<int:id>/review` - 审核申请
- `DELETE /api/applications/<int:id>` - 删除申请
- `GET /api/applications/pending` - 获取待审核申请

### 系统接口
- `GET /api/health` - 系统健康检查

## 注意事项

1. 本项目仅供学习和演示使用，实际部署时需要加强安全性
2. 数据库连接信息中的密码需要根据实际情况修改
3. 首次运行时需要初始化数据库
4. 前端API_BASE_URL可能需要根据后端运行的端口进行调整：
   - 修改 `frontend/stores/applications.js` 中的 `API_BASE_URL` 常量
   - 修改 `frontend/stores/auth.js` 中的 `API_BASE_URL` 常量
   - 修改 `frontend/components/admin/UserManagement.vue` 中直接使用的API地址
5. 确保前后端服务端口不冲突
6. 前端开发服务器默认运行在 http://localhost:5173/，如果端口被占用会自动切换到其他端口
