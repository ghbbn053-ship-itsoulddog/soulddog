"""
平台能力注册服务：
- 将 Skill 文件态同步到数据库对象
- 将 MCP registry 同步到数据库对象
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.platform import SkillManifest, MCPServerManifest
from app.services.skill_manager import get_skill_manager
from app.services.mcp_registry import get_mcp_registry
from app.services.mcp_manager import get_mcp_manager


class PlatformRegistryService:
    def sync_skills(self, db: Session, owner_username: str) -> List[SkillManifest]:
        skill_items = get_skill_manager().list_skills(owner_username)
        out: List[SkillManifest] = []
        for item in skill_items:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            record = (
                db.query(SkillManifest)
                .filter(SkillManifest.owner_username == owner_username, SkillManifest.name == name)
                .first()
            )
            if not record:
                record = SkillManifest(owner_username=owner_username, name=name)
                db.add(record)
            record.version = str(item.get("version", "")).strip() or None
            record.description = str(item.get("description", "")).strip() or None
            record.enabled = bool(item.get("enabled", True))
            record.triggers = item.get("triggers", []) or []
            record.tools = item.get("tools", []) or []
            record.source_type = str(item.get("source_type", "yaml")).strip() or "yaml"
            record.source_ref = str(item.get("source_ref", f"skills/{owner_username}/{name}.yaml")).strip()
            record.metadata_json = {
                "updated_at": item.get("updated_at"),
                "input_schema": item.get("input_schema", {}) or {},
                "always_on": bool(item.get("always_on", False)),
                "mode": item.get("mode", "rule"),
                "compatibility_level": item.get("compatibility_level", "direct"),
                "compatibility_notes": item.get("compatibility_notes", []) or [],
                "capabilities": item.get("capabilities", []) or [],
            }
            out.append(record)
        db.commit()
        return out

    def sync_mcp_tools(self, db: Session, owner_username: str) -> List[MCPServerManifest]:
        imported_map = {
            str(item.get("name", "")).strip(): item
            for item in get_mcp_manager().list_tools(owner_username)
            if str(item.get("name", "")).strip()
        }
        tools = get_mcp_registry().list_tools()
        out: List[MCPServerManifest] = []
        for item in tools:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            imported = imported_map.get(name) or {}
            record = (
                db.query(MCPServerManifest)
                .filter(MCPServerManifest.owner_username == owner_username, MCPServerManifest.name == name)
                .first()
            )
            if not record:
                record = MCPServerManifest(owner_username=owner_username, name=name)
                db.add(record)
            record.description = str(item.get("description", "")).strip() or None
            record.kind = str(item.get("kind", "python")).strip().lower() or "python"
            record.enabled = bool(imported.get("enabled", True))
            record.tool_schema = {
                "name": name,
                "description": item.get("description", ""),
                "parameters": item.get("parameters", {}) or {},
                "kind": record.kind,
            }
            record.source_type = str(imported.get("source_type", "registry")).strip() or "registry"
            record.source_ref = str(imported.get("source_ref", "mcp_registry")).strip() or "mcp_registry"
            record.metadata_json = {
                "updated_at": imported.get("updated_at"),
                "owner_username": imported.get("owner_username", owner_username),
                "transport": imported.get("transport", "python" if record.kind == "python" else "http"),
                "compatibility_level": imported.get("compatibility_level", "direct"),
                "compatibility_notes": imported.get("compatibility_notes", []) or [],
                "capabilities": imported.get("capabilities", []) or [],
            }
            out.append(record)
        db.commit()
        return out

    def list_skills(self, db: Session, owner_username: str) -> List[SkillManifest]:
        self.sync_skills(db, owner_username)
        return (
            db.query(SkillManifest)
            .filter(SkillManifest.owner_username == owner_username)
            .order_by(SkillManifest.name.asc())
            .all()
        )

    def list_mcp_tools(self, db: Session, owner_username: str) -> List[MCPServerManifest]:
        self.sync_mcp_tools(db, owner_username)
        return (
            db.query(MCPServerManifest)
            .filter(MCPServerManifest.owner_username == owner_username)
            .order_by(MCPServerManifest.name.asc())
            .all()
        )


_platform_registry_singleton: PlatformRegistryService | None = None


def get_platform_registry_service() -> PlatformRegistryService:
    global _platform_registry_singleton
    if _platform_registry_singleton is None:
        _platform_registry_singleton = PlatformRegistryService()
    return _platform_registry_singleton
