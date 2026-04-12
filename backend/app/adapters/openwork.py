"""OpenWork adapter for file-based skill and workspace management."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings


logger = logging.getLogger(__name__)


class OpenWorkAdapter:
    """Adapter for OpenWork server."""

    def __init__(self):
        self.base_url = settings.openwork_base_url.rstrip("/")
        self.token = settings.openwork_token
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        trace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Low-level request helper returning JSON or empty dict."""
        client = await self._get_client()
        headers = kwargs.pop("headers", {})
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        try:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        except httpx.HTTPError as e:
            logger.error("OpenWork request failed %s %s: %s", method, path, e)
            return {}

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def list_skills(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available skills in workspace."""
        data = await self._request("GET", f"/workspace/{workspace_id}/skills", trace_id=trace_id)
        skills = data.get("skills", []) if isinstance(data, dict) else []
        logger.info("Listed %s skills from workspace %s", len(skills), workspace_id)
        return skills

    async def get_skill_status(
        self,
        skill_name: str,
        workspace_id: str = "default",
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get skill installation status."""
        if not skill_name:
            return {"installed": False}
        data = await self._request("GET", f"/workspace/{workspace_id}/skills/{skill_name}", trace_id=trace_id)
        return data or {"installed": False}

    async def reload_engine(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> bool:
        """Reload OpenWork engine to pick up new skills."""
        data = await self._request("POST", f"/workspace/{workspace_id}/engine/reload", trace_id=trace_id)
        logger.info("Reloaded engine for workspace %s", workspace_id)
        return bool(data == {} or data.get("success", True))

    async def get_workspace_summary(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Return summary information for a workspace."""
        return await self._request("GET", f"/workspace/{workspace_id}", trace_id=trace_id)

    async def list_workspace_commands(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace command metadata."""
        data = await self._request("GET", f"/workspace/{workspace_id}/commands", trace_id=trace_id)
        return data.get("commands", []) if isinstance(data, dict) else []

    async def list_workspace_mcp(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace MCP integrations."""
        data = await self._request("GET", f"/workspace/{workspace_id}/mcp", trace_id=trace_id)
        return data.get("items", []) if isinstance(data, dict) else []

    async def list_workspace_audit(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace audit items."""
        data = await self._request("GET", f"/workspace/{workspace_id}/audit", trace_id=trace_id)
        return data.get("items", []) if isinstance(data, dict) else []

    async def probe_opencode_proxy(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Probe whether OpenWork exposes an OpenCode proxy for the workspace."""
        return await self._request("GET", f"/workspace/{workspace_id}/opencode", trace_id=trace_id)
