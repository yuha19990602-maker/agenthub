# AI Portal V2 快速启动指南 (Fake SSO 模式)

本指南帮助你在没有真实 SSO 基础设施的情况下快速启动 AI Portal V2 进行测试。

## 特性

- ✅ **Fake SSO 模式** - 无需配置真实 SSO，任何授权码都会被接受
- ✅ **完整功能** - 除真实 SSO 验证外，所有功能均可测试
- ✅ **默认用户** - 自动登录为 E10001 (测试用户，拥有 admin 角色)
- ✅ **示例资源** - 包含 direct_chat, skill_chat, openai_compatible_v1, websdk, iframe 等类型

## 环境要求

- Python 3.12+
- Node.js 18+
- (可选) OpenCode 服务 - 用于 native chat 功能
- (可选) OpenWork 服务 - 用于技能管理

## 快速启动

### 1. 使用一键启动脚本

```bash
./scripts/start_dev.sh
```

这个脚本会：
1. 检查并安装依赖
2. 启动后端服务 (http://localhost:8000)
3. 启动前端服务 (http://localhost:5173)

### 2. 手动启动

**后端:**
```bash
cd backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端:**
```bash
cd frontend
npm run dev
```

## 访问应用

- **前端界面**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## Fake SSO 工作原理

当 `SSO_AUTHORIZE_URL` 和 `SSO_TOKEN_URL` 为空时，系统自动启用 Fake SSO 模式：

1. 用户访问前端，未登录
2. 前端调用 `/api/auth/login-url` 获取登录地址
3. Fake SSO 直接返回回调 URL（带授权码）
4. 前端使用授权码调用 `/api/auth/exchange`
5. 后端接受任何授权码，创建本地会话
6. 用户自动登录为默认测试用户

### 默认测试用户信息

```json
{
  "emp_no": "E10001",
  "name": "测试用户",
  "dept": "Engineering",
  "roles": ["employee", "admin"],
  "email": "test@company.com"
}
```

## 测试不同功能

### 1. Native Chat (通用对话)
- 点击左侧"基础功能"->"通用对话"
- 无需 OpenCode 也可测试界面，但对话功能需要 OpenCode 服务

### 2. OpenAI Compatible 资源
- 点击左侧"模型资源"->"OpenAI 兼容模型"
- 配置实际的 API Key 后可测试:
  ```bash
  export OPENAI_API_KEY=your-key-here
  ```

### 3. WebSDK/Iframe 资源
- 点击对应资源会显示工作区
- 由于使用示例 URL，可能显示加载失败（这是正常的）

### 4. 会话恢复
- 创建会话后，刷新页面
- 点击左侧会话列表中的历史会话
- 系统会正确恢复会话状态

## 配置说明

### 后端配置 (backend/.env)

```env
# 启用 Fake SSO（留空即可）
SSO_AUTHORIZE_URL=
SSO_TOKEN_URL=

# 其他配置
ENV=dev
ENABLE_MOCK_LOGIN=true
COOKIE_SECURE=false
```

### 前端配置 (frontend/.env)

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 切换到真实 SSO

当需要测试真实 SSO 时:

1. 编辑 `backend/.env`，填入真实 SSO 配置:
```env
SSO_AUTHORIZE_URL=https://your-sso.com/oauth/authorize
SSO_TOKEN_URL=https://your-sso.com/oauth/token
SSO_CLIENT_ID=your-client-id
SSO_CLIENT_SECRET=your-client-secret
```

2. 重启后端服务

3. 系统将自动切换到真实 SSO 模式

## 常见问题

### Q: 启动时报 "Resources file not found"
A: 确保 `config/resources.generated.json` 存在，或运行资源同步脚本。

### Q: 无法登录 / 鉴权失败
A: 检查后端日志是否显示 "Fake SSO mode enabled"。如果显示，说明 Fake SSO 已启用。

### Q: 前端显示 "无法连接到后端"
A: 确保后端服务已启动，且 `VITE_API_BASE_URL` 配置正确。

### Q: 会话恢复失败
A: 检查后端日志，确认 `GET /api/sessions/{id}/resume` 返回正确数据。

## 生产环境注意事项

**警告**: Fake SSO 模式仅供开发和测试使用！

生产环境必须:
1. 配置真实 SSO 端点
2. 设置 `ENV=prod`
3. 禁用 `ENABLE_MOCK_LOGIN`
4. 启用 `COOKIE_SECURE=true` (HTTPS)

启动时会自动检查这些配置，不符合要求会拒绝启动。
