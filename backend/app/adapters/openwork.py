"""OpenWork adapter for file-based skill and workspace management."""

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import settings


logger = logging.getLogger(__name__)


class OpenWorkAdapter:
    """Adapter for OpenWork server."""

    def __init__(self):
        self.base_url = settings.openwork_base_url.rstrip("/")
        self.token = settings.openwork_token.strip()
        self.host_token = settings.openwork_host_token.strip()
        self.probe_workspace_id = settings.openwork_probe_workspace_id
        self._client: Optional[httpx.AsyncClient] = None
        self._capabilities: Optional[Dict[str, Any]] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self._client

    def _candidate_headers(self) -> List[Tuple[str, Dict[str, str]]]:
        """Build auth strategies for the current configuration."""
        candidates: List[Tuple[str, Dict[str, str]]] = [("anonymous", {})]
        seen: set[Tuple[str, str]] = set()

        if self.token:
            key = ("bearer", self.token)
            seen.add(key)
            candidates.insert(0, ("bearer", {"Authorization": f"Bearer {self.token}"}))

        if self.host_token:
            key = ("host", self.host_token)
            if key not in seen:
                seen.add(key)
                candidates.insert(0, ("host", {"X-OpenWork-Host-Token": self.host_token}))

        # Allow OPENWORK_TOKEN to be treated as a host token if the user only configured one value.
        if self.token and not self.host_token:
            key = ("host", self.token)
            if key not in seen:
                candidates.insert(1, ("host-fallback", {"X-OpenWork-Host-Token": self.token}))

        return candidates

    async def _request_raw(
        self,
        method: str,
        path: str,
        *,
        trace_id: Optional[str] = None,
        allow_retry_on_auth: bool = True,
        **kwargs: Any,
    ) -> Optional[httpx.Response]:
        """Issue a request and retry with alternate auth modes when appropriate."""
        client = await self._get_client()
        base_headers = kwargs.pop("headers", {})
        if trace_id:
            base_headers["X-Trace-ID"] = trace_id

        responses: List[httpx.Response] = []
        for index, (_, auth_headers) in enumerate(self._candidate_headers()):
            if index > 0 and not allow_retry_on_auth:
                break

            merged_headers = dict(base_headers)
            merged_headers.update(auth_headers)

            try:
                response = await client.request(method, path, headers=merged_headers, **kwargs)
            except httpx.HTTPError as e:
                logger.error("OpenWork request failed %s %s: %s", method, path, e)
                return None

            responses.append(response)
            if response.status_code not in (401, 403):
                return response

        return responses[-1] if responses else None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        trace_id: Optional[str] = None,
        allow_retry_on_auth: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Low-level request helper returning JSON, text, or empty dict."""
        response = await self._request_raw(
            method,
            path,
            trace_id=trace_id,
            allow_retry_on_auth=allow_retry_on_auth,
            **kwargs,
        )
        if response is None:
            return {}
        if response.status_code >= 400:
            logger.warning(
                "OpenWork request returned %s for %s %s",
                response.status_code,
                method,
                path,
            )
            return {}
        if not response.content:
            return {}
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return {"raw": response.text}

    async def probe_capabilities(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Probe runtime capabilities of the configured OpenWork server."""
        if self._capabilities is not None and not force_refresh:
            return self._capabilities

        health_response = await self._request_raw("GET", "/health", allow_retry_on_auth=False)
        health_payload: Dict[str, Any] = {}
        if health_response and health_response.status_code < 400 and health_response.content:
            try:
                health_payload = health_response.json()
            except ValueError:
                health_payload = {"raw": health_response.text}

        checks = {
            "workspace_config": f"/workspace/{self.probe_workspace_id}/config",
            "skills": f"/workspace/{self.probe_workspace_id}/skills",
            "commands": f"/workspace/{self.probe_workspace_id}/commands",
            "mcp": f"/workspace/{self.probe_workspace_id}/mcp",
            "audit": f"/workspace/{self.probe_workspace_id}/audit",
            "plugins": f"/workspace/{self.probe_workspace_id}/plugins",
            "events": f"/workspace/{self.probe_workspace_id}/events",
            "files_content": f"/workspace/{self.probe_workspace_id}/files/content",
            "export": f"/workspace/{self.probe_workspace_id}/export",
            "opencode_router": f"/workspace/{self.probe_workspace_id}/opencode-router/bindings",
        }

        routes: Dict[str, Dict[str, Any]] = {}
        for name, path in checks.items():
            response = await self._request_raw("GET", path)
            routes[name] = {
                "path": path,
                "available": bool(response and response.status_code < 400),
                "status_code": response.status_code if response else None,
                "auth_required": bool(response and response.status_code in (401, 403)),
            }

        token_routes: Dict[str, Any] = {"path": "/tokens", "available": False, "status_code": None, "auth_required": False}
        response = await self._request_raw("GET", "/tokens")
        if response is not None:
            token_routes.update(
                {
                    "available": response.status_code < 400,
                    "status_code": response.status_code,
                    "auth_required": response.status_code in (401, 403),
                }
            )

        self._capabilities = {
            "healthy": bool(health_response and health_response.status_code < 400),
            "version": health_payload.get("version"),
            "health": health_payload,
            "auth": {
                "bearer_configured": bool(self.token),
                "host_token_configured": bool(self.host_token),
            },
            "routes": {
                **routes,
                "tokens": token_routes,
            },
        }
        return self._capabilities

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def list_skills(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available skills in workspace."""
        data = await self._request("GET", f"/workspace/{workspace_id}/skills", trace_id=trace_id)
        if isinstance(data, dict):
            if isinstance(data.get("skills"), list):
                skills = data["skills"]
            elif isinstance(data.get("items"), list):
                skills = data["items"]
            else:
                skills = []
        elif isinstance(data, list):
            skills = data
        else:
            skills = []
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
        if not data:
            return {"installed": False}
        if isinstance(data, dict) and "installed" not in data:
            data["installed"] = True
        return data or {"installed": False}

    async def reload_engine(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> bool:
        """Reload OpenWork engine to pick up new skills."""
        data = await self._request("POST", f"/workspace/{workspace_id}/engine/reload", trace_id=trace_id)
        logger.info("Reloaded engine for workspace %s", workspace_id)
        return bool(data == {} or data.get("success", True))

    async def get_workspace_summary(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Return config/summary information for a workspace."""
        data = await self._request("GET", f"/workspace/{workspace_id}/config", trace_id=trace_id)
        if isinstance(data, dict):
            return data
        return {"raw": data}

    async def list_workspace_commands(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace command metadata."""
        data = await self._request("GET", f"/workspace/{workspace_id}/commands", trace_id=trace_id)
        if isinstance(data, dict):
            return data.get("commands", data.get("items", []))
        if isinstance(data, list):
            return data
        return []

    async def list_workspace_mcp(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace MCP integrations."""
        data = await self._request("GET", f"/workspace/{workspace_id}/mcp", trace_id=trace_id)
        if isinstance(data, dict):
            return data.get("items", data.get("mcp", []))
        if isinstance(data, list):
            return data
        return []

    async def list_workspace_audit(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace audit items."""
        data = await self._request("GET", f"/workspace/{workspace_id}/audit", trace_id=trace_id)
        if isinstance(data, dict):
            return data.get("items", data.get("audit", []))
        if isinstance(data, list):
            return data
        return []

    async def list_workspace_plugins(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace plugins."""
        data = await self._request("GET", f"/workspace/{workspace_id}/plugins", trace_id=trace_id)
        if isinstance(data, dict):
            return data.get("items", data.get("plugins", []))
        if isinstance(data, list):
            return data
        return []

    async def list_workspace_events(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workspace events."""
        data = await self._request("GET", f"/workspace/{workspace_id}/events", trace_id=trace_id)
        if isinstance(data, dict):
            return data.get("items", data.get("events", []))
        if isinstance(data, list):
            return data
        return []

    async def probe_opencode_proxy(self, workspace_id: str = "default", trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Probe whether OpenWork exposes opencode-router controls for the workspace."""
        response = await self._request_raw("GET", f"/workspace/{workspace_id}/opencode-router/bindings", trace_id=trace_id)
        return {
            "available": bool(response and response.status_code < 400),
            "status_code": response.status_code if response else None,
            "auth_required": bool(response and response.status_code in (401, 403)),
            "path": f"/workspace/{workspace_id}/opencode-router/bindings",
        }
