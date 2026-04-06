"""Resource catalog service"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import HTTPException, status

from ..models import Resource, ResourceType, LaunchMode
from ..acl.service import acl_service
from ..config import settings


logger = logging.getLogger(__name__)


class CatalogService:
    """Service for managing resource catalog"""

    def __init__(self):
        self.resources_path = Path(settings.resources_path)
        self._resources: Optional[List[Resource]] = None

    def load_resources(self) -> List[Resource]:
        """
        Load resources from configuration file
        """
        if self._resources is not None:
            return self._resources

        try:
            with open(self.resources_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._resources = [Resource(**item) for item in data]
            logger.info(f"Loaded {len(self._resources)} resources from {self.resources_path}")

            return self._resources

        except FileNotFoundError:
            logger.error(f"Resources file not found: {self.resources_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse resources file: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load resources: {e}")
            return []

    def get_resources(self, force_reload: bool = False) -> List[Resource]:
        """
        Get all resources
        """
        if force_reload:
            self._resources = None

        return self.load_resources()

    def get_resource_by_id(self, resource_id: str) -> Optional[Resource]:
        """
        Get resource by ID
        """
        resources = self.get_resources()
        for resource in resources:
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
        """
        Get resources grouped by group name
        """
        resources = self.get_resources()
        groups: Dict[str, List[Resource]] = {}

        for resource in resources:
            group = resource.group or "Other"
            if group not in groups:
                groups[group] = []
            groups[group].append(resource)

        return groups

    def get_resources_by_type(self, resource_type: ResourceType) -> List[Resource]:
        """
        Get resources by type
        """
        resources = self.get_resources()
        return [r for r in resources if r.type == resource_type]

    def filter_accessible_resources(self, user_emp_no: str, user_roles: List[str], user_dept: str) -> List[Resource]:
        """
        Filter resources accessible to user
        """
        from ..models import UserCtx

        # Create temporary user context for ACL check
        user = UserCtx(
            emp_no=user_emp_no,
            name=f"User-{user_emp_no}",
            dept=user_dept,
            roles=user_roles
        )

        resources = self.get_resources()
        return acl_service.filter_accessible_resources(resources, user)

    def get_skill_resources(self) -> List[Resource]:
        """
        Get all skill-type resources
        """
        resources = self.get_resources()
        return [r for r in resources if r.type == ResourceType.SKILL_CHAT]

    def get_websdk_resources(self) -> List[Resource]:
        """
        Get all WebSDK-type resources
        """
        resources = self.get_resources()
        return [r for r in resources if r.launch_mode == LaunchMode.WEBSDK]


# Global catalog service instance
catalog_service = CatalogService()
