# SSO 登录联调与排障文档

本文用于把 AI Portal 从 `dev mock-login` 切到真实 SSO，并在开发环境中自行完成登录联调与问题排查。

适用范围：

- 后端：FastAPI BFF
- 前端：Vite + React
- 认证模式：`OAuth2 / OIDC code flow + 本地 session(cookie: portal_sid)`

## 1. 切换到真实 SSO

编辑 [backend/.env](/home/yy/agenthub/backend/.env)，至少配置为：

```env
ENV=dev
ENABLE_MOCK_LOGIN=false
COOKIE_SECURE=false
SESSION_MAX_AGE_SEC=86400

SSO_AUTHORIZE_URL=https://your-sso.example.com/oauth/authorize
SSO_TOKEN_URL=https://your-sso.example.com/oauth/token
SSO_CLIENT_ID=your-client-id
SSO_CLIENT_SECRET=your-client-secret
SSO_REDIRECT_URI=http://localhost:8000/api/auth/callback
SSO_JWKS_URL=https://your-sso.example.com/.well-known/jwks.json

OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode
OPENCODE_PASSWORD=your-password

OPENWORK_BASE_URL=http://127.0.0.1:8787
OPENWORK_TOKEN=your-token
```

注意：

- `SSO_REDIRECT_URI` 必须和 SSO 平台登记的一致。
- 开发环境如果是 `http://localhost:5173 -> http://localhost:8000`，通常 `COOKIE_SECURE=false`。
- 若你本地前后端都改成 HTTPS，再把 `COOKIE_SECURE=true`。

## 2. 启动方式

后端：

```bash
cd /home/yy/agenthub/backend
/home/yy/python312/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd /home/yy/agenthub/frontend
npm run dev
```

访问：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`

## 3. 标准登录链路

当前代码中的真实链路如下：

1. 前端检测未登录。
2. 前端调用 `GET /api/auth/login-url?next=当前页面路径`
3. 后端生成 `state`，保存到内存存储。
4. 后端返回真实 SSO 的 authorize URL。
5. 浏览器跳转到 SSO 登录页。
6. SSO 登录成功后回跳：

```text
GET /api/auth/callback?code=...&state=...
```

7. 后端执行：
   - 校验 `state`
   - 用 `code` 请求 `SSO_TOKEN_URL`
   - 从 `id_token` 或 `access_token` 提取 JWT
   - 通过 `SSO_JWKS_URL` 验签
   - 解析 `preferred_username / email / sub`
   - 创建本地 `AuthSession`
   - 设置 `portal_sid`
   - 重定向回 `next`

8. 前端重新调用 `GET /api/auth/me`
9. 登录完成

## 4. 关键代码位置

- 登录地址生成：
  [backend/app/auth/routes.py](/home/yy/agenthub/backend/app/auth/routes.py)
- code 换 token / callback：
  [backend/app/auth/routes.py](/home/yy/agenthub/backend/app/auth/routes.py)
- JWT 验签：
  [backend/app/auth/service.py](/home/yy/agenthub/backend/app/auth/service.py)
- 本地 session 读取：
  [backend/app/auth/deps.py](/home/yy/agenthub/backend/app/auth/deps.py)
- 前端鉴权启动：
  [frontend/src/auth/AuthProvider.tsx](/home/yy/agenthub/frontend/src/auth/AuthProvider.tsx)
- 前端跳转登录：
  [frontend/src/api.ts](/home/yy/agenthub/frontend/src/api.ts)

## 5. 联调最小检查步骤

### 5.1 检查 login-url

浏览器或命令行访问：

```bash
curl "http://127.0.0.1:8000/api/auth/login-url?next=/"
```

预期：

- 返回 `login_url`
- URL 指向真实 `SSO_AUTHORIZE_URL`
- query 中包含：
  - `client_id`
  - `redirect_uri`
  - `response_type=code`
  - `scope`
  - `state`

如果这一步就不对，先不要继续查 callback。

### 5.2 检查 SSO 回调

登录后浏览器应命中：

```text
http://localhost:8000/api/auth/callback?code=...&state=...
```

预期：

- 返回 302
- 响应头包含 `Set-Cookie: portal_sid=...`
- `Location` 跳回前端目标页面

### 5.3 检查 me

登录完成后：

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/auth/me
```

预期返回当前用户 JSON。

## 6. 分阶段排障清单

### 问题 A：前端没有跳到 SSO

检查：

1. 前端控制台是否打印了未登录日志。
2. `GET /api/auth/login-url` 是否返回 200。
3. 返回的 `login_url` 是否为空。
4. `frontend/.env` 是否仍然用：

```env
VITE_API_BASE_URL=/
```

常见原因：

- 前端请求没打到后端
- Vite 代理没生效
- `SSO_AUTHORIZE_URL` 为空但又禁用了 mock-login

### 问题 B：SSO 登录成功后没有回到 Portal

检查：

1. SSO 平台登记的 callback URL 是否和 `SSO_REDIRECT_URI` 完全一致。
2. 协议、域名、端口、路径是否逐字一致。
3. 是否把 `localhost` 和 `127.0.0.1` 混用了。

常见原因：

- 回调地址不匹配
- SSO 平台只允许固定域名

### 问题 C：callback 返回 400，提示 invalid state

检查：

1. 浏览器是否真的先调过 `/api/auth/login-url`
2. 中间是否刷新过页面或重复走了一遍 callback
3. 后端是否重启过，导致内存里的 `state` 丢失

说明：

- 当前 `state` 存在内存里，不持久化。
- 只要后端重启，之前发出去的 state 全部失效。

### 问题 D：callback 返回 401，code 换 token 失败

检查：

1. `SSO_TOKEN_URL` 是否正确
2. `SSO_CLIENT_ID / SSO_CLIENT_SECRET` 是否正确
3. `redirect_uri` 是否与 SSO 平台要求一致
4. 授权码是否已被使用过

建议直接看后端日志中 `exchange_code` 阶段报错。

### 问题 E：callback 返回 401，JWT 验签失败

检查：

1. `SSO_JWKS_URL` 是否可访问
2. token 的签名算法是否与当前实现兼容
3. token 的 `aud` 是否等于 `SSO_CLIENT_ID`
4. token 是否过期

建议：

- 先把拿到的 JWT 在本地 decode 看 claims
- 再确认 `kid` 是否能在 JWKS 中找到

当前代码默认会校验 audience，只要填了 `SSO_CLIENT_ID` 就会启用 `aud` 校验。

### 问题 F：callback 成功但 `me` 仍然 401

检查：

1. 浏览器响应头里是否真的有 `Set-Cookie: portal_sid=...`
2. Cookie 是否被浏览器拦截
3. `COOKIE_SECURE` 是否与访问协议匹配
4. 前端和后端使用的域名是否一致

典型坑：

- 页面用 `127.0.0.1` 打开，但 cookie 是在 `localhost` 下发
- 本地 HTTP 却配置了 `COOKIE_SECURE=true`

### 问题 G：callback 成功但返回 403，user not authorized

检查：

1. JWT claims 中是否存在：
   - `preferred_username`
   - `email`
   - `sub`
2. 当前代码会优先用上面三者之一作为本地用户标识
3. 本地用户映射逻辑是否符合你们 SSO 用户名规则

当前默认逻辑：

- `email` 会截掉 `@` 前缀作为 `emp_no`
- `dev` 模式下如查不到用户，会自动创建本地用户
- 若你希望严格校验，需要把 `UserRepository` 改成对接你们真实用户库

### 问题 H：前端显示已跳回首页，但页面仍处于未登录状态

检查：

1. 浏览器 Network 中 `/api/auth/me` 的响应码
2. 是否返回 401
3. 是否存在跨域 cookie 没带上的情况
4. 前端是否使用了错误的 API base URL

建议：

- 本地开发优先使用 `VITE_API_BASE_URL=/`
- 让请求走 Vite 代理

## 7. 浏览器侧建议观察项

打开浏览器开发者工具，重点看：

- `Network -> /api/auth/login-url`
- `Network -> /api/auth/callback`
- `Network -> /api/auth/me`
- `Application -> Cookies`

确认：

- `portal_sid` 是否存在
- 域名是否正确
- `Path` 是否为 `/`
- `HttpOnly` 是否已开启

## 8. 命令行辅助检查

### 获取 login-url

```bash
curl "http://127.0.0.1:8000/api/auth/login-url?next=/"
```

### 检查健康状态

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:5173/api/health
```

### 检查 JWKS 可访问性

```bash
curl "https://your-sso.example.com/.well-known/jwks.json"
```

### 登录完成后检查 me

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/auth/me
```

## 9. 生产环境额外要求

切到生产前，必须满足：

```env
ENV=prod
ENABLE_MOCK_LOGIN=false
COOKIE_SECURE=true
```

并且：

- `SSO_AUTHORIZE_URL` 不能为空
- `SSO_TOKEN_URL` 不能为空
- `SSO_CLIENT_ID` 不能为空
- `SSO_CLIENT_SECRET` 不能为空

否则启动校验会直接失败。

## 10. 最后的排查顺序建议

按这个顺序排最省时间：

1. `login-url` 返回是否正确
2. callback URL 是否匹配
3. token exchange 是否成功
4. JWT 验签是否成功
5. `portal_sid` 是否真正下发
6. `/api/auth/me` 是否成功
7. 前端是否带上 cookie

如果你们后续要把“本地用户映射”改成真实用户库校验，建议单独把 `UserRepository` 拆成数据库或 LDAP 接口，而不是继续保留 dev 自动创建逻辑。
