"""Runtime resource sync service."""

from pathlib import Path
from typing import Any, Dict, List

from ..adapters.openwork import OpenWorkAdapter
from ..config import settings
from .service import catalog_service


class ResourceSyncService:
    """Syncs generated resources from OpenWork and reloads the in-process catalog."""

    def __init__(self) -> None:
        self._output_path = Path(settings.resources_path)

    async def sync(self, workspace_id: str, operator: str) -> List[Dict[str, Any]]:
        """Build generated resources, write them, and reload catalog."""
        from scripts.sync_resources import build_generated_resources, write_generated_resources

        openwork = OpenWorkAdapter()
        try:
            skills = await openwork.list_skills(workspace_id=workspace_id)
        finally:
            await openwork.close()

        merged = build_generated_resources(skills=skills, workspace_id=workspace_id)
        write_generated_resources(merged, self._output_path)
        catalog_service.reload_generated_resources()
        return merged


resource_sync_service = ResourceSyncService()
