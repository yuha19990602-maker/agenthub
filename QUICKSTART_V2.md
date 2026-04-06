# AI Portal V2 快速启动

本指南基于当前代码实现，覆盖两种本地模式：

- `dev + mock-login`：本地开发最快路径
- `dev/prod + 真实 SSO`：接入真实身份系统

OpenCode / OpenWork 可独立运行在本机：

- OpenCode: `http://127.0.0.1:4096`
- OpenWork: `http://127.0.0.1:8787`

## 1. 准备配置

### 后端 `backend/.env`

开发模式最小配置：

```env
ENV=dev
ENABLE_MOCK_LOGIN=true
COOKIE_SECURE=false
SESSION_MAX_AGE_SEC=86400

SSO_AUTHORIZE_URL=
SSO_TOKEN_URL=
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=
SSO_REDIRECT_URI=http://localhost:8000/api/auth/callback
SSO_JWKS_URL=

OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode
OPENCODE_PASSWORD=your-password

OPENWORK_BASE_URL=http://127.0.0.1:8787
OPENWORK_TOKEN=your-token

PORTAL_NAME=AI Portal
RESOURCES_PATH=config/resources.generated.json
```

说明：

- 若未配置真实 SSO 且启用了 `ENABLE_MOCK_LOGIN=true`，前端会从 `/api/auth/login-url` 获取 dev mock 登录地址。
- 若接入真实 SSO，填上 SSO 相关配置即可，Portal 仍使用本地 `portal_sid` session。

### 前端 `frontend/.env`

```env
VITE_API_BASE_URL=/
VITE_APP_NAME=AI Portal
```

## 2. 启动服务

### 一键启动

```bash
./scripts/start.sh
```

### 分别启动

后端：

```bash
cd backend
/home/yy/python312/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm run dev
```

## 3. 访问地址

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

## 4. 推荐联调检查

### 登录

开发模式：

```bash
curl -i "http://127.0.0.1:8000/api/auth/mock-login?emp_no=E10001"
```

应看到 `Set-Cookie: portal_sid=...`

### 健康检查

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:5173/api/health
```

第二个请求会经过前端 Vite 代理。

### OpenWork 联调

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/skills
```

### OpenCode 联调

1. 启动 native 资源

```bash
curl -X POST -b cookies.txt http://127.0.0.1:8000/api/resources/general-chat/launch
```

2. 非流式发消息

```bash
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/sessions/{session_id}/messages \
  -d '{"text":"请用一句中文回复：联调成功。"}'
```

3. 流式发消息

```bash
curl -N -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  http://127.0.0.1:8000/api/sessions/{session_id}/messages/stream \
  -d '{"text":"请只输出两个字：收到"}'
```

## 5. 切换到真实 SSO

把以下字段填完整后重启后端：

```env
SSO_AUTHORIZE_URL=https://your-sso.example.com/oauth/authorize
SSO_TOKEN_URL=https://your-sso.example.com/oauth/token
SSO_CLIENT_ID=your-client-id
SSO_CLIENT_SECRET=your-client-secret
SSO_JWKS_URL=https://your-sso.example.com/.well-known/jwks.json
COOKIE_SECURE=true
```

生产环境还需要：

```env
ENV=prod
ENABLE_MOCK_LOGIN=false
```

## 6. 常见问题

### 登录后仍 401

- 检查浏览器是否拿到了 `portal_sid`
- 检查 `COOKIE_SECURE` 与实际访问协议是否匹配

### Native chat launch 成功但发消息失败

- 检查 `OPENCODE_BASE_URL / OPENCODE_USERNAME / OPENCODE_PASSWORD`
- 查看 `logs/backend.log`

### `/api/skills` 返回空或 installed 异常

- 检查 `OPENWORK_BASE_URL / OPENWORK_TOKEN`
- 直接访问 OpenWork 确认服务已启动

### 流式请求无返回

- 确认前端使用 `VITE_API_BASE_URL=/`
- 确认浏览器请求走的是 `/api/...` 而不是错误拼接的绝对地址
