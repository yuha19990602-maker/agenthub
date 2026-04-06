#!/usr/bin/env python3
"""
Skill discovery and resource synchronization script.

Pulls skills from OpenWork, merges them with static resources and overrides,
and writes a unified resources.generated.json that the CatalogService consumes.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Allow importing backend modules when script is run from repo root
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.adapters.openwork import OpenWorkAdapter
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sync_resources")


# Paths relative to backend/
STATIC_PATH = BACKEND_DIR / "config" / "resources.static.json"
OVERRIDES_PATH = BACKEND_DIR / "config" / "resources.overrides.json"
GENERATED_PATH = BACKEND_DIR / "config" / "resources.generated.json"


def load_json(path: Path) -> Any:
    """Load JSON file if it exists, otherwise return empty dict/list depending on file content hint."""
    if not path.exists():
        logger.warning(f"File not found: {path}")
        if "overrides" in path.name:
            return {"overrides": {}}
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Write JSON file with pretty formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Wrote {path}")


def normalize_skill(skill: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
    """
    Normalize an OpenWork skill dict into a Portal Resource dict.
    OpenWork skill shape is expected to have at least a 'name' field.
    """
    skill_name = skill.get("name") or skill.get("skill_name") or skill.get("id", "unknown")
    resource_id = f"skill-{skill_name}"

    return {
        "id": resource_id,
        "name": skill.get("display_name") or skill.get("title") or skill_name,
        "type": "skill_chat",
        "launch_mode": "native",
        "group": "技能助手",
        "description": skill.get("description", ""),
        "enabled": True,
        "tags": skill.get("tags", ["skill"]),
        "config": {
            "skill_name": skill_name,
            "workspace_id": workspace_id,
            "starter_prompts": skill.get("starter_prompts", []),
        },
        "sync_meta": {
            "origin": "openwork",
            "origin_key": f"{workspace_id}:{skill_name}",
            "workspace_id": workspace_id,
            "version": skill.get("version"),
            "sync_status": "active",
            "last_seen_at": datetime.utcnow().isoformat(),
        },
    }


def apply_overrides(resource: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply product-level overrides to a discovered skill resource."""
    skill_name = resource.get("config", {}).get("skill_name")
    if not skill_name:
        return resource

    override = overrides.get("overrides", {}).get(skill_name)
    if not override:
        return resource

    merged = dict(resource)
    for key in ("name", "group", "description", "enabled", "tags", "acl"):
        if key in override:
            merged[key] = override[key]

    # Merge config overrides (starter_prompts, etc.)
    config_override = {}
    if "starter_prompts" in override:
        config_override["starter_prompts"] = override["starter_prompts"]

    if config_override:
        merged_config = dict(merged.get("config", {}))
        merged_config.update(config_override)
        merged["config"] = merged_config

    return merged


def merge_resources(
    static: List[Dict[str, Any]],
    discovered: List[Dict[str, Any]],
    overrides: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Merge static resources with discovered skills.
    Static resources take precedence by id to allow manual pinning.
    """
    by_id: Dict[str, Dict[str, Any]] = {}

    for item in static:
        by_id[item["id"]] = item

    for item in discovered:
        item = apply_overrides(item, overrides)
        if item["id"] in by_id:
            # If a static resource already exists with the same id, keep static
            logger.info(f"Skipping discovered resource '{item['id']}' because a static entry exists")
            continue
        by_id[item["id"]] = item

    return list(by_id.values())


def build_generated_resources(skills: List[Dict[str, Any]], workspace_id: str = "default") -> List[Dict[str, Any]]:
    """Build merged generated resources from OpenWork skills and local config."""
    discovered = [normalize_skill(s, workspace_id) for s in skills]
    logger.info(f"Discovered {len(discovered)} skills from workspace '{workspace_id}'")

    static_resources = load_json(STATIC_PATH)
    overrides = load_json(OVERRIDES_PATH)

    merged = merge_resources(static_resources, discovered, overrides)
    logger.info(f"Merged total resources: {len(merged)}")
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

    logger.info(f"Sync complete. {len(merged)} resources in generated catalog.")


if __name__ == "__main__":
    main()
