# 下一版本兼容式优化更新说明

本文档记录本次围绕“多入口资源门户”做的兼容式小改版，目标是在不推翻现有 `portal_sid`、`MemoryStore`、`resources.generated.json` 和 `adapter` 架构的前提下，补齐资源入口、用户态和 skill 治理能力。

## 1. 后端模型升级

涉及文件：

- `backend/app/models.py`

本次新增和扩展：

- `ResourceEntrypoint`
  - 为资源补充 `entrypoint_id / title / adapter / launch_mode / skill_name / workspace_id`
- `ResourceCapabilities`
  - 增加 `searchable / resumable / upload / auditable`
- `Resource`
  - 新增 `resource_kind / entrypoints / capabilities / recommended_for`
- `SessionBinding`
  - 新增 `entrypoint_id`
- `AuthSession`
  - 新增 `user_snapshot / profile_tags`
- `SkillInfo`
  - 新增 `workspace_id / version / entrypoint_id / source / status`
- `SessionResumePayload`
  - 新增 `entrypoint_id / workspace_id / skill_name`
- `LaunchRequest`
  - 为资源启动接口补充 `entrypoint_id`

兼容策略：

- 旧资源未配置 `entrypoints` 时仍可运行
- 目录加载阶段会自动补一个 `default` 入口，不要求先手工改 JSON

## 2. 资源目录与推荐能力

涉及文件：

- `backend/app/catalog/service.py`

新增能力：

- `normalize_legacy_resource(resource)`
  - 自动将旧资源补齐默认入口、能力和 `resource_kind`
- `resolve_entrypoint(resource, entrypoint_id)`
  - 统一 launch / resume 的入口解析逻辑
- `get_skill_store_resources()`
  - 不再只看 `type == skill_chat`
  - 现在会识别“带 `skill_chat` entrypoint 的资源”
- `search_resources(query, user)`
  - 支持基于 `name / description / tags / group / skill_name / entrypoint` 的简单关键词搜索
- `recommend_resources(user, recent, favorites, profile_tags)`
  - 提供 ACL 优先的规则推荐

## 3. Skill 同步与多入口合并

涉及文件：

- `scripts/sync_resources.py`
- `backend/app/catalog/sync_service.py`

本次同步链路优化：

- discovered skill 不再在“同 ID”时直接跳过
- 改为将 discovered skill 的 native assistant 入口合并进已有资源
- 支持从以下优先级解析 `portal_resource_id`
  - `metadata.portal_resource_id`
  - overrides 配置
  - 默认 `skill-<skill_name>`
- discovered resource 会补齐：
  - `resource_kind`
  - `entrypoints`
  - `capabilities`
  - `sync_meta`

效果：

- 旧 iframe / websdk 资源可以逐步获得 assistant 入口
- skill 不再被限制为“只能是独立资源”

## 4. OpenCode / Skill / OpenWork Adapter 增强

涉及文件：

- `backend/app/adapters/opencode.py`
- `backend/app/adapters/skill_chat.py`
- `backend/app/adapters/openwork.py`

主要改动：

- `OpenCodeAdapter.send_message()` 和 `send_message_stream()`
  - 新增 `agent / tools / extra_body` 扩展参数
- `SkillChatAdapter`
  - 发消息时接受 `workspace_id / entrypoint_id`
  - 将入口元信息经 `extra_body` 传递给 OpenCode
  - 运行时不再依赖仅存在于进程内的 skill 热缓存
- `OpenWorkAdapter`
  - 新增底层 `_request()`
  - 新增 workspace 级 wrapper：
    - `get_workspace_summary()`
    - `list_workspace_commands()`
    - `list_workspace_mcp()`
    - `list_workspace_audit()`
    - `probe_opencode_proxy()`

## 5. Auth Session 与用户态

涉及文件：

- `backend/app/auth/service.py`
- `backend/app/auth/deps.py`
- `backend/app/store/memory_store.py`

本次优化：

- 登录时在 `AuthSession` 固化 `user_snapshot`
- 自动生成基础 `profile_tags`
- 请求鉴权时优先从 `user_snapshot` 还原用户，只有缺字段时才回查 `user_repo`
- `MemoryStore` 新增用户态存储：
  - `recent_resources`
  - `favorite_resources`
  - `usage_events`
  - `profile_tags`

当前已用于支撑：

- 最近使用
- 收藏资源
- 规则推荐
- usage event 记录

## 6. 主 API 链路升级

涉及文件：

- `backend/app/main.py`

资源启动与恢复：

- `POST /api/resources/{id}/launch`
  - 支持 `entrypoint_id`
  - 按入口解析 `adapter / launch_mode / workspace_id / skill_name`
  - `SessionBinding` 现在会落 `entrypoint_id`
- `GET /api/sessions/{id}/resume`
  - 返回 `entrypoint_id / workspace_id / skill_name`

新增资源接口：

- `GET /api/resources/search?q=`
- `GET /api/resources/recent`
- `GET /api/resources/favorites`
- `POST /api/resources/{id}/favorite`
- `DELETE /api/resources/{id}/favorite`
- `GET /api/resources/recommended`

技能接口增强：

- `GET /api/skills`
  - 支持 `workspace_id / q / installed`
  - 由 Portal skill resources 与 OpenWork workspace skills 本地合并生成 richer 视图

使用记录：

- launch / resume / send_message / send_message_stream 都会写 usage event

## 7. 前端类型、API 与交互升级

涉及文件：

- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/ResourceSidebar.tsx`
- `frontend/src/components/SessionSidebar.tsx`

主要更新：

- `types.ts`
  - 补齐 `entrypoints / capabilities / resource_kind`
  - 扩展 `SkillInfo / SessionResumePayload / LaunchResponse / PortalSession`
- `api.ts`
  - `launchResource(id, entrypointId?)`
  - 新增 `searchResources / listRecentResources / listFavoriteResources / addFavorite / removeFavorite / listRecommendedResources`
  - `skillApi.listSkills(params)`
- `App.tsx`
  - 启动资源时支持默认入口和指定入口
  - 恢复会话时保留 `entrypoint_id`
  - 同步加载推荐、最近和收藏资源
- `ResourceSidebar.tsx`
  - 新增搜索框
  - 新增推荐、最近、收藏 section
  - 新增资源模式 badge
  - 多入口资源支持按入口直接启动
  - 支持收藏/取消收藏
- `SessionSidebar.tsx`
  - 会话项显示 `entrypoint_id`
  - 会话项显示 `workspace_id` 或 `skill_name`

## 8. 验证结果

本次已执行的验证：

- `python -m compileall backend/app scripts/sync_resources.py`
- `npm run build`
- `backend/tests/test_api_simple.py`

结果：

- 后端编译通过
- 前端构建通过
- 后端简化 API 冒烟测试通过

## 9. 当前版本边界

本次仍然保持以下边界不变：

- 未引入 Postgres 资源注册中心
- 未将 native chat 主链路整体切到 OpenWork proxy
- 未引入 LLM 画像推荐
- 未推翻现有 Portal session / binding / resource snapshot 架构

因此这次更新的定位是：

从“单入口资源门户”升级为“可治理的多入口资源门户”，并为后续 `bridge_api`、workspace 管理、资源治理和推荐体系打基础。
