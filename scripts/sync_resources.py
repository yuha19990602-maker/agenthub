#!/usr/bin/env python3
"""
Skill discovery and resource synchronization script.

Pulls skills from OpenWork, merges them with static resources and overrides,
and writes a unified resources.generated.json that the CatalogService consumes.
"""

import json
import logging
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow importing backend modules when script is run from repo root
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.adapters.openwork import OpenWorkAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sync_resources")


STATIC_PATH = BACKEND_DIR / "config" / "resources.static.json"
OVERRIDES_PATH = BACKEND_DIR / "config" / "resources.overrides.json"
GENERATED_PATH = BACKEND_DIR / "config" / "resources.generated.json"


def load_json(path: Path) -> Any:
    """Load JSON file if it exists."""
    if not path.exists():
        logger.warning("File not found: %s", path)
        if "overrides" in path.name:
            return {"overrides": {}}
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Write JSON file with pretty formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s", path)


def _get_skill_metadata(skill: Dict[str, Any]) -> Dict[str, Any]:
    metadata = skill.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _get_override_for_skill(skill_name: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
    return overrides.get("overrides", {}).get(skill_name, {})


def _resolve_portal_resource_id(skill: Dict[str, Any], workspace_id: str, overrides: Dict[str, Any]) -> str:
    skill_name = skill.get("name") or skill.get("skill_name") or skill.get("id", "unknown")
    metadata = _get_skill_metadata(skill)
    override = _get_override_for_skill(skill_name, overrides)
    return (
        metadata.get("portal_resource_id")
        or override.get("portal_resource_id")
        or f"skill-{skill_name}"
    )


def _skill_entrypoint(skill: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
    skill_name = skill.get("name") or skill.get("skill_name") or skill.get("id", "unknown")
    metadata = _get_skill_metadata(skill)
    return {
        "entrypoint_id": metadata.get("entrypoint_id") or "assistant",
        "title": metadata.get("entrypoint_title") or skill.get("entrypoint_title") or "聊天入口",
        "adapter": "skill_chat",
        "launch_mode": "native",
        "enabled": True,
        "is_default": False,
        "skill_name": skill_name,
        "workspace_id": metadata.get("workspace_id") or workspace_id,
    }


def _merge_entrypoints(existing: List[Dict[str, Any]], discovered: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for entrypoint in existing:
        merged[entrypoint["entrypoint_id"]] = deepcopy(entrypoint)
    for entrypoint in discovered:
        current = merged.get(entrypoint["entrypoint_id"], {})
        current.update(deepcopy(entrypoint))
        merged[entrypoint["entrypoint_id"]] = current
    if merged and not any(item.get("is_default") for item in merged.values()):
        first_key = next(iter(merged))
        merged[first_key]["is_default"] = True
    return list(merged.values())


def normalize_skill(skill: Dict[str, Any], workspace_id: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an OpenWork skill dict into a Portal resource dict."""
    skill_name = skill.get("name") or skill.get("skill_name") or skill.get("id", "unknown")
    metadata = _get_skill_metadata(skill)
    resource_id = _resolve_portal_resource_id(skill, workspace_id, overrides)
    entrypoint = _skill_entrypoint(skill, workspace_id)

    runtime = metadata.get("skill_runtime") or skill.get("skill_runtime") or "prompt_only"
    display_name = metadata.get("display_name") or skill.get("display_name") or skill.get("title") or skill_name

    resource = {
        "id": resource_id,
        "name": display_name,
        "type": "skill_chat",
        "launch_mode": "native",
        "adapter": "skill_chat",
        "resource_kind": "skill",
        "group": "技能助手",
        "description": skill.get("description", ""),
        "enabled": True,
        "tags": skill.get("tags", ["skill"]),
        "config": {
            "skill_name": skill_name,
            "workspace_id": entrypoint["workspace_id"],
            "starter_prompts": skill.get("starter_prompts", []),
            "skill_runtime": runtime,
        },
        "entrypoints": [entrypoint],
        "capabilities": {
            "searchable": True,
            "resumable": True,
            "upload": True,
            "auditable": True,
        },
        "sync_meta": {
            "origin": "openwork",
            "origin_key": f"{workspace_id}:{skill_name}",
            "workspace_id": entrypoint["workspace_id"],
            "version": skill.get("version"),
            "sync_status": "active",
            "last_seen_at": datetime.utcnow().isoformat(),
        },
    }
    return apply_overrides(resource, overrides)


def apply_overrides(resource: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply product-level overrides to a discovered skill resource."""
    skill_name = resource.get("config", {}).get("skill_name")
    if not skill_name:
        return resource

    override = _get_override_for_skill(skill_name, overrides)
    if not override:
        return resource

    merged = deepcopy(resource)
    for key in ("name", "group", "description", "enabled", "tags", "acl", "resource_kind", "recommended_for"):
        if key in override:
            merged[key] = deepcopy(override[key])

    merged_config = deepcopy(merged.get("config", {}))
    for key in ("starter_prompts", "workspace_id", "skill_runtime"):
        if key in override:
            merged_config[key] = deepcopy(override[key])
    merged["config"] = merged_config

    if "entrypoints" in override:
        merged["entrypoints"] = _merge_entrypoints(merged.get("entrypoints", []), override["entrypoints"])
    return merged


def merge_resources(
    static: List[Dict[str, Any]],
    discovered: List[Dict[str, Any]],
    overrides: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Merge static resources with discovered skills."""
    by_id: Dict[str, Dict[str, Any]] = {}

    for item in static:
        by_id[item["id"]] = deepcopy(item)

    for item in discovered:
        resource_id = item["id"]
        if resource_id not in by_id:
            by_id[resource_id] = deepcopy(item)
            continue

        logger.info("Merging discovered entrypoints into existing resource '%s'", resource_id)
        existing = by_id[resource_id]
        existing_entrypoints = existing.get("entrypoints", [])
        discovered_entrypoints = item.get("entrypoints", [])
        existing["entrypoints"] = _merge_entrypoints(existing_entrypoints, discovered_entrypoints)

        existing.setdefault("resource_kind", item.get("resource_kind"))
        existing.setdefault("capabilities", item.get("capabilities"))
        existing.setdefault("recommended_for", item.get("recommended_for"))

        existing_config = deepcopy(existing.get("config", {}))
        discovered_config = deepcopy(item.get("config", {}))
        for key in ("starter_prompts",):
            if key not in existing_config and key in discovered_config:
                existing_config[key] = discovered_config[key]
        existing.setdefault("adapter", item.get("adapter"))
        existing["config"] = existing_config

        override = _get_override_for_skill(item.get("config", {}).get("skill_name", ""), overrides)
        if override:
            by_id[resource_id] = apply_overrides(existing, overrides)

    return list(by_id.values())


def build_generated_resources(skills: List[Dict[str, Any]], workspace_id: str = "default") -> List[Dict[str, Any]]:
    """Build merged generated resources from OpenWork skills and local config."""
    static_resources = load_json(STATIC_PATH)
    overrides = load_json(OVERRIDES_PATH)
    discovered = [normalize_skill(skill, workspace_id, overrides) for skill in skills]
    logger.info("Discovered %s skills from workspace '%s'", len(discovered), workspace_id)
    merged = merge_resources(static_resources, discovered, overrides)
    logger.info("Merged total resources: %s", len(merged))
    return merged


def write_generated_resources(items: List[Dict[str, Any]], output_path: Path = GENERATED_PATH) -> None:
    """Write generated resources to disk."""
    write_json(output_path, items)


def main():
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Sync skills from OpenWork into Portal resource catalog")
    parser.add_argument("--workspace", default="default", help="OpenWork workspace ID")
    args = parser.parse_args()

    async def _run() -> List[Dict[str, Any]]:
        openwork = OpenWorkAdapter()
        try:
            skills = await openwork.list_skills(workspace_id=args.workspace)
        finally:
            await openwork.close()
        return build_generated_resources(skills=skills, workspace_id=args.workspace)

    merged = asyncio.run(_run())
    write_generated_resources(merged, GENERATED_PATH)
    logger.info("Sync complete. %s resources in generated catalog.", len(merged))


if __name__ == "__main__":
    main()
