"""Resource catalog service."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from ..acl.service import acl_service
from ..config import settings
from ..models import (
    LaunchMode,
    Resource,
    ResourceCapabilities,
    ResourceEntrypoint,
    ResourceType,
    UserCtx,
)


logger = logging.getLogger(__name__)


class CatalogService:
    """Service for managing resource catalog."""

    def __init__(self):
        self.resources_path = Path(settings.resources_path)
        self._resources: Optional[List[Resource]] = None

    @staticmethod
    def _infer_resource_kind(resource: Resource) -> str:
        if resource.resource_kind:
            return resource.resource_kind
        if resource.type in (ResourceType.DIRECT_CHAT, ResourceType.OPENAI_COMPATIBLE_V1):
            return "chat"
        if resource.type == ResourceType.SKILL_CHAT:
            return "skill"
        if resource.type == ResourceType.KB_WEBSDK:
            return "kb"
        if resource.type == ResourceType.AGENT_WEBSDK:
            return "agent"
        return "integration"

    @staticmethod
    def _infer_capabilities(resource: Resource) -> ResourceCapabilities:
        if resource.capabilities:
            return resource.capabilities
        return ResourceCapabilities(
            searchable=True,
            resumable=True,
            upload=resource.launch_mode == LaunchMode.NATIVE,
            auditable=True,
        )

    @staticmethod
    def normalize_legacy_resource(resource: Resource) -> Resource:
        """Backfill default entrypoint and optional fields for legacy resources."""
        resource.resource_kind = CatalogService._infer_resource_kind(resource)
        resource.capabilities = CatalogService._infer_capabilities(resource)
        if resource.entrypoints:
            has_default = any(item.is_default for item in resource.entrypoints if item.enabled)
            if not has_default:
                for index, item in enumerate(resource.entrypoints):
                    if item.enabled:
                        resource.entrypoints[index].is_default = True
                        break
            return resource

        adapter = resource.adapter or CatalogService._default_adapter_for_type(resource.type)
        title = "打开应用" if resource.launch_mode != LaunchMode.NATIVE else "聊天入口"
        resource.entrypoints = [
            ResourceEntrypoint(
                entrypoint_id="default",
                title=title,
                adapter=adapter,
                launch_mode=resource.launch_mode,
                enabled=resource.enabled,
                is_default=True,
                skill_name=resource.config.skill_name,
                workspace_id=resource.config.workspace_id,
            )
        ]
        return resource

    @staticmethod
    def _default_adapter_for_type(resource_type: ResourceType) -> str:
        mapping = {
            ResourceType.DIRECT_CHAT: "opencode",
            ResourceType.SKILL_CHAT: "skill_chat",
            ResourceType.KB_WEBSDK: "websdk",
            ResourceType.AGENT_WEBSDK: "websdk",
            ResourceType.IFRAME: "iframe",
            ResourceType.OPENAI_COMPATIBLE_V1: "openai_compatible",
        }
        return mapping.get(resource_type, "opencode")

    def load_resources(self) -> List[Resource]:
        """Load resources from configuration file."""
        if self._resources is not None:
            return self._resources

        try:
            with open(self.resources_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._resources = [
                self.normalize_legacy_resource(Resource(**item))
                for item in data
            ]
            logger.info("Loaded %s resources from %s", len(self._resources), self.resources_path)
            return self._resources

        except FileNotFoundError:
            logger.error("Resources file not found: %s", self.resources_path)
            return []
        except json.JSONDecodeError as e:
            logger.error("Failed to parse resources file: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to load resources: %s", e)
            return []

    def get_resources(self, force_reload: bool = False) -> List[Resource]:
        """Get all resources."""
        if force_reload:
            self._resources = None
        return self.load_resources()

    def get_resource_by_id(self, resource_id: str) -> Optional[Resource]:
        """Get resource by ID."""
        for resource in self.get_resources():
            if resource.id == resource_id:
                return resource
        return None

    def get_resource_or_none(self, resource_id: str) -> Optional[Resource]:
        """Alias helper for clearer call sites."""
        return self.get_resource_by_id(resource_id)

    def get_resource_or_raise(self, resource_id: str) -> Resource:
        """Get resource by ID or raise 404."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resource not found: {resource_id}",
            )
        return resource

    def reload_generated_resources(self) -> List[Resource]:
        """Reload generated resource catalog from disk."""
        self._resources = None
        return self.get_resources(force_reload=True)

    def get_resources_by_group(self) -> Dict[str, List[Resource]]:
        """Get resources grouped by group name."""
        groups: Dict[str, List[Resource]] = {}
        for resource in self.get_resources():
            group = resource.group or "Other"
            groups.setdefault(group, []).append(resource)
        return groups

    def get_resources_by_type(self, resource_type: ResourceType) -> List[Resource]:
        """Get resources by type."""
        return [r for r in self.get_resources() if r.type == resource_type]

    def filter_accessible_resources(self, user_emp_no: str, user_roles: List[str], user_dept: str) -> List[Resource]:
        """Filter resources accessible to user."""
        user = UserCtx(
            emp_no=user_emp_no,
            name=f"User-{user_emp_no}",
            dept=user_dept,
            roles=user_roles,
        )
        return acl_service.filter_accessible_resources(self.get_resources(), user)

    def resolve_entrypoint(self, resource: Resource, entrypoint_id: Optional[str] = None) -> ResourceEntrypoint:
        """Resolve the selected entrypoint for launch or resume."""
        entrypoints = [item for item in resource.entrypoints if item.enabled]
        if not entrypoints:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resource '{resource.id}' has no enabled entrypoints",
            )
        if entrypoint_id:
            for item in entrypoints:
                if item.entrypoint_id == entrypoint_id:
                    return item
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entrypoint not found: {entrypoint_id}",
            )
        for item in entrypoints:
            if item.is_default:
                return item
        return entrypoints[0]

    def get_skill_resources(self) -> List[Resource]:
        """Get all skill-type resources, including multi-entry resources."""
        resources = []
        for resource in self.get_resources():
            if resource.type == ResourceType.SKILL_CHAT:
                resources.append(resource)
                continue
            if any(item.adapter == "skill_chat" for item in resource.entrypoints):
                resources.append(resource)
        return resources

    def get_skill_store_resources(self) -> List[Resource]:
        """Get resources that expose a skill-chat entrypoint."""
        return self.get_skill_resources()

    def get_websdk_resources(self) -> List[Resource]:
        """Get all WebSDK-type resources."""
        return [r for r in self.get_resources() if r.launch_mode == LaunchMode.WEBSDK]

    def search_resources(self, query: str, user: UserCtx) -> List[Resource]:
        """Search accessible resources using simple keyword matching."""
        terms = [term for term in query.lower().split() if term]
        if not terms:
            return acl_service.filter_accessible_resources(self.get_resources(), user)

        results: List[tuple[int, Resource]] = []
        for resource in acl_service.filter_accessible_resources(self.get_resources(), user):
            haystack_parts = [
                resource.name,
                resource.description,
                resource.group,
                resource.resource_kind or "",
                " ".join(resource.tags),
                resource.config.skill_name or "",
            ]
            for entrypoint in resource.entrypoints:
                haystack_parts.extend(
                    [
                        entrypoint.title,
                        entrypoint.entrypoint_id,
                        entrypoint.skill_name or "",
                        entrypoint.workspace_id or "",
                    ]
                )
            haystack = " ".join(haystack_parts).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                results.append((score, resource))

        results.sort(key=lambda item: (-item[0], item[1].name))
        return [resource for _, resource in results]

    def recommend_resources(
        self,
        user: UserCtx,
        recent_resource_ids: Optional[List[str]] = None,
        favorite_resource_ids: Optional[List[str]] = None,
        profile_tags: Optional[List[str]] = None,
    ) -> List[Resource]:
        """Rule-based accessible resource recommendations."""
        recent_resource_ids = recent_resource_ids or []
        favorite_resource_ids = favorite_resource_ids or []
        profile_tags = profile_tags or []
        accessible = acl_service.filter_accessible_resources(self.get_resources(), user)

        scored: List[tuple[int, Resource]] = []
        for resource in accessible:
            score = 0
            if resource.id in favorite_resource_ids:
                score += 5
            if resource.id in recent_resource_ids:
                score += 3
            if resource.resource_kind == "skill":
                score += 1
            if resource.launch_mode == LaunchMode.NATIVE and "prefers_native_chat" in profile_tags:
                score += 2
            if resource.config.workspace_id == "hr" and "uses_hr_workspace" in profile_tags:
                score += 2
            if "data" in " ".join(resource.tags).lower() and "frequent_data_analysis" in profile_tags:
                score += 2

            recommended_for = resource.recommended_for or {}
            if user.dept in recommended_for.get("depts", []):
                score += 2
            if any(role in recommended_for.get("roles", []) for role in user.roles):
                score += 2

            if score > 0:
                scored.append((score, resource))

        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [resource for _, resource in scored]


catalog_service = CatalogService()
