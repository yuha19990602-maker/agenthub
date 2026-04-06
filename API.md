# API 参考（V2 当前实现）

Base URL: `http://localhost:8000`

认证方式：`portal_sid`（HTTP-only Cookie，本地 session）

## 1. 系统

### `GET /api/health`

```json
{
  "status": "healthy",
  "portal_name": "AI Portal",
  "version": "2.0.0"
}
```

## 2. 认证

### `GET /api/auth/login-url?next=/`
获取 SSO 登录地址。开发环境且启用 mock-login 时，可能返回 `/api/auth/mock-login?...`。

### `POST /api/auth/exchange`
用 `code/state` 换本地 session。

请求体：

```json
{
  "code": "authorization-code",
  "state": "opaque-state"
}
```

### `GET /api/auth/callback?code=...&state=...`
SSO 后端回调入口，成功后设置 `portal_sid` 并重定向。

### `GET /api/auth/me`
返回当前登录用户信息。

### `POST /api/auth/logout`
删除本地 session 并清除 `portal_sid`。

### `GET /api/auth/mock-login?emp_no=E10001`
仅 `ENV=dev && ENABLE_MOCK_LOGIN=true` 可用。

## 3. 资源

### `GET /api/resources`
返回 ACL 过滤后的资源列表。

### `GET /api/resources/grouped`
按 `group` 分组返回资源。

### `GET /api/resources/{resource_id}`
返回单个资源详情。

### `POST /api/resources/{resource_id}/launch`
启动资源。

native 返回示例：

```json
{
  "kind": "native",
  "portal_session_id": "uuid",
  "adapter": "opencode",
  "mode": "native"
}
```

embedded 返回示例：

```json
{
  "kind": "websdk",
  "portal_session_id": "uuid",
  "launch_id": "uuid",
  "adapter": "websdk",
  "mode": "embedded"
}
```

## 4. 会话

### `GET /api/sessions?limit=50&resource_id=&type=&status=`
返回当前用户会话列表，附带 `adapter` 和 `mode`。

### `GET /api/sessions/{portal_session_id}`
返回单个会话详情。

### `GET /api/sessions/{portal_session_id}/resume`
统一恢复入口。

```json
{
  "portal_session_id": "uuid",
  "resource_id": "general-chat",
  "title": "通用对话",
  "adapter": "opencode",
  "mode": "native",
  "launch_id": null,
  "show_chat_history": true,
  "show_workspace": false
}
```

### `GET /api/sessions/{portal_session_id}/messages`
优先读取 Portal 本地消息；本地为空时，`opencode/skill_chat` 会回源并回填。

### `POST /api/sessions/{portal_session_id}/messages`
非流式发送消息。

请求体：

```json
{ "text": "你好" }
```

响应体：

```json
{ "response": "你好，我可以帮你什么？", "message_id": "uuid" }
```

### `POST /api/sessions/{portal_session_id}/messages/stream`
SSE 流式发送消息。

事件格式：

```text
data: {"type":"start","message_id":"uuid"}
data: {"type":"delta","message_id":"uuid","content":"你"}
data: {"type":"delta","message_id":"uuid","content":"好"}
data: {"type":"done","message_id":"uuid","finish_reason":"stop"}
```

### `POST /api/sessions/{portal_session_id}/archive`
归档会话。

### `POST /api/sessions/{portal_session_id}/upload`
上传文件到 native 会话。`openai_compatible` 当前不支持文件上传。

### `GET /api/sessions/{portal_session_id}/context`
返回 `global < user < user_resource < session` 合并后的上下文。

## 5. Launch / Workspace

### `GET /api/launches`
列出当前用户最近启动记录。

### `GET /api/launches/{launch_id}/embed-config`
返回 WebSDK 嵌入配置。

### `GET /api/launches/{launch_id}/iframe-config`
返回 iframe 嵌入配置。

## 6. Context

### `PATCH /api/contexts/user-resource/{resource_id}`
更新当前用户在指定资源上的 `user_resource` 上下文。

请求体：

```json
{
  "payload": { "tone": "concise" },
  "summary": "用户偏好简洁回答"
}
```

## 7. Skills

### `GET /api/skills`
返回 skill 资源以及 OpenWork 安装状态。

## 8. Admin

### `POST /api/admin/resources/sync?workspace_id=default`
Admin-only。触发从 OpenWork 同步技能并 reload catalog。

## 9. OpenAPI

交互式文档：`/docs`
