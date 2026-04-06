# AI Portal V2 升级迁移指南

## 概述

本次升级将系统从 V1 (JWT Cookie + Mock SSO) 升级到 V2 (SSO OAuth2 + 本地 Session)，主要改进包括：

- **鉴权体系**：JWT → Server-side Session (portal_sid cookie)
- **存储层**：Redis/Memory 双轨 → Memory 主实现
- **新增资源类型**：`openai_compatible_v1` 原生聊天资源
- **流式协议统一**：SSE 事件标准化 (start/delta/done/error)
- **会话恢复闭环**：新增 `/api/sessions/{id}/resume` 端点

---

## 一、鉴权系统 (SSO)

### 1.1 架构变更

| 项目 | V1 (旧) | V2 (新) |
|------|---------|---------|
| 鉴权方式 | JWT Cookie (`access_token`) | Server-side Session (`portal_sid`) |
| 用户标识 | 从 JWT payload 解码 | 从本地 Session 存储查询 |
| Mock 登录 | `GET /api/auth/mock-login?emp_no=xxx` | 同上，但仅在 `ENV=dev && ENABLE_MOCK_LOGIN=true` 时可用 |
| SSO 流程 | 未实现 | OAuth2 授权码流程完整支持 |
| Token 刷新 | JWT 自动过期 | Session 自动续期 (last_seen_at) |

### 1.2 核心模型

```python
# AuthSession - 本地会话模型 (V2 新增)
class AuthSession(BaseModel):
    session_id: str          # portal_sid cookie 值
    user_id: str             # 用户 ID (emp_no)
    user_name: str           # SSO 用户名
    roles: list[str]         # 角色列表
    expires_at: int          # 过期时间戳 (秒)
    created_at: int          # 创建时间戳
    last_seen_at: int        # 最后访问时间
    sso_access_token: str | None  # SSO 访问令牌 (可选)
    id_token_claims: dict    # ID Token  claims
```

### 1.3 API 端点变更

| 端点 | V1 | V2 | 说明 |
|------|----|----|----|
| 登录入口 | `/api/auth/mock-login` | `/api/auth/login-url` | 返回 SSO 授权 URL |
| 回调处理 | 直接 mock 登录 | `/api/auth/exchange` | 用 code 换 session |
| 获取用户 | `/api/auth/me` | `/api/auth/me` | 不变，但依赖 portal_sid |
| 登出 | `/api/auth/logout` | `/api/auth/logout` | 清除 portal_sid |

### 1.4 依赖注入变更

```python
# V1
from app.auth.deps import CurrentUser, OptionalUser

# V2
from app.auth.deps import SessionUser, OptionalUser, AdminUser

# 使用示例
@app.get("/api/resources")
async def list_resources(user: SessionUser):  # 必须登录
    ...

@app.post("/api/admin/resources/sync")
async def admin_sync(user: AdminUser):  # 必须 admin 角色
    ...
```

### 1.5 后续配置指南

#### 方案 A：开发环境 (Fake SSO)

适用于本地开发，无需真实 SSO 服务：

```bash
# backend/.env
ENV=dev
ENABLE_MOCK_LOGIN=true
COOKIE_SECURE=false

# SSO 端点留空，自动启用 Fake SSO
SSO_AUTHORIZE_URL=
SSO_TOKEN_URL=
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=
```

访问时系统自动以 `E10001` 测试用户登录。

#### 方案 B：企业 SSO (OIDC/OAuth2)

适用于对接企业统一认证：

```bash
# backend/.env
ENV=prod
ENABLE_MOCK_LOGIN=false
COOKIE_SECURE=true

# SSO 配置
SSO_AUTHORIZE_URL=https://sso.company.com/oauth/authorize
SSO_TOKEN_URL=https://sso.company.com/oauth/token
SSO_CLIENT_ID=your-client-id
SSO_CLIENT_SECRET=your-client-secret
SSO_REDIRECT_URI=https://portal.company.com/api/auth/callback
SSO_JWKS_URL=https://sso.company.com/.well-known/jwks.json
```

**对接流程**：
1. 用户在浏览器访问 Portal
2. 前端检测到未登录，重定向到 `SSO_AUTHORIZE_URL`
3. 用户在 SSO 页面登录并授权
4. SSO 重定向回 `SSO_REDIRECT_URI` (带 `code` 和 `state`)
5. 后端用 `code` 调用 `SSO_TOKEN_URL` 换取 token
6. 验证 token，提取用户信息，创建本地 session
7. 设置 `portal_sid` cookie，返回用户信息给前端

#### 方案 C：混合模式 (推荐过渡方案)

生产环境也保留 mock-login 作为应急回退：

```bash
ENV=prod
ENABLE_MOCK_LOGIN=true  # 仅内网 IP 可访问
COOKIE_SECURE=true

# 同时配置真实 SSO
SSO_AUTHORIZE_URL=https://sso.company.com/...
```

---

## 二、资源系统 (Resources)

### 2.1 新增资源类型

V2 新增 `openai_compatible_v1` 资源类型：

```json
{
  "id": "my-llm-model",
  "name": "自定义大模型",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "模型资源",
  "config": {
    "base_url": "https://api.provider.com/v1",
    "request_path": "/chat/completions",
    "api_key_env": "LLM_API_KEY",
    "model": "qwen-plus",
    "default_params": {
      "temperature": 0.7,
      "max_tokens": 2048
    },
    "headers": {
      "X-Custom-Header": "value"
    },
    "history_window": 20,
    "stream_supported": true,
    "timeout_sec": 120
  }
}
```

### 2.2 资源类型对照表

| 资源类型 | launch_mode | adapter | 适用场景 |
|----------|-------------|---------|----------|
| `direct_chat` | native | opencode | 通用对话 (OpenCode) |
| `skill_chat` | native | skill_chat | 技能对话 (OpenCode + skill) |
| `openai_compatible_v1` | native | openai_compatible | OpenAI 兼容 API |
| `kb_websdk` | websdk | websdk | 知识库嵌入 |
| `agent_websdk` | websdk | websdk | Agent 应用嵌入 |
| `iframe` | iframe | iframe | 第三方页面嵌入 |

### 2.3 资源配置文件

V2 资源配置文件位置：`config/resources.generated.json`

```json
[
  {
    "id": "general-chat",
    "name": "通用对话",
    "type": "direct_chat",
    "adapter": "opencode",
    "launch_mode": "native",
    "group": "基础功能",
    "description": "通用 AI 对话",
    "enabled": true,
    "config": {
      "workspace_id": "default",
      "model": "gpt-3.5-turbo"
    },
    "acl": {
      "allowed_roles": ["employee"],
      "allowed_depts": ["Engineering", "Product"]
    }
  }
]
```

### 2.4 Adapter 分发逻辑

V2 明确区分 `resource.type`、`launch_mode` 和 `adapter`：

```python
def _get_adapter_for_resource(resource: Resource) -> str:
    # 优先级：resource.adapter > 类型映射
    if resource.adapter:
        return resource.adapter
    
    type_adapter_map = {
        ResourceType.DIRECT_CHAT: "opencode",
        ResourceType.SKILL_CHAT: "skill_chat",
        ResourceType.KB_WEBSDK: "websdk",
        ResourceType.AGENT_WEBSDK: "websdk",
        ResourceType.IFRAME: "iframe",
        ResourceType.OPENAI_COMPATIBLE_V1: "openai_compatible",
    }
    return type_adapter_map.get(resource.type, "opencode")
```

---

## 三、技能系统 (Skill)

### 3.1 技能资源管理

V2 技能发现流程：

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  OpenWork API   │────▶│  Catalog Service │────▶│  resources.json │
│  (技能列表)      │     │  (merge & filter)│     │  (本地配置)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  Portal 内存加载  │
                       └──────────────────┘
```

### 3.2 管理员同步接口

V2 强制要求 admin 角色：

```python
@app.post("/api/admin/resources/sync")
async def admin_sync_resources(
    workspace_id: str = Query("default"),
    user: AdminUser = None,  # 必须是 admin
):
    ...
```

调用方式：
```bash
curl -X POST "http://localhost:8000/api/admin/resources/sync?workspace_id=default" \
  -H "Cookie: portal_sid=xxx"
```

### 3.3 技能状态查询

```python
@app.get("/api/skills")
async def list_skills(user: SessionUser):
    """列出所有技能及安装状态"""
    ...
```

---

## 四、配置清单

### 4.1 后端配置 (backend/.env)

```bash
# ============ 环境 ============
ENV=dev  # dev | prod

# ============ 服务器 ============
PORT=8000
HOST=0.0.0.0
RELOAD=true

# ============ 鉴权 ============
ENABLE_MOCK_LOGIN=true        # 开发环境启用
COOKIE_SECURE=false           # 生产环境必须为 true
SESSION_MAX_AGE_SEC=86400

# SSO 配置 (生产环境必填)
SSO_AUTHORIZE_URL=
SSO_TOKEN_URL=
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=
SSO_REDIRECT_URI=http://localhost:8000/api/auth/callback
SSO_JWKS_URL=

# ============ OpenCode ============
OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode
OPENCODE_PASSWORD=

# ============ OpenWork ============
OPENWORK_BASE_URL=http://127.0.0.1:8787
OPENWORK_TOKEN=

# ============ Portal ============
PORTAL_NAME=AI Portal
RESOURCES_PATH=config/resources.generated.json

# ============ 日志 ============
LOG_LEVEL=INFO
```

### 4.2 前端配置 (frontend/.env)

```bash
# 开发环境 - 使用 Vite 代理
VITE_API_BASE_URL=/

# 生产环境 - 直接访问后端
# VITE_API_BASE_URL=https://portal.company.com

VITE_APP_NAME=AI Portal
```

### 4.3 资源配置 (config/resources.generated.json)

见上文 2.3 节。

---

## 五、迁移检查清单

### 从 V1 迁移到 V2

- [ ] 更新 `backend/.env`，添加 SSO 相关配置
- [ ] 更新 `frontend/.env`，修改 `VITE_API_BASE_URL=/`
- [ ] 更新资源文件，为需要 `adapter` 的资源显式设置
- [ ] 删除 Redis 相关配置 (可选，已废弃)
- [ ] 重启后端服务，验证 `/api/health` 返回 2.0.0
- [ ] 测试登录流程，验证 `portal_sid` cookie 设置
- [ ] 测试消息发送，验证流式响应正常

---

## 六、故障排查

### Q: 消息发送失败
A: 检查：
1. 浏览器 F12 Network 是否有 CORS 错误
2. `VITE_API_BASE_URL` 是否为 `/` (开发环境)
3. 后端日志是否有 `/api/sessions/{id}/messages/stream` 请求

### Q: 无法登录 / 循环刷新
A: 检查：
1. `COOKIE_SECURE` 与协议是否匹配 (HTTPS=true, HTTP=false)
2. 访问地址是否为 `localhost` 而非 `127.0.0.1`
3. `ENV=dev` 时 Fake SSO 是否启用

### Q: 资源不显示
A: 检查：
1. `config/resources.generated.json` 是否存在且格式正确
2. 用户角色是否有资源 ACL 访问权限
3. 后端日志 `Loaded X resources`

---

## 七、文件变更汇总

### 新增文件
- `backend/app/auth/fake_sso.py` - Fake SSO 服务
- `frontend/src/auth/DevAutoLogin.tsx` - 开发自动登录
- `frontend/src/auth/ProtectedRoute.tsx` - 路由守卫

### 重大修改
- `backend/app/auth/routes.py` - SSO OAuth2 流程
- `backend/app/auth/deps.py` - SessionUser 依赖
- `backend/app/auth/service.py` - 本地会话管理
- `backend/app/store/memory_store.py` - AuthSession 存储
- `backend/app/main.py` - 流式协议统一
- `frontend/src/api.ts` - V2 API 调用
- `frontend/src/auth/AuthProvider.tsx` - 认证上下文

### 废弃文件
- Redis 存储 (`backend/app/store/redis_store.py`) - 仍保留但默认不使用

---

**版本**: 2.0.0  
**更新日期**: 2026-04-06
