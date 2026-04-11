# AI Portal 版本更新历史 (Version History)

> 本文档详细记录了 AI Portal 项目从初始版本到当前版本的所有重要变更。
> 
> **当前版本**: v2.0.0  
> **最后更新**: 2026-04-06

---

## 📊 版本演进概览

| 版本 | 提交哈希 | 日期 | 版本名称 | 主要特性 |
|------|----------|------|----------|----------|
| v1.0.0 | `2312263` | 2026-03-27 | Initial Commit | 项目初始化，基础框架搭建 |
| v1.1.0 | `4073f34` | 2026-03-27 | 118 | 基础功能完善 |
| v1.2.0 | `fc3917d` | 2026-03-28 | UI Opt | 三栏UI布局、Iframe嵌入支持 |
| v1.3.0 | `94d6652` | 2026-04-03 | Web Opt | 资源加载优化、会话详情API |
| v1.4.0 | `0827c4a` | 2026-04-03 | File SSE | 文件上传、SSE流式响应 |
| v1.4.1 | `f4fad8e` | 2026-04-03 | File SSE Fix | SSE修复和优化 |
| v1.5.0 | `95e630b` | 2026-04-04 | Syn | 资源同步功能 |
| v1.6.0 | `b51c551` | 2026-04-06 | CSV LS | CSV处理和列表功能 |
| **v2.0.0** | `0d6da35` | 2026-04-06 | Opt Codex | **V2大版本升级，OpenAI兼容、认证重构** |

---

## 🔍 详细版本变更说明

### v1.0.0 → v1.2.0 (Initial → UI优化)

**时间**: 2026-03-27 → 2026-03-28  
**涉及文件数**: 23个文件  
**代码变更**: +4,214 行 / -190 行

#### 主要改动模块

| 模块 | 改动文件 | 改动类型 | 详细说明 |
|------|----------|----------|----------|
| **文档** | `AGENTS.md` | 新增 | 新增619行AI Agent项目指南 |
| **后端-适配器** | `backend/app/adapters/iframe.py` | 新增 | 新增Iframe适配器，支持直接iframe嵌入第三方应用 |
| **后端-主程序** | `backend/app/main.py` | 修改 | 添加Iframe启动模式支持，优化会话列表API参数校验 |
| **后端-模型** | `backend/app/models.py` | 修改 | 新增IframeConfig模型定义 |
| **后端-配置** | `backend/config/resources.json` | 修改 | 添加Iframe资源配置 |
| **前端-主应用** | `frontend/src/App.tsx` | 大幅修改 | 重构为三栏布局（资源侧边栏+会话侧边栏+工作区） |
| **前端-API** | `frontend/src/api.ts` | 修改 | 新增iframe-config API调用 |
| **前端-组件** | `frontend/src/components/ChatInterface.tsx` | 大幅修改 | 增强聊天界面，添加Markdown渲染支持 |
| **前端-组件** | `frontend/src/components/IframeWorkspace.tsx` | 新增 | 新增Iframe工作区组件 |
| **前端-组件** | `frontend/src/components/ResourceSidebar.tsx` | 新增 | 新增资源侧边栏组件，支持分组折叠 |
| **前端-样式** | `frontend/src/styles/globals.css` | 修改 | 新增大量CSS样式支持三栏布局 |
| **前端-类型** | `frontend/src/types.ts` | 修改 | 更新TypeScript类型定义 |
| **前端-依赖** | `frontend/package.json` | 修改 | 添加rehype-highlight等Markdown渲染依赖 |

#### API变更

| API端点 | 变更类型 | 说明 |
|---------|----------|------|
| `GET /api/launches/{launch_id}/iframe-config` | 新增 | 获取Iframe嵌入配置 |
| `GET /api/sessions` | 修改 | limit参数添加范围校验(1-100) |
| `GET /api/launches` | 修改 | limit参数添加范围校验(1-100) |

---

### v1.2.0 → v1.3.0 (UI优化 → Web优化)

**时间**: 2026-03-28 → 2026-04-03  
**涉及文件数**: 11个文件  
**代码变更**: +209 行 / -97 行

#### 主要改动模块

| 模块 | 改动文件 | 改动类型 | 详细说明 |
|------|----------|----------|----------|
| **文档** | `AGENTS.md` | 修改 | 优化项目文档，精简内容 |
| **后端-主程序** | `backend/app/main.py` | 修改 | 新增会话详情查询API，增强资源启动模式校验 |
| **后端-配置** | `backend/config/resources.json` | 修改 | 调整资源配置 |
| **前端-主应用** | `frontend/src/App.tsx` | 修改 | 优化应用路由和状态管理 |
| **前端-API** | `frontend/src/api.ts` | 修改 | 新增获取会话详情接口 |
| **前端-组件** | `frontend/src/components/ResourceSidebar.tsx` | 修改 | 优化资源侧边栏交互 |

#### API变更

| API端点 | 变更类型 | 说明 |
|---------|----------|------|
| `GET /api/sessions/{portal_session_id}` | 新增 | 根据ID获取会话详情 |
| `GET /api/launches/{launch_id}/embed-config` | 修改 | 添加WebSDK模式校验 |
| `GET /api/launches/{launch_id}/iframe-config` | 修改 | 添加Iframe模式校验 |

---

### v1.3.0 → v1.4.0 (Web优化 → File SSE)

**时间**: 2026-04-03  
**涉及文件数**: 55+ 个文件  
**代码变更**: 大量重构

#### 主要改动模块

| 模块 | 改动文件 | 改动类型 | 详细说明 |
|------|----------|----------|----------|
| **后端-适配器基类** | `backend/app/adapters/base.py` | 修改 | 扩展适配器基类，支持流式消息返回类型定义 |
| **后端-OpenCode适配器** | `backend/app/adapters/opencode.py` | 大幅修改 | 重构SSE流式处理，优化消息解析 |
| **后端-Skill适配器** | `backend/app/adapters/skill_chat.py` | 修改 | 增强技能聊天适配器 |
| **后端-主程序** | `backend/app/main.py` | 大幅修改 | 新增文件上传API，重构SSE流式响应端点 |
| **后端-依赖** | `backend/pyproject.toml` | 修改 | 添加新依赖 |
| **前端-缓存** | `frontend/.vite/deps/*` | 清理 | 清理Vite缓存文件 |
| **前端-HTML** | `frontend/index.html` | 删除 | 删除测试HTML |
| **前端-主应用** | `frontend/src/App.tsx` | 删除 | 完整重构准备 |

#### 核心功能变更

| 功能 | 变更说明 |
|------|----------|
| **文件上传** | 新增文件上传到会话功能，支持多文件 |
| **SSE流式响应** | 重构Server-Sent Events实现，支持更稳定的流式输出 |
| **消息格式** | 统一流式消息格式：`start` → `delta` → `done` |

---

### v1.4.0 → v1.5.0 (File SSE → Syn)

**时间**: 2026-04-03 → 2026-04-04  
**主要特性**: 资源同步功能增强

#### 主要改动模块

| 模块 | 改动文件 | 改动类型 | 详细说明 |
|------|----------|----------|----------|
| **后端-目录服务** | `backend/app/catalog/service.py` | 修改 | 增强资源目录服务，支持动态同步 |
| **后端-同步服务** | `backend/app/catalog/sync_service.py` | 新增 | 新增资源同步服务，支持OpenWork技能同步 |
| **脚本** | `scripts/sync_resources.py` | 修改 | 优化资源同步脚本 |

---

### v1.5.0 → v2.0.0 (Syn → Opt Codex / V2大版本)

**时间**: 2026-04-04 → 2026-04-06  
**涉及文件数**: 70+ 个文件  
**代码变更**: 大规模重构升级

#### 主要改动模块

| 模块 | 改动文件 | 改动类型 | 详细说明 |
|------|----------|----------|----------|
| **项目配置** | `.env.example` | 大幅修改 | 新增V2环境变量配置模板 |
| **文档** | `AGENTS.md` | 大幅修改 | 更新为V2版本完整指南 (+486行) |
| **文档** | `API.md` | 修改 | API文档更新 |
| **文档** | `README.md` | 大幅修改 | 项目README重构 |
| **文档** | `QUICKSTART_V2.md` | 新增 | V2快速启动指南 |
| **文档** | `V2_ADVANCED_CONFIGURATION.md` | 新增 | V2高级配置指南 (1368行) |
| **文档** | `V2_MIGRATION_GUIDE.md` | 新增 | V1到V2迁移指南 (396行) |
| **文档** | `docs/SSO_LOGIN_DEBUG_GUIDE.md` | 新增 | SSO登录调试指南 |
| **后端-配置** | `backend/app/config.py` | 大幅修改 | 新增启动验证、配置项扩展 |
| **后端-模型** | `backend/app/models.py` | 大幅修改 | 新增PortalSession、LaunchRecord、SessionBinding等V2核心模型 |
| **后端-主程序** | `backend/app/main.py` | 大幅修改 | V2重构：适配器注册表、统一会话管理、上下文管理 |
| **后端-认证-依赖** | `backend/app/auth/deps.py` | 大幅修改 | 重构认证依赖，新增SessionUser、AdminUser |
| **后端-认证-路由** | `backend/app/auth/routes.py` | 大幅修改 | 新增fake_sso支持、服务器端会话 |
| **后端-认证-服务** | `backend/app/auth/service.py` | 大幅修改 | JWT + 服务器端会话双模式支持 |
| **后端-认证-FakeSSO** | `backend/app/auth/fake_sso.py` | 新增 | 开发环境Fake SSO模拟器 |
| **后端-ACL** | `backend/app/acl/service.py` | 修改 | 增强访问控制 |
| **后端-适配器** | `backend/app/adapters/openai_compatible.py` | 新增 | 新增OpenAI兼容适配器 |
| **后端-存储** | `backend/app/store/memory_store.py` | 大幅修改 | 扩展存储层，支持四层数据模型 |
| **后端-存储** | `backend/app/store/redis_store.py` | 大幅修改 | Redis存储实现更新 |
| **后端-配置** | `backend/config/resources.generated.json` | 新增 | 自动生成资源配置 |
| **后端-配置** | `backend/config/resources.overrides.json` | 新增 | 资源覆盖配置 |
| **后端-配置** | `backend/config/resources.static.json` | 新增 | 静态资源配置 |
| **后端-测试** | `backend/tests/test_api_simple.py` | 修改 | 测试用例更新 |
| **前端-认证** | `frontend/src/auth/*` | 新增 | 新增完整认证模块 (AuthProvider, ProtectedRoute等) |
| **前端-主应用** | `frontend/src/App.tsx` | 大幅修改 | V2重构，支持新认证流程 |
| **前端-组件** | `frontend/src/components/ChatInterface.tsx` | 大幅修改 | V2聊天界面优化 |
| **前端-组件** | `frontend/src/components/SessionSidebar.tsx` | 修改 | 会话列表增强 |
| **脚本** | `scripts/start_dev.sh` | 新增 | 开发启动脚本 |

#### V2核心功能变更

| 功能模块 | 变更说明 |
|----------|----------|
| **架构升级** | 从V1架构升级到V2，支持更灵活的资源配置 |
| **认证重构** | 支持JWT Cookie + 服务器端会话双模式，新增Fake SSO开发模式 |
| **适配器注册表** | 新增适配器注册表模式，支持动态适配器分发 |
| **OpenAI兼容** | 新增OpenAI Compatible适配器，支持标准OpenAI API格式 |
| **四层数据模型** | 引入PortalSession、LaunchRecord、SessionBinding、PortalMessage四层数据模型 |
| **上下文管理** | 新增Context系统，支持用户级、资源级、会话级上下文 |
| **资源同步** | 完善从OpenWork同步技能到Portal的机制 |
| **存储抽象** | 统一存储接口，支持Memory和Redis两种实现 |

#### V2新增API端点

| API端点 | 说明 |
|---------|------|
| `POST /api/admin/resources/sync` | 触发资源同步 |
| `PATCH /api/contexts/user-resource/{resource_id}` | 更新用户-资源级上下文 |
| `POST /api/sessions/{id}/archive` | 归档会话 |
| `GET /api/sessions/{id}/context` | 获取会话合并上下文 |
| `GET /api/resources/grouped` | 获取分组资源列表 |

#### 数据模型变更

| 新增模型 | 说明 |
|----------|------|
| `PortalSession` | Portal会话核心模型 |
| `LaunchRecord` | 资源启动记录 |
| `SessionBinding` | 会话与引擎绑定关系 |
| `PortalMessage` | Portal消息模型 |
| `ContextScope` | 上下文作用域枚举 |
| `EnrichedPortalSession` | 增强会话信息 |
| `SessionResumePayload` | 会话恢复载荷 |

---

## 📈 代码统计

### 各版本代码量变化

| 版本 | 后端Python代码 | 前端TypeScript代码 | 文档 | 总计 |
|------|---------------|-------------------|------|------|
| v1.0.0 | ~2,000 行 | ~1,500 行 | ~500 行 | ~4,000 行 |
| v1.2.0 | ~2,500 行 | ~3,000 行 | ~1,200 行 | ~6,700 行 |
| v1.3.0 | ~2,600 行 | ~3,100 行 | ~1,100 行 | ~6,800 行 |
| v1.4.0 | ~3,000 行 | ~2,500 行 | ~1,000 行 | ~6,500 行 |
| **v2.0.0** | **~8,000+ 行** | **~4,000+ 行** | **~5,000+ 行** | **~17,000+ 行** |

---

## 🔄 破坏性变更 (Breaking Changes)

### v1.4.0 中的破坏性变更

- 前端项目结构大幅重构，移除旧组件重新实现
- SSE消息格式变更，需要客户端同步更新

### v2.0.0 中的破坏性变更

| 变更项 | 说明 | 迁移建议 |
|--------|------|----------|
| 认证方式 | 从纯JWT改为JWT + 服务器端会话 | 参考 `V2_MIGRATION_GUIDE.md` |
| 环境变量 | 大量配置项变更 | 使用新的 `.env.example` 模板 |
| API响应格式 | 部分API响应结构调整 | 更新前端API调用代码 |
| 存储结构 | 数据存储格式变更 | 需要清理旧数据或迁移 |
| 资源配置 | 从单文件改为三层配置 | 使用 `sync_resources.py` 重新生成 |

---

## 📝 配置文件变更

### v1.x 配置 (resources.json)
```json
{
  "id": "general-chat",
  "name": "通用对话",
  "type": "direct_chat",
  "launch_mode": "native"
}
```

### v2.0 配置 (三层配置)

**resources.static.json** - 静态资源
```json
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
```

**resources.overrides.json** - 覆盖配置
```json
{
  "skill-coding": {
    "name": "编程助手",
    "group": "技能助手"
  }
}
```

**resources.generated.json** - 自动生成
```json
{
  "generated_at": "2026-04-06T10:00:00Z",
  "workspace_id": "default",
  "resources": [...]
}
```

---

## 🚀 升级建议

### 从 v1.4.x 升级到 v2.0.0

1. **备份数据**
   ```bash
   cp -r backend/.env backend/.env.backup
   cp backend/config/resources.json backend/config/resources.json.backup
   ```

2. **更新配置**
   ```bash
   cp .env.example backend/.env
   # 编辑 .env 填入实际配置
   ```

3. **重新生成资源**
   ```bash
   python scripts/sync_resources.py --workspace default
   ```

4. **重启服务**
   ```bash
   ./scripts/stop.sh
   ./scripts/start.sh
   ```

详细升级步骤请参考: [V2_MIGRATION_GUIDE.md](./V2_MIGRATION_GUIDE.md)

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| [AGENTS.md](./AGENTS.md) | 项目完整指南 |
| [API.md](./API.md) | API接口文档 |
| [QUICKSTART_V2.md](./QUICKSTART_V2.md) | V2快速启动指南 |
| [V2_MIGRATION_GUIDE.md](./V2_MIGRATION_GUIDE.md) | V1到V2迁移指南 |
| [V2_ADVANCED_CONFIGURATION.md](./V2_ADVANCED_CONFIGURATION.md) | V2高级配置 |
| [docs/SSO_LOGIN_DEBUG_GUIDE.md](./docs/SSO_LOGIN_DEBUG_GUIDE.md) | SSO调试指南 |

---

*文档生成时间: 2026-04-11*  
*基于 Git 提交历史自动生成*
