"""
对话 API - AI 聊天接口（支持 Function Calling）
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging
import json
import asyncio
import threading
import re
import time
from collections import Counter

from app.models import get_db, User, Conversation, Message, EducationData, EducationSyncSnapshot
from app.services import get_model_provider_for_user, get_vector_store
from app.services.model_provider import UnifiedModelProvider
from app.services.education_normalizer import build_payload_from_education_data_record
from app.services.workspace_knowledge import get_workspace_knowledge_service
from app.services.skill_router import build_skill_prompt_hint, explain_skill_matches
from app.services.agent_runtime import get_agent_runtime
from app.security import enforce_username_isolation
from app.core.observability import (
    CHAT_STREAM_REQUESTS_TOTAL,
    CHAT_STREAM_ABORTED_TOTAL,
    CHAT_STREAM_DURATION,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["对话"])


def _infer_rag_filters(question: str) -> dict:
    """
    从问题文本中提取 RAG 过滤条件：
    - data_types: 成绩/课表/考试/培养方案/学业进度/个人信息
    - semester: 形如 2025-2026-2
    """
    q = (question or "").lower()
    data_types = []
    mapping = [
        (["课表", "schedule"], "schedule"),
        (["成绩", "grade", "绩点"], "grade"),
        (["考试", "exam"], "exam"),
        (["培养方案", "training"], "training_plan"),
        (["学业进度", "进度"], "academic_progress"),
        (["个人信息", "我是谁", "基本信息"], "personal_info"),
    ]
    for keywords, dt in mapping:
        if any(k in q for k in keywords):
            data_types.append(dt)

    semester = ""
    m = re.search(r"(20\d{2}-20\d{2}-[12])", question or "")
    if m:
        semester = m.group(1)

    return {"data_types": data_types, "semester": semester}


def _is_identity_question(question: str) -> bool:
    q = (question or "").strip()
    keywords = ["你是谁", "我是谁", "个人信息", "我的信息", "我的学号", "我的专业", "我的班级", "我的学院"]
    return any(k in q for k in keywords)


def _is_location_question(question: str) -> bool:
    q = (question or "").strip()
    keywords = ["哪里上课", "在哪上课", "上课地点", "教室", "校区", "广州校区", "佛山校区", "三水校区", "在哪里上课"]
    return any(k in q for k in keywords)


def _extract_building_name(location: str) -> str:
    text = (location or "").strip()
    if not text:
        return ""
    for sep in ["(", "（", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]:
        idx = text.find(sep)
        if idx > 0:
            return text[:idx].strip()
    return text


def _join_natural_text(parts: List[str]) -> str:
    return "，".join([part.strip("，。 ") for part in parts if part and part.strip("，。 ")])


def _format_examples(items: List[str], limit: int = 8) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return ""
    unique_items = list(dict.fromkeys(cleaned))
    shown = unique_items[:limit]
    suffix = "等" if len(unique_items) > limit else ""
    return "、".join(shown) + suffix


def _build_grounded_answer(question: str, normalized_payload: dict) -> Optional[str]:
    personal = normalized_payload.get("个人信息", {}) or {}
    schedule_info = normalized_payload.get("课表信息", {}) or {}
    schedule_courses = schedule_info.get("课程列表", []) or []
    semester = (schedule_info.get("学期", "") or "").strip()

    if _is_identity_question(question):
        sentence_parts = []
        if personal.get("name") and personal.get("student_id"):
            sentence_parts.append(f"按当前教务数据，你是{personal.get('name')}，学号 {personal.get('student_id')}")
        elif personal.get("name"):
            sentence_parts.append(f"按当前教务数据，姓名是 {personal.get('name')}")
        elif personal.get("student_id"):
            sentence_parts.append(f"按当前教务数据，学号是 {personal.get('student_id')}")

        if personal.get("major"):
            sentence_parts.append(f"专业是 {personal.get('major')}")
        if personal.get("class"):
            sentence_parts.append(f"班级是 {personal.get('class')}")
        if personal.get("department"):
            sentence_parts.append(f"学院字段当前记录为 {personal.get('department')}")

        natural_summary = _join_natural_text(sentence_parts)
        if natural_summary:
            return f"{natural_summary}。以上内容只复述当前已同步的教务字段，不补充未验证信息。"

    if _is_location_question(question):
        if not schedule_courses:
            return "当前缓存课表中没有可用的上课地点数据，无法判断上课地点或校区。"

        locations = [str(c.get("地点", "")).strip() for c in schedule_courses if str(c.get("地点", "")).strip()]
        buildings = [_extract_building_name(loc) for loc in locations if _extract_building_name(loc)]
        building_counter = Counter(buildings)
        unique_locations = list(dict.fromkeys(locations))
        location_examples = _format_examples(unique_locations, limit=8)
        building_examples = _format_examples(
            [f"{name}（{count}次）" for name, count in building_counter.most_common(5)],
            limit=5,
        )

        opening = f"按当前课表记录，{semester} 能直接确认的是教室和楼栋信息" if semester else "按当前课表记录，能直接确认的是教室和楼栋信息"
        detail_parts = []
        if location_examples:
            detail_parts.append(f"目前出现过的上课地点包括 {location_examples}")
        if building_examples:
            detail_parts.append(f"出现较多的楼栋有 {building_examples}")
        detail_text = "；".join(detail_parts) if detail_parts else "但当前没有可读的地点明细"

        return (
            f"{opening}，{detail_text}。"
            "不过现有数据没有明确的“广州校区/佛山校区”字段，"
            "所以我不能仅凭楼名去判断校区，也不会补充导航、签到、WiFi、开放时间这类未验证信息。"
        )

    return None


def _build_workspace_context(db: Session, username: str, question: str, session_store=None, workspace_id: int | None = None) -> List[dict]:
    try:
        svc = get_workspace_knowledge_service()
        workspaces = svc.list_workspaces(db, username)
        if not workspaces:
            return []
        selected_id = workspace_id
        if selected_id is None and session_store:
            pref = session_store.get_user_workspace_preference(username) or {}
            selected_id = pref.get("workspace_id")
        workspace = next((item for item in workspaces if item.id == selected_id), None) or workspaces[0]
        hits = svc.search_workspace(db, username, workspace.id, question, top_k=5)
        return hits or []
    except Exception as e:
        logger.warning(f"工作区知识检索失败: {e}")
        return []


def _format_context_source(item: dict) -> str:
    source = str(item.get("source", "") or "").strip()
    title = str(item.get("title", "") or "").strip()
    document_id = item.get("document_id")
    chunk_index = item.get("chunk_index")
    score = item.get("score")

    if source.startswith("workspace:"):
        parts = source.split(":", 2)
        workspace_part = parts[1] if len(parts) > 1 else "unknown"
        title_part = title or (parts[2] if len(parts) > 2 else "未知文档")
        query_parts = []
        if document_id is not None:
            query_parts.append(f"doc={document_id}")
        if chunk_index is not None:
            query_parts.append(f"chunk={chunk_index}")
        if score is not None:
            try:
                query_parts.append(f"score={float(score):.3f}")
            except Exception:
                pass
        query = f"?{'&'.join(query_parts)}" if query_parts else ""
        return f"knowledge://workspace/{workspace_part}/{title_part}{query}"

    if source:
        return source
    if title:
        return f"knowledge://workspace/unknown/{title}"
    return "knowledge://workspace/unknown/untitled"


def _render_workspace_rag_context(workspace_hits: List[dict]) -> str:
    parts = []
    for idx, item in enumerate(workspace_hits[:5], start=1):
        title = str(item.get("title", "") or "未知标题").strip()
        content = str(item.get("content", "") or item.get("text", "") or "").strip()
        source = _format_context_source(item)
        if not content:
            continue
        parts.append(f"工作区知识[{idx}]\n标题: {title}\n来源: {source}\n内容: {content}")
    return "\n\n".join(parts)


def _collect_context_sources(*contexts: List[dict]) -> List[str]:
    sources: List[str] = []
    seen = set()
    for context in contexts:
        for item in context or []:
            source = _format_context_source(item)
            if source in seen:
                continue
            seen.add(source)
            sources.append(source)
    return sources


def _collect_context_highlights(*contexts: List[dict]) -> List[dict]:
    highlights: List[dict] = []
    seen = set()
    for context in contexts:
        for item in context or []:
            source = _format_context_source(item)
            key = (source, item.get("chunk_index"), item.get("document_id"))
            if key in seen:
                continue
            seen.add(key)
            content = str(item.get("content", "") or item.get("text", "") or "").strip()
            snippet = content[:220]
            if len(content) > 220:
                snippet += "..."
            highlights.append(
                {
                    "source": source,
                    "title": str(item.get("title", "") or "未知标题").strip(),
                    "snippet": snippet,
                    "document_id": item.get("document_id"),
                    "chunk_index": item.get("chunk_index"),
                    "score": item.get("score"),
                }
            )
    return highlights[:5]


def _apply_workspace_context_to_conversation(conversation: Conversation, workspace_id: int | None):
    meta = dict(conversation.conversation_meta or {})
    if workspace_id:
        meta["workspace_id"] = int(workspace_id)
    conversation.conversation_meta = meta


def _build_message_meta(base: dict | None = None, workspace_id: int | None = None) -> dict:
    meta = dict(base or {})
    if workspace_id:
        meta["workspace_id"] = int(workspace_id)
    return meta


async def _prepare_runtime_hint(
    username: str,
    message: str,
    session_store,
    workspace_id: int | None,
) -> tuple[str, List[dict]]:
    try:
        prepared = await get_agent_runtime().build_chat_runtime_context(
            username=username,
            message=message,
            session_store=session_store,
            workspace_id=workspace_id,
        )
        return prepared.get("system_context", "") or "", prepared.get("tool_trace", []) or []
    except Exception as e:
        logger.warning(f"运行态提示构建失败: {e}")
        return "", []


# ============ 数据模型 ============

class ChatRequest(BaseModel):
    """聊天请求"""
    username: str
    message: str
    conversation_id: Optional[int] = None
    workspace_id: Optional[int] = None
    override_provider: Optional[str] = None
    override_model: Optional[str] = None
    override_api_base: Optional[str] = None
    override_api_key: Optional[str] = None
    reasoning_mode: Optional[str] = "standard"
    show_thinking: Optional[bool] = False
    execution_mode: Optional[str] = "chat"
    agent_framework: Optional[str] = "openai_agents"


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    message: str
    conversation_id: int
    sources: List[str] = []
    highlights: List[dict] = []
    tool_calls: List[dict] = []
    tool_trace: List[dict] = []
    usage: dict = {}


class ConversationResponse(BaseModel):
    """对话列表响应"""
    id: int
    title: str
    created_at: str
    workspace_id: Optional[int] = None


# ============ API 接口 ============

@router.post("/send", response_model=ChatResponse)
async def send_message(request: ChatRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    发送消息给 AI
    
    优先级：
    1. 工具调用（Function Calling）— 用户已登录时，AI 自主决定是否调用爬虫工具
    2. RAG 兜底 — 无工具调用时，使用向量库检索已缓存数据
    3. 直接对话 — 无数据时纯 AI 对话
    """
    try:
        enforce_username_isolation(http_request, request.username)
        session_store = getattr(http_request.app.state, 'session_store', None)
        model_svc = get_model_provider_for_user(request.username, session_store)
        if (request.override_provider or "").strip():
            model_svc = UnifiedModelProvider(
                provider_name=(request.override_provider or "").strip().lower(),
                model=(request.override_model or "").strip() or None,
                api_base=(request.override_api_base or "").strip() or None,
                api_key=(request.override_api_key or "").strip() or None,
            )
        vec_store = get_vector_store()

        # 1. 查找或创建用户
        user = db.query(User).filter(User.username == request.username).first()
        if not user:
            user = User(username=request.username, name=request.username)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # 2. 查找或创建对话
        if request.conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user.id
            ).first()
            if not conversation:
                raise HTTPException(status_code=404, detail="对话不存在")
        else:
            title = request.message[:20] + "..." if len(request.message) > 20 else request.message
            conversation = Conversation(user_id=user.id, title=title)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        _apply_workspace_context_to_conversation(conversation, request.workspace_id)
        db.add(conversation)
        db.commit()
        
        # 3. 保存用户消息
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            message_meta=_build_message_meta(workspace_id=request.workspace_id),
        )
        db.add(user_msg)
        db.commit()
        
        # 4. 获取历史对话（最近5轮 = 10条消息）
        history_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at.desc()).limit(10).all()
        
        history = []
        for msg in reversed(history_messages):
            history.append({"role": msg.role, "content": msg.content})
        
        # 5. 构建工具上下文（从 SessionStore 获取用户 session）
        user_session_data = session_store.get_user_session(request.username) if session_store else None
        
        tools_context = None
        if user_session_data:
            tools_context = {
                "session": user_session_data["session"],
                "server_url": user_session_data["server_url"],
                "username": request.username
            }
        skill_context = build_skill_prompt_hint(request.username, request.message)
        skill_matches = explain_skill_matches(request.username, request.message)
        runtime_hint, runtime_tool_trace = await _prepare_runtime_hint(
            request.username,
            request.message,
            session_store,
            request.workspace_id,
        )
        history_for_model = history
        system_blocks = [block for block in [skill_context, runtime_hint] if block.strip()]
        if system_blocks:
            history_for_model = [{"role": "system", "content": "\n\n".join(system_blocks)}] + history
        
        ai_result = None

        if (request.execution_mode or "chat").strip().lower() == "agent":
            logger.info(f"【Chat】用户 {request.username} 使用 Agent Runtime 模式")
            runtime = get_agent_runtime()
            ai_result = await runtime.run(
                username=request.username,
                message=request.message,
                framework=(request.agent_framework or "openai_agents").strip().lower(),
                session_store=session_store,
                workspace_id=request.workspace_id,
            )

        # 6. 优先使用工具调用（Function Calling）
        if not ai_result and getattr(model_svc, "available", False) and tools_context:
            logger.info(f"【Chat】用户 {request.username} 使用工具调用模式")
            ai_result = model_svc.chat_with_tools(
                messages=history_for_model,
                tools_context=tools_context
            )
        
        # 7. 工具调用不可用或失败时，尝试 RAG 兜底
        if not ai_result or not ai_result.get("success"):
            edu_data = db.query(EducationData).filter(EducationData.user_id == user.id).first()
            context = []
            workspace_context = _build_workspace_context(db, request.username, request.message, session_store=session_store, workspace_id=request.workspace_id)
            normalized_payload = None
            if edu_data:
                try:
                    normalized_payload = build_payload_from_education_data_record(edu_data)
                    grounded_answer = _build_grounded_answer(request.message, normalized_payload)
                    if grounded_answer:
                        ai_result = {
                            "success": True,
                            "content": grounded_answer,
                            "sources": ["grounded_structured_data"],
                            "tool_calls": [],
                            "usage": {},
                            "skill_matches": skill_matches,
                            "tool_trace": runtime_tool_trace,
                        }
                except Exception as e:
                    logger.warning(f"结构化直答构建失败: {e}")
            if edu_data and vec_store.available and getattr(model_svc, "available", False):
                try:
                    query_embedding = model_svc.generate_embedding(request.message)
                    if query_embedding:
                        filters = _infer_rag_filters(request.message)
                        active_snapshot = (
                            db.query(EducationSyncSnapshot)
                            .filter(
                                EducationSyncSnapshot.user_id == user.id,
                                EducationSyncSnapshot.status == "success",
                                EducationSyncSnapshot.is_active == True,
                            )
                            .order_by(EducationSyncSnapshot.created_at.desc())
                            .first()
                        )
                        context = vec_store.search(
                            user.id,
                            query_embedding,
                            top_k=8,
                            data_types=filters["data_types"],
                            semester=filters["semester"],
                            sync_key=active_snapshot.sync_key if active_snapshot else "",
                        )
                except Exception as e:
                    logger.warning(f"向量检索失败: {e}")
            
            merged_context = []
            if context:
                merged_context.extend(context)
            if workspace_context:
                merged_context.extend(workspace_context)
            rag_sources = _collect_context_sources(context, workspace_context)
            rag_highlights = _collect_context_highlights(context, workspace_context)

            if merged_context:
                logger.info(f"【Chat】用户 {request.username} 使用 RAG 模式")
                ai_result = model_svc.chat_with_rag(
                    question=request.message,
                    context=merged_context,
                    conversation_history=history[:-1] if len(history) > 1 else None
                )
                if ai_result.get("success"):
                    ai_result["sources"] = rag_sources or ai_result.get("sources", [])
                    ai_result["highlights"] = rag_highlights
            elif getattr(model_svc, "available", False):
                logger.info(f"【Chat】用户 {request.username} 使用纯对话模式")
                ai_result = model_svc.chat(history_for_model)
            else:
                raise HTTPException(status_code=503, detail="AI 服务未配置，请联系管理员")
        
        if not ai_result.get("success"):
            raise HTTPException(status_code=500, detail=ai_result.get("message", "AI服务错误"))
        
        # 8. 保存 AI 回复
        ai_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_result["content"],
            message_meta=_build_message_meta({
                "usage": ai_result.get("usage", {}),
                "sources": ai_result.get("sources", []),
                "highlights": ai_result.get("highlights", []),
                "tool_calls": ai_result.get("tool_calls", []),
                "tool_trace": ai_result.get("tool_trace", []) or runtime_tool_trace,
            }, workspace_id=request.workspace_id),
        )
        db.add(ai_msg)
        db.commit()
        
        return ChatResponse(
            success=True,
            message=ai_result["content"],
            conversation_id=conversation.id,
            sources=ai_result.get("sources", []),
            highlights=ai_result.get("highlights", []),
            tool_calls=ai_result.get("tool_calls", []),
            tool_trace=ai_result.get("tool_trace", []) or runtime_tool_trace,
            usage=ai_result.get("usage", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"聊天失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"聊天失败: {str(e)}")


@router.get("/conversations/{username}", response_model=List[ConversationResponse])
async def get_conversations(
    username: str,
    workspace_id: Optional[int] = None,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    """获取用户的所有对话"""
    try:
        enforce_username_isolation(http_request, username)
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return []
        
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user.id
        ).order_by(Conversation.updated_at.desc()).all()

        if workspace_id:
            filtered = []
            for item in conversations:
                meta = item.conversation_meta or {}
                if int(meta.get("workspace_id") or 0) == int(workspace_id):
                    filtered.append(item)
            conversations = filtered
        
        return [
            ConversationResponse(
                id=c.id,
                title=c.title,
                created_at=c.created_at.isoformat(),
                workspace_id=int((c.conversation_meta or {}).get("workspace_id") or 0) or None,
            )
            for c in conversations
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取对话列表失败")


@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: int, username: str = None, http_request: Request = None, db: Session = Depends(get_db)):
    """获取对话历史（按学号严格隔离）"""
    try:
        if not username:
            raise HTTPException(status_code=400, detail="缺少用户名参数")
        enforce_username_isolation(http_request, username)

        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")

        messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at.asc()).all()
        
        return {
            "success": True,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                    "meta": m.message_meta
                }
                for m in messages
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取历史失败")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, username: str = None, http_request: Request = None, db: Session = Depends(get_db)):
    """删除对话及其所有消息"""
    try:
        # 1. 查找用户
        if not username:
            raise HTTPException(status_code=400, detail="缺少用户名参数")
        enforce_username_isolation(http_request, username)
        
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 2. 查找对话（确保是该用户的对话）
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        # 3. 显式删除该对话的所有消息（级联删除会自动处理，但这里显式处理更安全）
        db.query(Message).filter(Message.conversation_id == conversation_id).delete()
        
        # 4. 删除对话
        db.delete(conversation)
        db.commit()
        
        logger.info(f"用户 {username} 删除对话 {conversation_id} 及其 {len(conversation.messages)} 条消息")
        
        return {"success": True, "message": "对话及所有消息已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除对话失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除对话失败")


@router.post("/send-stream")
async def send_message_stream(request: ChatRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    流式发送消息给 AI（SSE）
    支持工具调用 + RAG + 纯流式对话
    """
    conversation = None
    trace_id = getattr(getattr(http_request, "state", None), "trace_id", "")
    try:
        CHAT_STREAM_REQUESTS_TOTAL.inc()
        stream_t0 = time.perf_counter()
        enforce_username_isolation(http_request, request.username)
        session_store = getattr(http_request.app.state, 'session_store', None)
        model_svc = get_model_provider_for_user(request.username, session_store)
        if (request.override_provider or "").strip():
            model_svc = UnifiedModelProvider(
                provider_name=(request.override_provider or "").strip().lower(),
                model=(request.override_model or "").strip() or None,
                api_base=(request.override_api_base or "").strip() or None,
                api_key=(request.override_api_key or "").strip() or None,
            )
        
        if not getattr(model_svc, "available", False):
            async def error_stream():
                yield f"data: {json.dumps({'content': '[AI服务未配置]', 'done': True})}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        
        # 1. 查找或创建用户
        user = db.query(User).filter(User.username == request.username).first()
        if not user:
            user = User(username=request.username, name=request.username)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # 2. 查找或创建对话
        if request.conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user.id
            ).first()
            if not conversation:
                raise HTTPException(status_code=404, detail="对话不存在")
        else:
            title = request.message[:20] + "..." if len(request.message) > 20 else request.message
            conversation = Conversation(user_id=user.id, title=title)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        _apply_workspace_context_to_conversation(conversation, request.workspace_id)
        db.add(conversation)
        db.commit()
        
        # 3. 保存用户消息
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            message_meta=_build_message_meta(workspace_id=request.workspace_id),
        )
        db.add(user_msg)
        db.commit()
        
        # 4. 获取历史对话
        history_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at.desc()).limit(10).all()
        
        history = []
        for msg in reversed(history_messages):
            history.append({"role": msg.role, "content": msg.content})
        
        # 5. 获取工具上下文
        user_session_data = session_store.get_user_session(request.username) if session_store else None
        
        tools_context = None
        if user_session_data:
            tools_context = {
                "session": user_session_data["session"],
                "server_url": user_session_data["server_url"],
                "username": request.username
            }
        skill_context = build_skill_prompt_hint(request.username, request.message)
        skill_matches = explain_skill_matches(request.username, request.message)
        runtime_hint, runtime_tool_trace = await _prepare_runtime_hint(
            request.username,
            request.message,
            session_store,
            request.workspace_id,
        )
        history_for_model = history
        system_blocks = [block for block in [skill_context, runtime_hint] if block.strip()]
        if system_blocks:
            history_for_model = [{"role": "system", "content": "\n\n".join(system_blocks)}] + history
        
        # 6. 构建教务数据上下文（从数据库缓存，按学期组织）
        edu_context = ""
        try:
            edu_data = db.query(EducationData).filter(EducationData.user_id == user.id).first()
            if edu_data:
                normalized = build_payload_from_education_data_record(edu_data)
                grounded_answer = _build_grounded_answer(request.message, normalized)
                if grounded_answer:
                    async def grounded_stream():
                        yield f"data: {json.dumps({'conversation_id': conversation.id, 'done': False})}\n\n"
                        if trace_id:
                            yield f"data: {json.dumps({'trace_id': trace_id, 'done': False})}\n\n"
                        yield f"data: {json.dumps({'content': grounded_answer, 'done': False})}\n\n"
                        ai_msg = Message(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=grounded_answer,
                            message_meta=_build_message_meta({"sources": ["grounded_structured_data"], "tool_trace": runtime_tool_trace}, workspace_id=request.workspace_id),
                        )
                        db.add(ai_msg)
                        db.commit()
                        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'tool_trace': runtime_tool_trace, 'skill_matches': skill_matches})}\n\n"

                    return StreamingResponse(
                        grounded_stream(),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache, no-transform",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no",
                            "Content-Encoding": "identity",
                        }
                    )
                context_parts = []
                if normalized["个人信息"]:
                    context_parts.append(f"个人信息：{json.dumps(normalized['个人信息'], ensure_ascii=False)}")

                grades_by_sem = normalized["成绩信息"]["按学期"]
                if grades_by_sem:
                    grades_context = {
                        sem: [f"{c.get('课程名称','')}({c.get('成绩','')}/{c.get('学分','')}学分)" for c in courses[:10]]
                        for sem, courses in grades_by_sem.items()
                    }
                    context_parts.append(f"成绩数据（按学期）：{json.dumps(grades_context, ensure_ascii=False)}")
                if normalized["成绩信息"]["统计信息"]:
                    context_parts.append(f"成绩统计：{json.dumps(normalized['成绩信息']['统计信息'], ensure_ascii=False)}")

                schedule_sem = normalized["课表信息"]["学期"] or "当前学期"
                schedule_courses = normalized["课表信息"]["课程列表"]
                if schedule_courses:
                    context_parts.append(f"课表数据 [{schedule_sem}]：{json.dumps(schedule_courses, ensure_ascii=False)}")

                if normalized["学业进度"]:
                    context_parts.append(f"学业进度：{json.dumps(normalized['学业进度'], ensure_ascii=False)}")

                exam_sem = normalized["考试安排"]["学期"] or "当前学期"
                exam_list = normalized["考试安排"]["考试列表"]
                if exam_list:
                    context_parts.append(f"考试安排 [{exam_sem}]：{json.dumps(exam_list, ensure_ascii=False)}")
                if context_parts:
                    edu_context = "\n".join(context_parts)
        except Exception as e:
            logger.warning(f"加载教务数据缓存失败: {e}")

        if skill_context:
            edu_context = f"{edu_context}\n\n{skill_context}" if edu_context else skill_context

        workspace_context = _build_workspace_context(db, request.username, request.message, session_store=session_store, workspace_id=request.workspace_id)
        workspace_sources = _collect_context_sources(workspace_context)
        workspace_highlights = _collect_context_highlights(workspace_context)
        if workspace_context:
            workspace_text = _render_workspace_rag_context(workspace_context)
            edu_context = f"{edu_context}\n\n{workspace_text}" if edu_context else workspace_text
        
        # 7. 流式生成AI回复（先回包，再在流内执行工具调用/模型调用）
        async def generate():
            full_content = ""
            done_sent = False
            stream_outcome = "success"
            loop = asyncio.get_running_loop()
            chunk_queue: asyncio.Queue = asyncio.Queue()
            tool_calls_info = []
            tool_trace_info = runtime_tool_trace[:]
            skill_matches_info = skill_matches[:]
            response_sources = workspace_sources[:]
            response_highlights = workspace_highlights[:]

            try:
                yield f"data: {json.dumps({'conversation_id': conversation.id, 'done': False})}\n\n"
                if trace_id:
                    yield f"data: {json.dumps({'trace_id': trace_id, 'done': False})}\n\n"

                if (request.execution_mode or "chat").strip().lower() == "agent":
                    runtime = get_agent_runtime()
                    agent_result = await runtime.run(
                        username=request.username,
                        message=request.message,
                        framework=(request.agent_framework or "openai_agents").strip().lower(),
                        session_store=session_store,
                        workspace_id=request.workspace_id,
                    )
                    tool_trace_info = agent_result.get("tool_trace", []) or []
                    tool_content = agent_result.get("content", "") or ""
                    if tool_content:
                        chunk_size = 16
                        for i in range(0, len(tool_content), chunk_size):
                            chunk = tool_content[i:i + chunk_size]
                            full_content += chunk
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                            await asyncio.sleep(0.01)

                    ai_msg = Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=full_content or "本轮 Agent 未返回有效内容。",
                        message_meta=_build_message_meta({
                            "tool_calls": tool_calls_info,
                            "tool_trace": tool_trace_info,
                            "skill_matches": skill_matches_info,
                            "framework": agent_result.get("framework", ""),
                            "sources": response_sources,
                            "highlights": response_highlights,
                        }, workspace_id=request.workspace_id),
                    )
                    db.add(ai_msg)
                    db.commit()

                    yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'tool_calls': tool_calls_info, 'tool_trace': tool_trace_info, 'skill_matches': skill_matches_info, 'sources': response_sources, 'highlights': response_highlights})}\n\n"
                    done_sent = True
                    return

                # 7.1 优先工具调用（在流内执行，并发送 keepalive 防止连接空闲断开）
                if tools_context:
                    try:
                        tool_task = asyncio.create_task(
                            asyncio.to_thread(model_svc.chat_with_tools, history_for_model, tools_context)
                        )
                        while not tool_task.done():
                            yield f"data: {json.dumps({'ping': True, 'stage': 'tool_call', 'done': False})}\n\n"
                            await asyncio.sleep(2)

                        tool_result = await tool_task
                        if tool_result and tool_result.get("success"):
                            tool_content = tool_result.get("content", "")
                            tool_calls_info = tool_result.get("tool_calls", [])

                            if tool_content:
                                chunk_size = 8
                                for i in range(0, len(tool_content), chunk_size):
                                    chunk = tool_content[i:i + chunk_size]
                                    full_content += chunk
                                    yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                                    await asyncio.sleep(0.01)

                                ai_msg = Message(
                                    conversation_id=conversation.id,
                                    role="assistant",
                                    content=full_content,
                                    message_meta=_build_message_meta(
                                        {"tool_calls": tool_calls_info, "tool_trace": tool_trace_info, "skill_matches": skill_matches_info, "sources": response_sources, "highlights": response_highlights},
                                        workspace_id=request.workspace_id,
                                    )
                                )
                                db.add(ai_msg)
                                db.commit()

                                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'tool_calls': tool_calls_info, 'tool_trace': tool_trace_info, 'skill_matches': skill_matches_info, 'sources': response_sources, 'highlights': response_highlights})}\n\n"
                                done_sent = True
                                return
                    except Exception as e:
                        logger.warning(f"工具调用失败，降级为流式: {e}")

                # 7.2 工具调用不可用/失败时：走 chat_stream
                def sync_producer():
                    try:
                        for event in model_svc.chat_stream_events(
                            history_for_model,
                            education_context=edu_context,
                            reasoning_mode=(request.reasoning_mode or "standard"),
                            show_thinking=bool(request.show_thinking),
                        ):
                            loop.call_soon_threadsafe(chunk_queue.put_nowait, event)
                    except Exception as e:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, {"type": "content", "content": f"[错误: {str(e)}]"})
                    finally:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

                producer_thread = threading.Thread(target=sync_producer, daemon=True)
                producer_thread.start()

                while True:
                    try:
                        event = await asyncio.wait_for(chunk_queue.get(), timeout=10)
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'ping': True, 'stage': 'model_stream', 'done': False})}\n\n"
                        continue

                    if event is None:
                        break
                    if isinstance(event, dict):
                        etype = event.get("type", "content")
                        econtent = event.get("content", "") or ""
                    else:
                        etype = "content"
                        econtent = str(event or "")
                    if not econtent:
                        continue
                    if etype == "thinking":
                        yield f"data: {json.dumps({'thinking': econtent, 'done': False})}\n\n"
                    else:
                        full_content += econtent
                        yield f"data: {json.dumps({'content': econtent, 'done': False})}\n\n"

                if not full_content.strip():
                    full_content = "本次未获取到有效回复，请重试。"
                    yield f"data: {json.dumps({'content': full_content, 'done': False})}\n\n"

                ai_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_content,
                    message_meta=_build_message_meta(
                        {"tool_calls": tool_calls_info, "tool_trace": tool_trace_info, "skill_matches": skill_matches_info, "sources": response_sources, "highlights": response_highlights},
                        workspace_id=request.workspace_id,
                    ) if (tool_calls_info or tool_trace_info or skill_matches_info or response_sources or response_highlights or request.workspace_id) else None
                )
                db.add(ai_msg)
                db.commit()

                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'tool_trace': tool_trace_info, 'skill_matches': skill_matches_info, 'sources': response_sources, 'highlights': response_highlights})}\n\n"
                done_sent = True
            except asyncio.CancelledError:
                logger.warning(f"流式连接被客户端中断: conversation_id={conversation.id}")
                CHAT_STREAM_ABORTED_TOTAL.inc()
                stream_outcome = "aborted"
                raise
            except Exception as e:
                logger.exception(f"流式生成异常: {e}")
                error_text = f"抱歉，本次请求处理失败：{str(e)}"
                try:
                    db.rollback()
                    ai_msg = Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=full_content or error_text,
                        message_meta=_build_message_meta(workspace_id=request.workspace_id),
                    )
                    db.add(ai_msg)
                    db.commit()
                except Exception as save_err:
                    db.rollback()
                    logger.error(f"流式异常后保存消息失败: {save_err}")

                yield f"data: {json.dumps({'content': error_text, 'done': False})}\n\n"
                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"
                done_sent = True
                stream_outcome = "failed"
            finally:
                if not done_sent:
                    # 确保前端能收到结束帧，避免一直转圈
                    yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"
                CHAT_STREAM_DURATION.labels(outcome=stream_outcome).observe(max(0.001, time.perf_counter() - stream_t0))
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Encoding": "identity",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"流式聊天失败: {str(e)}")
        error_text = f"抱歉，本次请求处理失败：{str(e)}"
        try:
            if conversation is not None:
                ai_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=error_text,
                    message_meta=_build_message_meta(workspace_id=request.workspace_id),
                )
                db.add(ai_msg)
                db.commit()
        except Exception as save_err:
            db.rollback()
            logger.error(f"流式失败后写入错误消息失败: {save_err}")

        async def error_stream():
            yield f"data: {json.dumps({'content': error_text, 'done': False})}\n\n"
            if conversation is not None:
                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"
            else:
                yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Encoding": "identity",
            },
        )
