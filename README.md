# AI Portal（统一入口）

AI Portal 是一个面向企业内部场景的统一 AI 门户，当前代码已收敛到 V2 结构：

- 认证：`SSO code + 本地 session(cookie: portal_sid)`，开发环境可选 mock-login
- 存储：`MemoryStore` 为默认主实现
- 原生会话：`direct_chat / skill_chat / openai_compatible_v1`
- 嵌入会话：`kb_websdk / agent_websdk / iframe`
- 恢复链路：统一通过 `SessionBinding.adapter` 和 `/api/sessions/{id}/resume`
- 流式协议：统一 SSE `start / delta / done / error`

## 当前架构

```text
[SSO / Dev Mock Login]
          │
          ▼
      [Portal Web UI] (Vite + React)
          │
          ▼
     [FastAPI BFF]
   ├─ Auth / ACL / Catalog
   ├─ Session Center
   ├─ Launch Record Center
   ├─ Context Merge
   ├─ OpenCodeAdapter
   ├─ SkillChatAdapter
   ├─ OpenAICompatibleAdapter
   ├─ WebSDKAdapter
   ├─ IframeAdapter
   └─ OpenWorkAdapter
          │
   ┌──────┼───────────────┐
   ▼      ▼               ▼
OpenCode  OpenWork        WebSDK / Iframe Apps
```

## 本地联调状态

本机已验证以下链路可用：

- `OpenCode`: `http://127.0.0.1:4096`
- `OpenWork`: `http://127.0.0.1:8787`
- Portal Backend: `http://127.0.0.1:8000`
- Portal Frontend: `http://127.0.0.1:5173`

已实测通过：

- dev mock-login 获取 `portal_sid`
- `/api/skills` 访问 OpenWork
- `general-chat` launch
- OpenCode 非流式消息
- OpenCode 流式消息
- 前端 Vite 代理 `http://127.0.0.1:5173/api/health`

## 快速启动

### 1. 配置后端

后端配置文件：`backend/.env`

典型本地开发配置：

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

- 若 `ENV=dev` 且 `ENABLE_MOCK_LOGIN=true`，未配置真实 SSO 时会回落到 dev mock-login。
- 若切到真实 SSO，填入 `SSO_AUTHORIZE_URL / SSO_TOKEN_URL / SSO_CLIENT_ID / SSO_CLIENT_SECRET / SSO_JWKS_URL` 即可。
- 非 `dev` 环境下，启动时会强校验 `COOKIE_SECURE=true` 且必须关闭 mock-login。

### 2. 配置前端

前端配置文件：`frontend/.env`

推荐本地开发配置：

```env
VITE_API_BASE_URL=/
VITE_APP_NAME=AI Portal
```

这会走 Vite 代理，避免本地 CORS 和 URL 拼接问题。

### 3. 启动 Portal

```bash
./scripts/start.sh
```

或分别启动：

```bash
cd backend
/home/yy/python312/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

cd frontend
npm run dev
```

访问地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

## 资源类型与 adapter

| 资源类型 | launch_mode | adapter | 用途 |
|---|---|---|---|
| `direct_chat` | `native` | `opencode` | 通用原生聊天 |
| `skill_chat` | `native` | `skill_chat` | skill 对话 |
| `openai_compatible_v1` | `native` | `openai_compatible` | OpenAI 兼容模型 |
| `kb_websdk` | `websdk` | `websdk` | 知识库 WebSDK |
| `agent_websdk` | `websdk` | `websdk` | Agent WebSDK |
| `iframe` | `iframe` | `iframe` | 第三方 iframe 应用 |

## 会话恢复与流式协议

### 会话恢复

- Native / Embedded 会话都持久化为 `PortalSession`
- 恢复统一调用：`GET /api/sessions/{portal_session_id}/resume`
- adapter 以 `SessionBinding.adapter` 为唯一可信来源

### 流式协议

统一 SSE 事件：

```text
data: {"type":"start","message_id":"..."}
data: {"type":"delta","message_id":"...","content":"..."}
data: {"type":"done","message_id":"...","finish_reason":"stop"}
```

若流异常关闭且未收到 `done`，前端会按错误处理，不会误判为成功完成。

## 资源配置样例

当前默认加载：`config/resources.generated.json`

`openai_compatible_v1` 示例：

```json
{
  "id": "openai-compatible-demo",
  "name": "OpenAI 兼容模型",
  "type": "openai_compatible_v1",
  "launch_mode": "native",
  "adapter": "openai_compatible",
  "group": "模型资源",
  "description": "通过 OpenAI Compatible API 访问的模型",
  "enabled": true,
  "config": {
    "base_url": "https://api.openai.com/v1",
    "request_path": "/chat/completions",
    "api_key_env": "OPENAI_API_KEY",
    "model": "gpt-4o-mini",
    "default_params": {
      "temperature": 0.7,
      "max_tokens": 2048
    },
    "headers": {
      "X-Portal-Source": "agenthub"
    },
    "history_window": 20,
    "stream_supported": true,
    "timeout_sec": 120
  }
}
```

## 测试

后端快速测试：

```bash
cd backend
/home/yy/python312/bin/python tests/test_api_simple.py
```

前端构建检查：

```bash
cd frontend
npm run build
```

## 文档

- [API.md](API.md)
- [QUICKSTART_V2.md](QUICKSTART_V2.md)
- [docs/SSO_LOGIN_DEBUG_GUIDE.md](docs/SSO_LOGIN_DEBUG_GUIDE.md)
- [V2_MIGRATION_GUIDE.md](V2_MIGRATION_GUIDE.md)
- [V2_ADVANCED_CONFIGURATION.md](V2_ADVANCED_CONFIGURATION.md)
