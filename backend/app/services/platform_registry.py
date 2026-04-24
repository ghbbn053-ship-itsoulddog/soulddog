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
            record.source_type = "yaml"
            record.source_ref = f"skills/{owner_username}/{name}.yaml"
            record.metadata_json = {"updated_at": item.get("updated_at")}
            out.append(record)
        db.commit()
        return out

    def sync_mcp_tools(self, db: Session, owner_username: str) -> List[MCPServerManifest]:
        tools = get_mcp_registry().list_tools()
        out: List[MCPServerManifest] = []
        for item in tools:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
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
            record.enabled = True
            record.tool_schema = {
                "name": name,
                "description": item.get("description", ""),
                "parameters": item.get("parameters", {}) or {},
                "kind": record.kind,
            }
            record.source_type = "registry"
            record.source_ref = "mcp_registry"
            record.metadata_json = {}
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
