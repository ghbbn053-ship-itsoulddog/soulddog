"""
Skill 管理 API
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
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


@router.post("/upload-file")
async def upload_skill_file(
    username: str = Form(...),
    skill_file: UploadFile = File(...),
    http_request: Request = None,
):
    """
    通过文件上传安装 skill。
    支持：
    - .yaml/.yml: manifest skill
    - .md/.txt: 文档型 rule skill
    """
    enforce_username_isolation(http_request, username)
    manager = get_skill_manager()
    filename = (skill_file.filename or "").lower()
    if not (filename.endswith(".yaml") or filename.endswith(".yml") or filename.endswith(".md") or filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="仅支持 .yaml/.yml/.md/.txt 文件")
    try:
        content_bytes = await skill_file.read()
        text_content = content_bytes.decode("utf-8", errors="ignore")
        saved = manager.import_skill_from_text(
            username,
            text_content,
            source_type="file",
            source_ref=skill_file.filename or "upload",
            file_name=skill_file.filename or "",
        )
        return {"success": True, "skill": saved, "source": "file"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件安装失败: {e}")


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
