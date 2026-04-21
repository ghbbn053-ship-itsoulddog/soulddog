"""
Skill 管理 API
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.security import enforce_username_isolation
from app.services.skill_manager import get_skill_manager

router = APIRouter(prefix="/api/skills", tags=["Skill管理"])


class SkillUploadRequest(BaseModel):
    username: str
    yaml_content: str


class SkillValidateRequest(BaseModel):
    username: str
    yaml_content: str


class SkillToggleRequest(BaseModel):
    username: str
    enabled: bool


class SkillDeleteRequest(BaseModel):
    username: str


class SkillImportUrlRequest(BaseModel):
    username: str
    url: str


@router.get("/{username}")
async def list_skills(username: str, http_request: Request):
    enforce_username_isolation(http_request, username)
    manager = get_skill_manager()
    return {"success": True, "skills": manager.list_skills(username)}


@router.post("/upload")
async def upload_skill(payload: SkillUploadRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_skill_manager()
    try:
        saved = manager.upload_skill(payload.username, payload.yaml_content)
        return {"success": True, "skill": saved}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


@router.post("/validate")
async def validate_skill_yaml(payload: SkillValidateRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_skill_manager()
    try:
        result = manager.validate_skill_yaml(payload.yaml_content)
        return {"success": True, "meta": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"校验失败: {e}")


@router.post("/import-url")
async def import_skill_from_url(payload: SkillImportUrlRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_skill_manager()
    try:
        saved = manager.import_skill_from_url(payload.username, payload.url)
        return {"success": True, "skill": saved}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {e}")


@router.post("/{skill_name}/enable")
async def set_skill_enabled(skill_name: str, payload: SkillToggleRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_skill_manager()
    try:
        result = manager.set_enabled(payload.username, skill_name, payload.enabled)
        return {"success": True, "skill": result}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {e}")


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str, payload: SkillDeleteRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_skill_manager()
    ok = manager.delete_skill(payload.username, skill_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return {"success": True}
