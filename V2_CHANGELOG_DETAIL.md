# AI Portal V1.5 → V2.0 详细版本更新说明

> **版本**: v2.0.0 (Opt Codex)  
> **发布日期**: 2026-04-06  
> **变更范围**: 57个文件，+5,357行/-1,001行

---

## 📋 版本概览

V2.0 是 AI Portal 的重大版本升级，主要包含以下核心改进：

1. **认证系统重构**: JWT → 服务器端会话 + OAuth2 SSO
2. **新增 OpenAI 兼容适配器**: 支持标准 OpenAI API 格式
3. **四层数据模型**: PortalSession / LaunchRecord / SessionBinding / PortalMessage
4. **V2 配置体系**: 三层资源配置 (static + overrides + generated)
5. **Fake SSO 开发模式**: 无需真实 SSO 即可开发测试
6. **前端认证模块**: 完整的 React 认证上下文体系

---

## 🔧 后端模块变更

### 1. 配置模块 (`backend/app/config.py`)

#### 新增配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `env` | str | `dev` | 运行环境标识 |
| `enable_mock_login` | bool | `false` | 启用开发Mock登录 |
| `cookie_secure` | bool | `false` | Cookie安全标志 |
| `session_max_age_sec` | int | `86400` | 会话有效期(24小时) |
| `sso_authorize_url` | str | `""` | SSO授权端点 |
| `sso_token_url` | str | `""` | SSO令牌端点 |
| `sso_client_id` | str | `""` | SSO客户端ID |
| `sso_client_secret` | str | `""` | SSO客户端密钥 |
| `sso_redirect_uri` | str | `http://localhost:8000/api/auth/callback` | 回调地址 |
| `sso_jwks_url` | str | `""` | SSO公钥集URL |

#### 废弃配置项 (向后兼容但忽略)

| 配置项 | 说明 |
|--------|------|
| `use_redis` | Redis支持已废弃，强制使用内存存储 |
| `jwt_secret` | JWT认证已废弃，使用服务器端会话 |
| `auth_mock_fallback_enabled` | 旧Mock回退机制废弃 |

#### 新增函数

```python
def validate_startup():
    """启动时验证关键配置（生产环境强制检查）"""
    # 检查点:
    # 1. 非dev环境禁止enable_mock_login
    # 2. 非dev环境必须使用HTTPS (cookie_secure)
    # 3. SSO配置完整性检查
```

---

### 2. 数据模型 (`backend/app/models.py`)

#### 新增枚举值

```python
class ResourceType(str, Enum):
    # ... 原有类型
    OPENAI_COMPATIBLE_V1 = "openai_compatible_v1"  # 新增
```

#### Resource 模型变更

```python
class Resource(BaseModel):
    # ... 原有字段
    adapter: Optional[str] = Field(None, description="Adapter name for dispatch")  # 新增
```

#### SessionBinding 模型变更

```python
class SessionBinding(BaseModel):
    # engine_type 扩展支持: opencode, websdk, iframe, openai_compatible
    engine_type: str = Field(..., description="Engine type: opencode, websdk, iframe, openai_compatible")
```

#### PortalMessage 模型扩展 (V2字段)

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `status` | str | 消息状态: streaming/done/error |
| `dedupe_key` | Optional[str] | 去重键 |
| `source_provider` | Optional[str] | 来源: opencode/openai_compatible/backfill |
| `source_message_id` | Optional[str] | 源消息ID |
| `seq` | int | 排序序号 |

#### ContextScope 模型扩展

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `updated_by` | Optional[str] | 最后更新者 |
| `version` | int | 上下文版本 |

#### 新增 V2 核心模型

##### AuthSession (认证会话)
```python
class AuthSession(BaseModel):
    session_id: str           # Portal session ID (portal_sid cookie)
    user_id: str              # 用户ID
    user_name: str            # SSO登录名
    roles: List[str]          # 用户角色
    expires_at: int           # 过期时间戳
    created_at: int           # 创建时间戳
    last_seen_at: int         # 最后活动时间
    sso_access_token: Optional[str]  # SSO访问令牌
    id_token_claims: Dict[str, Any]  # ID令牌声明
```

##### SessionResumePayload (会话恢复载荷)
```python
class SessionResumePayload(BaseModel):
    portal_session_id: str    # Portal会话ID
    resource_id: str          # 资源ID
    title: str                # 会话标题
    adapter: str              # 适配器名称
    mode: str                 # 模式: native/embedded
    launch_id: Optional[str]  # 启动ID(embedded模式)
    show_chat_history: bool   # 是否显示聊天记录
    show_workspace: bool      # 是否显示工作区
```

##### OAuthState (OAuth状态)
```python
class OAuthState(BaseModel):
    state: str                # 状态参数
    next_url: str             # 登录后跳转
    code_verifier: Optional[str]  # PKCE验证码
    expires_at: int           # 过期时间戳
```

---

### 3. 认证模块重构

#### 3.1 依赖注入 (`backend/app/auth/deps.py`)

**V1 依赖 (废弃)**:
```python
CurrentUser = Annotated[UserCtx, Depends(get_current_user)]
OptionalUser = Annotated[Optional[UserCtx], Depends(get_optional_user)]
```

**V2 依赖 (新增)**:
```python
# 从服务器端会话获取用户
SessionUser = Annotated[UserCtx, Depends(get_session_user)]
OptionalUser = Annotated[Optional[UserCtx], Depends(get_optional_user)]
AdminUser = Annotated[UserCtx, Depends(get_admin_user)]  # 管理员权限
```

**关键变更**:
- 认证来源从 JWT Cookie (`access_token`) 改为服务器端会话 (`portal_sid`)
- 新增 `get_session_user()` 从内存存储查询 AuthSession
- 新增 `validate_session()` 会话有效性验证

#### 3.2 认证服务 (`backend/app/auth/service.py`)

**完整重构**: 从 Mock JWT 改为 SSO OAuth2 + Local Session

| 新组件 | 说明 |
|--------|------|
| `UserRepository` | 用户仓储，支持自动创建用户(dev模式) |
| `SSOService` | SSO OAuth2 服务，处理授权码交换 |
| `SessionService` | 本地会话管理，创建/验证/销毁会话 |

**关键方法**:

```python
class SSOService:
    async def exchange_code(self, code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        """交换授权码获取访问令牌"""
        
    def verify_jwt(self, token: str) -> Dict[str, Any]:
        """验证JWT令牌 (支持JWKS)"""

class SessionService:
    async def create_session(self, user: UserCtx, sso_tokens: Optional[Dict] = None) -> AuthSession:
        """创建服务器端会话"""
        
    async def validate_session(self, session_id: str) -> Optional[AuthSession]:
        """验证会话有效性"""
        
    async def destroy_session(self, session_id: str) -> bool:
        """销毁会话(登出)"""
```

#### 3.3 Fake SSO 服务 (`backend/app/auth/fake_sso.py`) **[新增文件]**

用于开发环境模拟 SSO 流程，无需真实 SSO 基础设施。

```python
class FakeSSOService:
    def issue_authorization_code(self, next_url: str = "/") -> str:
        """发放伪造授权码"""
        
    def build_authorize_url(self, redirect_uri: str, state: str, next_url: str = "/") -> str:
        """构建授权URL(立即重定向回回调地址)"""
        
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """接受任意授权码，返回伪造令牌"""
        
    def verify_jwt(self, token: str) -> Dict[str, Any]:
        """验证伪造JWT(无签名验证)"""
```

**警告**: 仅用于开发测试，生产环境禁用。

#### 3.4 认证路由 (`backend/app/auth/routes.py`)

**新增端点**:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login-url` | GET | 获取SSO登录URL |
| `/api/auth/callback` | GET | OAuth2回调处理 |
| `/api/auth/exchange` | POST | 交换授权码获取会话 |
| `/api/auth/session` | GET | 获取当前会话信息 |
| `/api/auth/mock-login` | GET | 开发环境Mock登录 |

**废弃端点**:

| 端点 | 说明 |
|------|------|
| `/api/auth/me` (旧版) | 改用 `/api/auth/session` |

**登录流程变化**:

```
V1 流程:
Frontend → POST /api/auth/mock-login → JWT Cookie

V2 流程:
Frontend → GET /api/auth/login-url → Redirect to SSO
       ← Callback to /api/auth/callback ←
       → POST /api/auth/exchange → Session Cookie (portal_sid)
```

---

### 4. 存储模块 (`backend/app/store/`)

#### 4.1 MemoryStore 大幅扩展 (`backend/app/store/memory_store.py`)

**V2 定位**: 从"Redis替代方案"升级为"主存储实现"

**新增存储类型**:

| 存储 | 类型 | 说明 |
|------|------|------|
| `_auth_sessions` | Dict[str, AuthSession] | 认证会话存储 |
| `_oauth_states` | Dict[str, tuple] | OAuth状态临时存储 |
| `_message_dedupe` | Dict[str, str] | 消息去重索引 |

**新增索引**:

```python
# 上下文作用域索引
self._context_scopes: Dict[str, List[str]] = defaultdict(list)
```

**新增方法**:

```python
# 认证会话操作
async def save_auth_session(self, session: AuthSession) -> bool
async def get_auth_session(self, session_id: str) -> Optional[AuthSession]
async def delete_auth_session(self, session_id: str) -> bool

# OAuth状态操作  
async def save_oauth_state(self, state: str, next_url: str, expires_at: int, code_verifier: Optional[str] = None) -> bool
async def get_oauth_state(self, state: str) -> Optional[tuple]
async def delete_oauth_state(self, state: str) -> bool

# 消息去重
async def dedupe_message(self, dedupe_key: str, message_id: str) -> bool

# 并发控制
# 所有写操作添加 asyncio.Lock() 保护
```

**线程安全改进**:
```python
async with self._lock:
    # 所有写操作
```

#### 4.2 存储初始化 (`backend/app/store/__init__.py`)

**变更**: 移除 Redis 支持，强制使用 MemoryStore

```python
# V1
if settings.use_redis:
    from .redis_store import RedisStore
    store = RedisStore()
else:
    from .memory_store import MemoryStore
    store = MemoryStore()

# V2
from .memory_store import MemoryStore
store = MemoryStore()  # 强制内存存储
```

---

### 5. 适配器模块

#### 5.1 新增 OpenAI 兼容适配器 (`backend/app/adapters/openai_compatible.py`) **[新增文件]**

支持标准 OpenAI API 格式的后端服务。

```python
class OpenAICompatibleAdapter:
    async def send_message(
        self,
        resource: Resource,
        history: List[PortalMessage],
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """非流式消息发送"""
        
    async def send_message_stream(
        self,
        resource: Resource,
        history: List[PortalMessage],
        text: str,
        context: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """流式消息发送(SSE)"""
```

**配置支持**:
```python
class ResourceConfig(BaseModel):
    # OpenAI Compatible v1 config
    request_path: str = "/chat/completions"
    api_key_env: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    default_params: Dict[str, Any] = Field(default_factory=dict)
    history_window: int = 20
    stream_supported: bool = True
    timeout_sec: int = 120
```

#### 5.2 适配器注册表 (`backend/app/main.py`)

**新增机制**:
```python
adapter_registry = {
    "opencode": opencode_adapter,
    "skill_chat": skill_chat_adapter,
    "websdk": websdk_adapter,
    "iframe": iframe_adapter,
    "openai_compatible": openai_compatible_adapter,
}

def _get_adapter_for_resource(resource: Resource) -> str:
    """
    从资源确定适配器名称
    优先级: resource.adapter > resource.type 映射
    """
```

#### 5.3 适配器基类扩展 (`backend/app/adapters/base.py`)

**新增方法签名**:
```python
class ExecutionAdapter(ABC):
    @abstractmethod
    async def send_message_stream(
        self, session_id, message, trace_id
    ) -> AsyncIterator[str]:
        """流式消息返回"""
```

---

### 6. 目录服务 (`backend/app/catalog/`)

#### 6.1 同步服务 (`backend/app/catalog/sync_service.py`) **[新增文件]**

```python
class ResourceSyncService:
    async def sync_from_openwork(self, workspace_id: str = "default") -> int:
        """从OpenWork同步技能到Portal"""
        
    def _skill_to_resource(self, skill: Dict) -> Resource:
        """将OpenWork技能转换为Portal资源"""
```

#### 6.2 目录服务增强 (`backend/app/catalog/service.py`)

```python
def get_resource_or_raise(self, resource_id: str) -> Resource:
    """获取资源或抛出404"""
    
def reload_resources(self) -> int:
    """重新加载资源(支持热更新)"""
```

---

### 7. ACL 服务 (`backend/app/acl/service.py`)

**新增方法**:
```python
def require_resource_access(self, resource: Resource, user: UserCtx) -> None:
    """强制检查资源访问权限，无权限则抛出HTTPException"""
```

---

### 8. 主应用 (`backend/app/main.py`)

#### 8.1 生命周期变更

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 新增: 启动配置验证
    validate_startup()
    
    # 打印信息更新
    print(f"🔐 Auth: Server-side session (Redis deprecated)")
```

#### 8.2 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/sessions/{id}` | GET | 获取会话详情(富化) |
| `/api/sessions/{id}/archive` | POST | 归档会话 |
| `/api/sessions/{id}/context` | GET | 获取会话合并上下文 |
| `/api/resources/grouped` | GET | 分组资源列表 |
| `/api/admin/resources/sync` | POST | 触发资源同步 |
| `/api/contexts/user-resource/{resource_id}` | PATCH | 更新用户-资源上下文 |

#### 8.3 SSE 流式格式更新

```python
class StreamMessageChunk(BaseModel):
    # V1 格式: type: "chunk" | "done" | "error"
    # V2 格式: type: "start" | "delta" | "done" | "error"
    type: str
    content: Optional[str] = None
    message_id: Optional[str] = None
    finish_reason: Optional[str] = None  # 新增
```

#### 8.4 新增帮助函数

```python
async def _get_session_or_404(portal_session_id: str, user) -> PortalSession:
    """获取会话或404"""

async def _get_active_binding(portal_session_id: str) -> SessionBinding:
    """获取活跃绑定"""

def _get_resource_or_404(resource_id: str) -> Resource:
    """获取资源或404"""

def _require_resource_access(resource: Resource, user) -> None:
    """强制ACL检查"""

def _get_adapter_for_resource(resource: Resource) -> str:
    """获取资源适配器"""

async def _save_portal_message(...) -> PortalMessage:
    """保存Portal消息(带去重)"""
```

---

## 🎨 前端模块变更

### 1. 认证模块重构 (`frontend/src/auth/`) **[新增目录]**

#### 1.1 AuthProvider.tsx

```typescript
interface AuthContextValue {
  user: UserCtx | null;
  loading: boolean;
  error: string | null;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

// 自动处理 OAuth2 回调
// 检查 URL 中的 code/state 参数
// 自动交换授权码获取会话
```

#### 1.2 ProtectedRoute.tsx

```typescript
// 保护路由，未登录重定向到登录页
// 支持自动跳回原页面 (?next=)
```

#### 1.3 DevAutoLogin.tsx

```typescript
// 开发环境自动登录组件
// 仅在 enable_mock_login 时显示
```

#### 1.4 auth/index.ts

```typescript
// 统一导出认证模块
export { AuthProvider, useAuth } from './AuthProvider';
export { ProtectedRoute } from './ProtectedRoute';
export { DevAutoLogin } from './DevAutoLogin';
```

#### 1.5 前端认证流程

```
App 加载
  ↓
AuthProvider.bootstrap()
  ↓
检查 URL 是否有 code 参数?
  ├── 是 → authApi.exchangeCode(code, state)
  │         → 设置用户状态 → 清理 URL
  │
  └── 否 → authApi.getMe()
            → 检查现有会话
```

### 2. API 客户端 (`frontend/src/api.ts`)

#### 新增认证 API

```typescript
export const authApi = {
  // V2 新增
  getLoginUrl: () => axios.get(`${API_BASE}/auth/login-url`),
  exchangeCode: (code: string, state: string | null) => 
    axios.post(`${API_BASE}/auth/exchange`, { code, state }),
  getSession: () => axios.get(`${API_BASE}/auth/session`),
  
  // 保留
  getMe: () => axios.get(`${API_BASE}/auth/session`), // 别名
  logout: () => axios.post(`${API_BASE}/auth/logout`),
  mockLogin: (empNo: string) => axios.get(`${API_BASE}/auth/mock-login?emp_no=${empNo}`),
};
```

#### 新增会话 API

```typescript
export const sessionsApi = {
  // V2 新增
  getSession: (id: string) => axios.get(`${API_BASE}/sessions/${id}`),
  archiveSession: (id: string) => axios.post(`${API_BASE}/sessions/${id}/archive`),
  getSessionContext: (id: string) => axios.get(`${API_BASE}/sessions/${id}/context`),
  
  // 保留
  listSessions: (...) => ...,
  getMessages: (...) => ...,
  sendMessage: (...) => ...,
  sendMessageStream: (...) => ...,
};
```

### 3. 类型定义 (`frontend/src/types.ts`)

#### 新增 V2 类型

```typescript
// 会话恢复载荷
export interface SessionResumePayload {
  portal_session_id: string;
  resource_id: string;
  title: string;
  adapter: string;
  mode: 'native' | 'embedded';
  launch_id?: string;
  show_chat_history: boolean;
  show_workspace: boolean;
}

// 资源扩展
export interface Resource {
  // ... 原有字段
  adapter?: string;  // 新增
}

// 消息扩展
export interface Message {
  // ... 原有字段
  status?: 'streaming' | 'done' | 'error';  // 新增
  seq?: number;  // 新增
}
```

### 4. 主应用 (`frontend/src/App.tsx`)

#### V2 架构变化

```typescript
function App() {
  return (
    <AuthProvider>          {/* 新增: 认证上下文 */}
      <Router>
        <Routes>
          <Route path="/" element={
            <ProtectedRoute>  {/* 新增: 路由保护 */}
              <Layout />
            </ProtectedRoute>
          } />
        </Routes>
      </Router>
    </AuthProvider>
  );
}
```

### 5. 组件更新

#### 5.1 SessionSidebar.tsx

- 新增归档功能
- 优化会话列表加载

#### 5.2 ChatInterface.tsx

- 适配新的 SSE 消息格式 (`start`/`delta`/`done`)
- 支持消息状态显示

#### 5.3 ResourceSidebar.tsx

- 新增分组折叠动画
- 优化资源加载

---

## 📝 配置文件变更

### 1. 三层资源配置体系

#### 1.1 resources.static.json **[新增]**

静态资源配置，手工维护的核心资源。

```json
{
  "resources": [
    {
      "id": "general-chat",
      "name": "通用对话",
      "type": "direct_chat",
      "launch_mode": "native",
      "sync_meta": {
        "origin": "static",
        "origin_key": "general-chat"
      }
    }
  ]
}
```

#### 1.2 resources.overrides.json **[新增]**

覆盖配置，用于调整自动同步的资源属性。

```json
{
  "skill-coding": {
    "name": "编程助手",
    "group": "技能助手",
    "acl": {
      "allowed_roles": ["employee", "admin"]
    }
  }
}
```

#### 1.3 resources.generated.json **[新增]**

自动生成的最终资源配置，由 sync_resources.py 生成。

```json
{
  "generated_at": "2026-04-06T10:00:00Z",
  "workspace_id": "default",
  "resources": [...]
}
```

### 2. 环境变量模板 (`.env.example`)

#### V2 新增变量

```bash
# 运行环境
ENV=dev

# Mock登录 (仅开发)
ENABLE_MOCK_LOGIN=true

# Cookie安全
COOKIE_SECURE=false

# 会话有效期
SESSION_MAX_AGE_SEC=86400

# SSO配置
SSO_AUTHORIZE_URL=https://sso.company.com/oauth2/authorize
SSO_TOKEN_URL=https://sso.company.com/oauth2/token
SSO_CLIENT_ID=your-client-id
SSO_CLIENT_SECRET=your-client-secret
SSO_REDIRECT_URI=http://localhost:8000/api/auth/callback
SSO_JWKS_URL=https://sso.company.com/.well-known/jwks.json
```

#### 废弃变量

```bash
# 以下变量已废弃但保留向后兼容
USE_REDIS=false
JWT_SECRET=...
AUTH_MOCK_FALLBACK_ENABLED=false
```

---

## 🔨 脚本变更

### 1. sync_resources.py

#### 新增功能

```python
def generate_final_config(static_resources: List[Dict], 
                         overrides: Dict,
                         workspace_id: str) -> Dict:
    """生成最终资源配置"""
    # 合并 static + overrides
    # 添加 generated_at 时间戳
    # 输出到 resources.generated.json
```

#### 调用方式

```bash
# V2 推荐方式
python scripts/sync_resources.py --workspace default

# 输出: backend/config/resources.generated.json
```

### 2. start_dev.sh **[新增]**

开发环境快速启动脚本。

```bash
#!/bin/bash
# 1. 检查依赖
# 2. 生成资源配置
# 3. 启动后端
# 4. 启动前端
```

---

## 📚 文档变更

| 文档 | 变更类型 | 说明 |
|------|----------|------|
| `QUICKSTART_V2.md` | 新增 | V2快速启动指南 |
| `V2_MIGRATION_GUIDE.md` | 新增 | V1到V2迁移指南 |
| `V2_ADVANCED_CONFIGURATION.md` | 新增 | V2高级配置说明 |
| `docs/SSO_LOGIN_DEBUG_GUIDE.md` | 新增 | SSO调试指南 |
| `AGENTS.md` | 大幅更新 | 更新为V2完整指南 |
| `API.md` | 更新 | API文档更新 |
| `README.md` | 大幅更新 | 项目说明重构 |

---

## 🔄 升级检查清单

### 后端升级步骤

1. **备份现有配置**
   ```bash
   cp backend/.env backend/.env.backup.v1
   cp backend/config/resources.json backend/config/resources.json.backup
   ```

2. **更新 .env 文件**
   ```bash
   # 复制新模板
   cp .env.example backend/.env
   
   # 编辑填入实际值
   vim backend/.env
   ```

3. **生成 V2 资源配置**
   ```bash
   # 将旧 resources.json 迁移到 resources.static.json
   python scripts/migrate_v1_resources.py  # 如有提供
   
   # 生成最终配置
   python scripts/sync_resources.py --workspace default
   ```

4. **验证配置**
   ```bash
   python -c "from backend.app.config import validate_startup; validate_startup()"
   ```

### 前端升级步骤

1. **更新 .env**
   ```bash
   cp .env.example frontend/.env
   ```

2. **重新安装依赖**
   ```bash
   cd frontend
   npm install
   ```

3. **构建测试**
   ```bash
   npm run build
   ```

---

## ⚠️ 破坏性变更汇总

| 变更项 | 影响 | 迁移方案 |
|--------|------|----------|
| JWT → Session | 需要重新登录 | 使用新登录流程 |
| Redis 废弃 | 数据不持久化 | 仅影响重启后数据 |
| resources.json 格式 | 需要重新配置 | 使用 sync_resources.py |
| SSE 消息格式 | 前端需更新 | 更新 ChatInterface |
| 认证端点变更 | 前端API调用 | 更新 api.ts |

---

*文档版本: v2.0.0*  
*最后更新: 2026-04-11*
