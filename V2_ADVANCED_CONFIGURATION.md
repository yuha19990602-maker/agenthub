# AI Portal V2 高级配置指南

本文档涵盖 AI Portal V2 在特定场景下的高级配置说明。

---

## 一、多环境部署配置

### 1.1 环境变量分层管理

推荐按环境分离配置文件：

```
backend/
├── .env                    # 基础配置 (gitignored)
├── .env.dev                # 开发环境覆盖
├── .env.test               # 测试环境覆盖
├── .env.prod               # 生产环境覆盖
└── config/
    ├── resources.dev.json
    ├── resources.test.json
    └── resources.prod.json
```

### 1.2 开发环境 (.env.dev)

```bash
# ============ 基础 ============
ENV=dev
PORT=8000
HOST=0.0.0.0
RELOAD=true

# ============ 鉴权 - Fake SSO ============
ENABLE_MOCK_LOGIN=true
COOKIE_SECURE=false
COOKIE_SAMESITE=lax

# SSO 端点留空
SSO_AUTHORIZE_URL=
SSO_TOKEN_URL=
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=

# ============ 外部服务 ============
OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode
OPENCODE_PASSWORD=dev-password

OPENWORK_BASE_URL=http://127.0.0.1:8787
OPENWORK_TOKEN=dev-token

# ============ Portal ============
PORTAL_NAME="AI Portal - Dev"
RESOURCES_PATH=config/resources.dev.json

# ============ 调试 ============
LOG_LEVEL=DEBUG
LOG_FORMAT=json
```

### 1.3 测试环境 (.env.test)

```bash
# ============ 基础 ============
ENV=test
PORT=8000
HOST=0.0.0.0
RELOAD=false

# ============ 鉴权 - 混合模式 ============
ENABLE_MOCK_LOGIN=true  # 保留回退
COOKIE_SECURE=true      # HTTPS 测试
COOKIE_SAMESITE=none    # 跨域测试

# 配置测试 SSO
SSO_AUTHORIZE_URL=https://sso-test.company.com/oauth/authorize
SSO_TOKEN_URL=https://sso-test.company.com/oauth/token
SSO_CLIENT_ID=portal-test
SSO_CLIENT_SECRET=test-secret
SSO_REDIRECT_URI=https://portal-test.company.com/api/auth/callback
SSO_JWKS_URL=https://sso-test.company.com/.well-known/jwks.json

# ============ 外部服务 ============
OPENCODE_BASE_URL=https://opencode-test.company.com
OPENWORK_BASE_URL=https://openwork-test.company.com

# ============ Portal ============
PORTAL_NAME="AI Portal - Test"
RESOURCES_PATH=config/resources.test.json

# ============ 日志 ============
LOG_LEVEL=INFO
```

### 1.4 生产环境 (.env.prod)

```bash
# ============ 基础 ============
ENV=prod
PORT=8000
HOST=0.0.0.0
RELOAD=false

# ============ 鉴权 - 严格 SSO ============
ENABLE_MOCK_LOGIN=false  # 严禁 Mock 登录
COOKIE_SECURE=true       # HTTPS 必需
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=.company.com  # 子域共享

# 生产 SSO
SSO_AUTHORIZE_URL=https://sso.company.com/oauth/authorize
SSO_TOKEN_URL=https://sso.company.com/oauth/token
SSO_CLIENT_ID=portal-prod
SSO_CLIENT_SECRET=${SSO_CLIENT_SECRET}  # 从环境变量注入
SSO_REDIRECT_URI=https://portal.company.com/api/auth/callback
SSO_JWKS_URL=https://sso.company.com/.well-known/jwks.json

# Token 验证加强
SSO_TOKEN_ISSUER=https://sso.company.com
SSO_TOKEN_AUDIENCE=portal-prod

# ============ 外部服务 ============
OPENCODE_BASE_URL=https://opencode.company.com
OPENCODE_USERNAME=${OPENCODE_USERNAME}
OPENCODE_PASSWORD=${OPENCODE_PASSWORD}

OPENWORK_BASE_URL=https://openwork.company.com
OPENWORK_TOKEN=${OPENWORK_TOKEN}

# ============ Portal ============
PORTAL_NAME="AI Portal"
RESOURCES_PATH=config/resources.prod.json

# ============ 安全 ============
SESSION_MAX_AGE_SEC=28800  # 8小时会话
SESSION_CLEANUP_INTERVAL=3600  # 每小时清理过期会话

# ============ 性能 ============
WORKERS=4
MAX_CONNECTIONS=100
```

### 1.5 启动脚本 (start.sh)

```bash
#!/bin/bash
ENV=${1:-dev}

echo "Starting AI Portal in $ENV mode..."

# 加载对应环境配置
cp backend/.env.$ENV backend/.env 2>/dev/null || true
cp backend/config/resources.$ENV.json backend/config/resources.generated.json 2>/dev/null || true

# 启动服务
cd backend
/home/yy/python312/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
cd ../frontend
npm run dev &

wait
```

---

## 二、多租户/多 Workspace 配置

### 2.1 Workspace 隔离模式

AI Portal 支持多 workspace 隔离，不同部门/团队可拥有独立资源：

```json
// config/resources.prod.json
[
  {
    "id": "general-chat",
    "name": "通用对话",
    "type": "direct_chat",
    "adapter": "opencode",
    "launch_mode": "native",
    "group": "基础功能",
    "workspace_id": "default",  // 默认 workspace
    "enabled": true,
    "acl": {
      "allowed_roles": ["employee"]
    }
  },
  {
    "id": "engineering-copilot",
    "name": "研发 Copilot",
    "type": "skill_chat",
    "adapter": "skill_chat",
    "launch_mode": "native",
    "group": "研发专用",
    "workspace_id": "engineering",  // 研发 workspace
    "config": {
      "skill_name": "coding_assistant",
      "workspace_id": "engineering"
    },
    "acl": {
      "allowed_roles": ["employee"],
      "allowed_depts": ["Engineering", "DevOps"]
    }
  },
  {
    "id": "hr-policy-bot",
    "name": "HR 政策助手",
    "type": "kb_websdk",
    "adapter": "websdk",
    "launch_mode": "websdk",
    "group": "HR 专用",
    "workspace_id": "hr",  // HR workspace
    "config": {
      "app_id": "hr-knowledge-base",
      "workspace_id": "hr"
    },
    "acl": {
      "allowed_roles": ["employee"],
      "allowed_depts": ["HR"]
    }
  }
]
```

### 2.2 Workspace ACL 配置

```python
# backend/.env
ENABLE_WORKSPACE_ISOLATION=true
DEFAULT_WORKSPACE=default

# Workspace 权限映射
WORKSPACE_ACL_MAP='{
  "engineering": {"allowed_depts": ["Engineering", "DevOps", "QA"]},
  "hr": {"allowed_depts": ["HR"]},
  "finance": {"allowed_depts": ["Finance"], "allowed_roles": ["manager", "admin"]},
  "admin": {"allowed_roles": ["admin"]}
}'
```

### 2.3 动态 Workspace 路由

```python
# 根据用户部门自动选择 workspace
@app.get("/api/user/workspace")
async def get_user_workspace(user: SessionUser):
    dept_workspace_map = {
        "Engineering": "engineering",
        "DevOps": "engineering",
        "HR": "hr",
        "Finance": "finance",
    }
    return {
        "default_workspace": dept_workspace_map.get(user.dept, "default"),
        "available_workspaces": get_accessible_workspaces(user)
    }
```

---

## 三、自定义模型接入配置

### 3.1 OpenAI 兼容模型 (通用模板)

```json
{
  "id": "provider-model-id",
  "name": "显示名称",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "模型分类",
  "description": "模型描述",
  "enabled": true,
  "config": {
    "base_url": "https://api.provider.com/v1",
    "request_path": "/chat/completions",
    "api_key_env": "PROVIDER_API_KEY",
    "model": "model-name",
    "default_params": {
      "temperature": 0.7,
      "max_tokens": 2048,
      "top_p": 0.9
    },
    "headers": {
      "X-Request-Source": "ai-portal"
    },
    "history_window": 20,
    "stream_supported": true,
    "timeout_sec": 120,
    "retry_config": {
      "max_retries": 3,
      "backoff_factor": 2
    }
  },
  "acl": {
    "allowed_roles": ["employee"],
    "allowed_depts": ["Engineering", "Product"]
  }
}
```

### 3.2 常见模型提供商配置

#### DeepSeek

```json
{
  "id": "deepseek-chat",
  "name": "DeepSeek V3",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "第三方模型",
  "config": {
    "base_url": "https://api.deepseek.com",
    "api_key_env": "DEEPSEEK_API_KEY",
    "model": "deepseek-chat",
    "default_params": {
      "temperature": 0.7,
      "max_tokens": 4096
    },
    "history_window": 20,
    "stream_supported": true
  }
}
```

#### Moonshot (Kimi)

```json
{
  "id": "moonshot-kimi",
  "name": "Kimi K1.5",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "第三方模型",
  "config": {
    "base_url": "https://api.moonshot.cn/v1",
    "api_key_env": "MOONSHOT_API_KEY",
    "model": "kimi-k1-5",
    "default_params": {
      "temperature": 0.3,
      "max_tokens": 8192
    },
    "history_window": 50
  }
}
```

#### 阿里通义千问

```json
{
  "id": "qwen-max",
  "name": "通义千问 Max",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "国内模型",
  "config": {
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key_env": "DASHSCOPE_API_KEY",
    "model": "qwen-max",
    "default_params": {
      "temperature": 0.7,
      "max_tokens": 2048
    },
    "headers": {
      "X-DashScope-WorkSpace": "default"
    }
  }
}
```

#### Azure OpenAI

```json
{
  "id": "azure-gpt4",
  "name": "Azure GPT-4",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "Azure",
  "config": {
    "base_url": "https://your-resource.openai.azure.com/openai/deployments/your-deployment",
    "api_key_env": "AZURE_OPENAI_API_KEY",
    "model": "gpt-4",
    "default_params": {
      "temperature": 0.7
    },
    "headers": {
      "api-key": "${AZURE_OPENAI_API_KEY}",
      "api-version": "2024-02-01"
    }
  }
}
```

#### SiliconFlow

```json
{
  "id": "siliconflow-deepseek",
  "name": "SiliconFlow DeepSeek",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "第三方模型",
  "config": {
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key_env": "SILICONFLOW_API_KEY",
    "model": "deepseek-ai/DeepSeek-V3",
    "default_params": {
      "temperature": 0.7
    }
  }
}
```

### 3.3 本地模型 (vLLM/Ollama)

```json
{
  "id": "local-llama3",
  "name": "本地 Llama 3",
  "type": "openai_compatible_v1",
  "adapter": "openai_compatible",
  "launch_mode": "native",
  "group": "本地模型",
  "config": {
    "base_url": "http://localhost:8000/v1",
    "api_key_env": "DUMMY_API_KEY",
    "model": "meta-llama/Llama-3-8B-Instruct",
    "default_params": {
      "temperature": 0.7,
      "max_tokens": 2048
    }
  },
  "acl": {
    "allowed_roles": ["employee"]
  }
}
```

---

## 四、技能权限细粒度控制

### 4.1 角色-技能映射

```json
// config/resources.prod.json
[
  {
    "id": "skill-coding-pro",
    "name": "高级编程助手",
    "type": "skill_chat",
    "adapter": "skill_chat",
    "launch_mode": "native",
    "group": "研发工具",
    "config": {
      "skill_name": "coding_pro",
      "starter_prompts": ["审查代码", "设计架构"]
    },
    "acl": {
      "allowed_roles": ["senior_engineer", "staff_engineer", "admin"],
      "allowed_depts": ["Engineering"],
      "denied_users": ["contractor_001", "intern_group"]
    }
  },
  {
    "id": "skill-data-analysis",
    "name": "数据分析专家",
    "type": "skill_chat",
    "adapter": "skill_chat",
    "launch_mode": "native",
    "group": "数据工具",
    "config": {
      "skill_name": "data_analyst"
    },
    "acl": {
      "allowed_roles": ["employee"],
      "allowed_depts": ["Engineering", "Data", "Product"],
      "required_labels": ["data_access_approved"]
    }
  }
]
```

### 4.2 动态 ACL 策略

```python
# backend/app/acl/dynamic_policy.py

class DynamicACLPolicy:
    """动态权限策略"""
    
    def check_resource_access(self, user: UserCtx, resource: Resource) -> bool:
        # 1. 基础 ACL 检查
        if not self._check_basic_acl(user, resource.acl):
            return False
        
        # 2. 时间限制 (如仅工作时间可用)
        if resource.acl.get("time_restrictions"):
            if not self._check_time_restrictions(resource.acl["time_restrictions"]):
                return False
        
        # 3. 配额检查 (如每日使用次数)
        if resource.acl.get("quota"):
            if not self._check_quota(user, resource.id, resource.acl["quota"]):
                return False
        
        # 4. 审批流程 (敏感技能)
        if resource.acl.get("requires_approval"):
            if not self._check_approval(user, resource.id):
                return False
        
        return True
    
    def _check_quota(self, user: UserCtx, resource_id: str, quota: dict) -> bool:
        """检查使用配额"""
        today_usage = get_today_usage(user.user_id, resource_id)
        return today_usage < quota.get("daily_limit", 100)
```

### 4.3 技能审批工作流

```python
# backend/app/acl/approval.py

class SkillApprovalService:
    """敏感技能审批服务"""
    
    async def request_approval(
        self,
        user: UserCtx,
        resource_id: str,
        reason: str
    ) -> ApprovalRequest:
        """申请使用敏感技能"""
        request = ApprovalRequest(
            id=generate_id(),
            user_id=user.user_id,
            resource_id=resource_id,
            reason=reason,
            status="pending",
            requested_at=now(),
            approvers=self._get_approvers(user, resource_id)
        )
        await storage.save_approval_request(request)
        await self._notify_approvers(request)
        return request
    
    async def approve(self, request_id: str, approver: UserCtx) -> bool:
        """审批通过"""
        request = await storage.get_approval_request(request_id)
        if approver.user_id not in request.approvers:
            raise PermissionError("Not an approver")
        
        request.status = "approved"
        request.approved_at = now()
        request.approved_by = approver.user_id
        await storage.save_approval_request(request)
        
        # 授予临时权限
        await grant_temporary_access(
            user_id=request.user_id,
            resource_id=request.resource_id,
            duration_hours=24
        )
        return True
```

---

## 五、高可用/集群部署配置

### 5.1 多实例部署架构

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (Nginx/ALB)   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
   │ Portal  │          │ Portal  │          │ Portal  │
   │  #1     │          │  #2     │          │  #3     │
   │ :8000   │          │ :8000   │          │ :8000   │
   └────┬────┘          └────┬────┘          └────┬────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Redis Cluster │
                    │   (Session共享)  │
                    └─────────────────┘
```

### 5.2 Redis 集群配置

```bash
# backend/.env - 集群模式
USE_REDIS=true
REDIS_MODE=cluster
REDIS_NODES=redis-node1:6379,redis-node2:6379,redis-node3:6379
REDIS_PASSWORD=${REDIS_PASSWORD}

# Sentinel 高可用
# REDIS_MODE=sentinel
# REDIS_SENTINEL_HOSTS=sentinel1:26379,sentinel2:26379,sentinel3:26379
# REDIS_SENTINEL_MASTER_NAME=mymaster
```

### 5.3 Session 共享配置

```python
# backend/app/store/redis_store.py - 集群适配

class RedisClusterStore:
    """Redis Cluster 存储实现"""
    
    def __init__(self, nodes: list[str], password: str):
        from redis.cluster import RedisCluster
        
        startup_nodes = [
            {"host": host, "port": int(port)}
            for node in nodes
            for host, port in [node.split(":")]
        ]
        
        self.client = RedisCluster(
            startup_nodes=startup_nodes,
            password=password,
            decode_responses=True,
            skip_full_coverage_check=True
        )
    
    async def save_session(self, session: AuthSession) -> bool:
        """保存会话到集群"""
        key = f"session:{session.session_id}"
        data = session.model_dump_json()
        ttl = session.expires_at - int(time.time())
        return await self.client.setex(key, ttl, data)
```

### 5.4 Nginx 负载均衡配置

```nginx
# /etc/nginx/conf.d/portal.conf

upstream portal_backend {
    least_conn;  # 最少连接数算法
    
    server 10.0.1.10:8000 weight=5;
    server 10.0.1.11:8000 weight=5;
    server 10.0.1.12:8000 weight=5 backup;
    
    keepalive 32;
}

server {
    listen 80;
    server_name portal.company.com;
    
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name portal.company.com;
    
    ssl_certificate /etc/nginx/ssl/portal.crt;
    ssl_certificate_key /etc/nginx/ssl/portal.key;
    
    # 会话粘性 (确保 SSE 连接到同一实例)
    location /api/sessions/ {
        proxy_pass http://portal_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        
        # Cookie 粘性
        sticky cookie portal_route expires=1h domain=.company.com path=/;
    }
    
    location /api/ {
        proxy_pass http://portal_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        root /var/www/portal/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

### 5.5 健康检查与自动恢复

```python
# backend/app/health/checks.py

class HealthCheckService:
    """健康检查服务"""
    
    async def comprehensive_check(self) -> HealthStatus:
        """综合健康检查"""
        checks = await asyncio.gather(
            self._check_storage(),
            self._check_opencode(),
            self._check_openwork(),
            self._check_sso(),
            return_exceptions=True
        )
        
        return HealthStatus(
            status="healthy" if all(c.is_healthy for c in checks) else "degraded",
            version="2.0.0",
            checks={
                "storage": checks[0],
                "opencode": checks[1],
                "openwork": checks[2],
                "sso": checks[3]
            }
        )
    
    async def _check_storage(self) -> ComponentHealth:
        """存储健康检查"""
        try:
            start = time.time()
            await storage.ping()
            latency_ms = (time.time() - start) * 1000
            return ComponentHealth(
                is_healthy=True,
                latency_ms=latency_ms
            )
        except Exception as e:
            return ComponentHealth(
                is_healthy=False,
                error=str(e)
            )
```

---

## 六、审计日志配置

### 6.1 审计事件类型

```python
# backend/app/audit/models.py

class AuditEventType(str, Enum):
    # 认证事件
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_EXPIRED = "session_expired"
    
    # 资源访问
    RESOURCE_VIEW = "resource_view"
    RESOURCE_LAUNCH = "resource_launch"
    RESOURCE_ACCESS_DENIED = "resource_access_denied"
    
    # 会话操作
    SESSION_CREATE = "session_create"
    SESSION_MESSAGE = "session_message"
    SESSION_UPLOAD = "session_upload"
    SESSION_DELETE = "session_delete"
    
    # 管理操作
    ADMIN_SYNC = "admin_sync"
    ADMIN_CONFIG_CHANGE = "admin_config_change"
    ADMIN_USER_MANAGE = "admin_user_manage"
```

### 6.2 审计日志配置

```bash
# backend/.env

# 审计日志
AUDIT_LOG_ENABLED=true
AUDIT_LOG_LEVEL=INFO  # DEBUG | INFO | WARNING
AUDIT_LOG_OUTPUT=file  # file | stdout | both
AUDIT_LOG_PATH=logs/audit.log
AUDIT_LOG_MAX_SIZE_MB=100
AUDIT_LOG_MAX_BACKUPS=30
AUDIT_LOG_FORMAT=json  # json | text

# 敏感数据脱敏
AUDIT_MASK_PII=true
AUDIT_MASK_FIELDS=password,token,api_key,secret

# 实时告警
AUDIT_ALERT_WEBHOOK=https://hooks.company.com/security
AUDIT_ALERT_EVENTS=login_failure,resource_access_denied,admin_config_change
```

### 6.3 审计日志实现

```python
# backend/app/audit/service.py

class AuditService:
    """审计日志服务"""
    
    async def log_event(
        self,
        event_type: AuditEventType,
        user: Optional[UserCtx],
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None
    ):
        """记录审计事件"""
        event = AuditEvent(
            id=generate_uuid(),
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            user_id=user.user_id if user else None,
            user_name=user.user_name if user else None,
            user_dept=user.dept if user else None,
            resource_id=resource_id,
            details=self._mask_sensitive_data(details),
            ip_address=ip_address or self._get_client_ip(),
            user_agent=self._get_user_agent(),
            trace_id=self._get_trace_id()
        )
        
        # 写入日志
        await self._write_log(event)
        
        # 实时告警检查
        if event_type in settings.audit_alert_events:
            await self._send_alert(event)
    
    def _mask_sensitive_data(self, details: Optional[dict]) -> Optional[dict]:
        """脱敏敏感字段"""
        if not details or not settings.audit_mask_pii:
            return details
        
        masked = deepcopy(details)
        for field in settings.audit_mask_fields.split(","):
            if field in masked:
                masked[field] = "***MASKED***"
        return masked
```

### 6.4 审计日志查询 API

```python
@app.get("/api/admin/audit/logs")
async def query_audit_logs(
    start_time: datetime,
    end_time: datetime,
    user_id: Optional[str] = None,
    event_type: Optional[AuditEventType] = None,
    resource_id: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    user: AdminUser = None
) -> AuditLogList:
    """查询审计日志 (仅 admin)"""
    
    logs = await audit_service.query_logs(
        start_time=start_time,
        end_time=end_time,
        filters={
            "user_id": user_id,
            "event_type": event_type,
            "resource_id": resource_id
        },
        limit=limit,
        offset=offset
    )
    
    return AuditLogList(
        total=logs.total,
        items=logs.items,
        limit=limit,
        offset=offset
    )
```

---

## 七、速率限制配置

### 7.1 分层速率限制

```bash
# backend/.env

# 全局限制
RATE_LIMIT_ENABLED=true

# 层级1: IP 级别 (防 DDoS)
RATE_LIMIT_IP_REQUESTS_PER_MINUTE=60
RATE_LIMIT_IP_BURST=10

# 层级2: 用户级别 (防滥用)
RATE_LIMIT_USER_REQUESTS_PER_MINUTE=30
RATE_LIMIT_USER_MESSAGES_PER_MINUTE=20

# 层级3: 资源级别 (成本控制)
RATE_LIMIT_RESOURCE_DEFAULT_PER_MINUTE=10
RATE_LIMIT_RESOURCE_PREMIUM_PER_MINUTE=100

# 层级4: 模型级别 (API 配额)
RATE_LIMIT_MODEL_TOKENS_PER_DAY=100000
```

### 7.2 速率限制实现

```python
# backend/app/rate_limit/service.py

class RateLimitService:
    """分层速率限制服务"""
    
    def __init__(self, storage: Storage):
        self.storage = storage
        self.rules = self._load_rules()
    
    async def check_rate_limit(
        self,
        key: str,  # ip:xxx 或 user:xxx 或 resource:xxx
        limit: int,
        window_seconds: int
    ) -> RateLimitResult:
        """检查是否超过速率限制"""
        current = int(time.time())
        window_start = current - window_seconds
        
        # 清理旧记录
        await self.storage.zremrangebyscore(
            f"ratelimit:{key}",
            0,
            window_start
        )
        
        # 统计当前窗口请求数
        count = await self.storage.zcard(f"ratelimit:{key}")
        
        if count >= limit:
            # 获取下次重置时间
            oldest = await self.storage.zrange(
                f"ratelimit:{key}",
                0, 0,
                withscores=True
            )
            reset_at = int(oldest[0][1]) + window_seconds if oldest else current + window_seconds
            
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at
            )
        
        # 记录本次请求
        await self.storage.zadd(
            f"ratelimit:{key}",
            {str(uuid.uuid4()): current}
        )
        await self.storage.expire(
            f"ratelimit:{key}",
            window_seconds
        )
        
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit - count - 1,
            reset_at=current + window_seconds
        )
    
    async def check_multi_tier(
        self,
        ip: str,
        user: Optional[UserCtx],
        resource: Optional[Resource]
    ) -> Optional[str]:
        """
        多层速率限制检查
        返回 None 表示通过，否则返回错误信息
        """
        # 层级1: IP 限制
        ip_result = await self.check_rate_limit(
            f"ip:{ip}",
            settings.rate_limit_ip_requests_per_minute,
            60
        )
        if not ip_result.allowed:
            return f"IP rate limit exceeded, retry after {ip_result.reset_at}"
        
        # 层级2: 用户限制
        if user:
            user_result = await self.check_rate_limit(
                f"user:{user.user_id}:requests",
                settings.rate_limit_user_requests_per_minute,
                60
            )
            if not user_result.allowed:
                return f"User rate limit exceeded, retry after {user_result.reset_at}"
        
        # 层级3: 资源限制
        if resource:
            resource_limit = resource.config.get(
                "rate_limit_per_minute",
                settings.rate_limit_resource_default_per_minute
            )
            resource_result = await self.check_rate_limit(
                f"resource:{resource.id}",
                resource_limit,
                60
            )
            if not resource_result.allowed:
                return f"Resource rate limit exceeded, retry after {resource_result.reset_at}"
        
        return None
```

### 7.3 模型 Token 配额管理

```python
# backend/app/rate_limit/token_quota.py

class TokenQuotaService:
    """模型 Token 配额管理"""
    
    async def check_token_quota(
        self,
        user: UserCtx,
        model: str,
        estimated_tokens: int
    ) -> QuotaResult:
        """检查 Token 配额"""
        daily_key = f"quota:tokens:{user.user_id}:{model}:{today()}"
        
        current_usage = await self.storage.get(daily_key) or 0
        limit = self._get_user_model_limit(user, model)
        
        if current_usage + estimated_tokens > limit:
            return QuotaResult(
                allowed=False,
                current_usage=current_usage,
                limit=limit,
                remaining=limit - current_usage
            )
        
        return QuotaResult(
            allowed=True,
            current_usage=current_usage,
            limit=limit,
            remaining=limit - current_usage
        )
    
    async def consume_tokens(
        self,
        user: UserCtx,
        model: str,
        input_tokens: int,
        output_tokens: int
    ):
        """消耗 Token 配额"""
        daily_key = f"quota:tokens:{user.user_id}:{model}:{today()}"
        total_tokens = input_tokens + output_tokens
        
        await self.storage.incrby(daily_key, total_tokens)
        await self.storage.expire(daily_key, 86400)  # 24小时过期
        
        # 记录明细
        await self._log_token_usage(user, model, input_tokens, output_tokens)
    
    def _get_user_model_limit(self, user: UserCtx, model: str) -> int:
        """获取用户模型配额"""
        # 根据用户角色返回不同配额
        if "admin" in user.roles:
            return float('inf')
        if "premium" in user.roles:
            return 500000  # 50万
        if "standard" in user.roles:
            return 100000  # 10万
        return 10000  # 1万
```

---

## 八、前端生产部署配置

### 8.1 多环境构建配置

```typescript
// frontend/.env.development
VITE_API_BASE_URL=/
VITE_APP_NAME="AI Portal - Dev"
VITE_ENABLE_MOCK=true
VITE_LOG_LEVEL=debug

// frontend/.env.test
VITE_API_BASE_URL=https://portal-test.company.com
VITE_APP_NAME="AI Portal - Test"
VITE_ENABLE_MOCK=false
VITE_LOG_LEVEL=info

// frontend/.env.production
VITE_API_BASE_URL=https://portal.company.com
VITE_APP_NAME="AI Portal"
VITE_ENABLE_MOCK=false
VITE_LOG_LEVEL=warn
VITE_ENABLE_SENTRY=true
VITE_SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
```

### 8.2 Docker 生产构建

```dockerfile
# frontend/Dockerfile.prod

# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# 运行阶段
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API 代理
    location /api/ {
        proxy_pass ${VITE_API_BASE_URL};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SPA 回退
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 九、监控与告警配置

### 9.1 Prometheus 指标

```python
# backend/app/metrics/prometheus.py

from prometheus_client import Counter, Histogram, Gauge, generate_latest

# 请求计数
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# 请求延迟
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# 活跃会话数
active_sessions = Gauge(
    'portal_active_sessions',
    'Number of active sessions'
)

# 消息计数
messages_total = Counter(
    'portal_messages_total',
    'Total messages processed',
    ['adapter', 'status']
)

@app.get("/metrics")
async def metrics():
    """Prometheus 指标端点"""
    return Response(generate_latest(), media_type="text/plain")
```

### 9.2 健康检查端点

```python
@app.get("/api/health")
async def health_check() -> HealthCheck:
    """健康检查"""
    checks = await health_service.check_all()
    
    return HealthCheck(
        status="healthy" if all(c.is_healthy for c in checks.values()) else "unhealthy",
        version=VERSION,
        timestamp=datetime.utcnow().isoformat(),
        checks=checks
    )

@app.get("/api/ready")
async def readiness_check() -> ReadyCheck:
    """就绪检查 (K8s)"""
    required = ["storage", "opencode"]
    ready = all(
        checks.get(service, False)
        for service in required
    )
    
    return ReadyCheck(
        ready=ready,
        checks={k: v for k, v in checks.items() if k in required}
    )

@app.get("/api/live")
async def liveness_check():
    """存活检查 (K8s)"""
    return {"alive": True}
```

---

## 十、完整配置示例汇总

### 10.1 开发环境完整配置

```bash
# backend/.env
ENV=dev
PORT=8000
HOST=0.0.0.0
RELOAD=true

ENABLE_MOCK_LOGIN=true
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
SESSION_MAX_AGE_SEC=86400

SSO_AUTHORIZE_URL=
SSO_TOKEN_URL=
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=

OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode
OPENCODE_PASSWORD=dev

OPENWORK_BASE_URL=http://127.0.0.1:8787
OPENWORK_TOKEN=dev

PORTAL_NAME="AI Portal - Dev"
RESOURCES_PATH=config/resources.dev.json

LOG_LEVEL=DEBUG
USE_REDIS=false

# frontend/.env
VITE_API_BASE_URL=/
VITE_APP_NAME="AI Portal - Dev"
```

### 10.2 生产环境完整配置

```bash
# backend/.env
ENV=prod
PORT=8000
HOST=0.0.0.0
RELOAD=false

ENABLE_MOCK_LOGIN=false
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=.company.com
SESSION_MAX_AGE_SEC=28800

SSO_AUTHORIZE_URL=https://sso.company.com/oauth/authorize
SSO_TOKEN_URL=https://sso.company.com/oauth/token
SSO_CLIENT_ID=portal-prod
SSO_CLIENT_SECRET=${SSO_CLIENT_SECRET}
SSO_REDIRECT_URI=https://portal.company.com/api/auth/callback
SSO_JWKS_URL=https://sso.company.com/.well-known/jwks.json

OPENCODE_BASE_URL=https://opencode.company.com
OPENCODE_USERNAME=${OPENCODE_USERNAME}
OPENCODE_PASSWORD=${OPENCODE_PASSWORD}

OPENWORK_BASE_URL=https://openwork.company.com
OPENWORK_TOKEN=${OPENWORK_TOKEN}

PORTAL_NAME="AI Portal"
RESOURCES_PATH=config/resources.prod.json

LOG_LEVEL=INFO
USE_REDIS=true
REDIS_MODE=cluster
REDIS_NODES=redis-1:6379,redis-2:6379,redis-3:6379
REDIS_PASSWORD=${REDIS_PASSWORD}

AUDIT_LOG_ENABLED=true
AUDIT_LOG_LEVEL=INFO
AUDIT_LOG_OUTPUT=both
AUDIT_LOG_PATH=logs/audit.log

RATE_LIMIT_ENABLED=true
RATE_LIMIT_IP_REQUESTS_PER_MINUTE=60
RATE_LIMIT_USER_REQUESTS_PER_MINUTE=30

# frontend/.env.production
VITE_API_BASE_URL=https://portal.company.com
VITE_APP_NAME="AI Portal"
VITE_ENABLE_MOCK=false
VITE_LOG_LEVEL=warn
```

---

**版本**: 2.0.0  
**更新日期**: 2026-04-06
