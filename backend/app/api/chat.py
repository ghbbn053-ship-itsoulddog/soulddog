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

from app.models import get_db, User, Conversation, Message, EducationData
from app.services import get_model_provider_for_user, get_vector_store
from app.services.education_normalizer import build_payload_from_education_data_record
from app.services.skill_router import build_skill_prompt_hint
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


# ============ 数据模型 ============

class ChatRequest(BaseModel):
    """聊天请求"""
    username: str
    message: str
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    message: str
    conversation_id: int
    sources: List[str] = []
    tool_calls: List[dict] = []
    usage: dict = {}


class ConversationResponse(BaseModel):
    """对话列表响应"""
    id: int
    title: str
    created_at: str


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
        
        # 3. 保存用户消息
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message
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
        history_for_model = history
        if skill_context:
            history_for_model = [{"role": "system", "content": skill_context}] + history
        
        ai_result = None
        
        # 6. 优先使用工具调用（Function Calling）
        if getattr(model_svc, "available", False) and tools_context:
            logger.info(f"【Chat】用户 {request.username} 使用工具调用模式")
            ai_result = model_svc.chat_with_tools(
                messages=history_for_model,
                tools_context=tools_context
            )
        
        # 7. 工具调用不可用或失败时，尝试 RAG 兜底
        if not ai_result or not ai_result.get("success"):
            edu_data = db.query(EducationData).filter(EducationData.user_id == user.id).first()
            context = []
            if edu_data and vec_store.available and getattr(model_svc, "available", False):
                try:
                    query_embedding = model_svc.generate_embedding(request.message)
                    if query_embedding:
                        filters = _infer_rag_filters(request.message)
                        context = vec_store.search(
                            user.id,
                            query_embedding,
                            top_k=8,
                            data_types=filters["data_types"],
                            semester=filters["semester"],
                        )
                except Exception as e:
                    logger.warning(f"向量检索失败: {e}")
            
            if context:
                logger.info(f"【Chat】用户 {request.username} 使用 RAG 模式")
                ai_result = model_svc.chat_with_rag(
                    question=request.message,
                    context=context,
                    conversation_history=history[:-1] if len(history) > 1 else None
                )
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
            message_meta={
                "usage": ai_result.get("usage", {}),
                "sources": ai_result.get("sources", []),
                "tool_calls": ai_result.get("tool_calls", [])
            }
        )
        db.add(ai_msg)
        db.commit()
        
        return ChatResponse(
            success=True,
            message=ai_result["content"],
            conversation_id=conversation.id,
            sources=ai_result.get("sources", []),
            tool_calls=ai_result.get("tool_calls", []),
            usage=ai_result.get("usage", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"聊天失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"聊天失败: {str(e)}")


@router.get("/conversations/{username}", response_model=List[ConversationResponse])
async def get_conversations(username: str, http_request: Request, db: Session = Depends(get_db)):
    """获取用户的所有对话"""
    try:
        enforce_username_isolation(http_request, username)
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return []
        
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user.id
        ).order_by(Conversation.updated_at.desc()).all()
        
        return [
            ConversationResponse(
                id=c.id,
                title=c.title,
                created_at=c.created_at.isoformat()
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
        
        # 3. 保存用户消息
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message
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
        history_for_model = history
        if skill_context:
            history_for_model = [{"role": "system", "content": skill_context}] + history
        
        # 6. 构建教务数据上下文（从数据库缓存，按学期组织）
        edu_context = ""
        try:
            edu_data = db.query(EducationData).filter(EducationData.user_id == user.id).first()
            if edu_data:
                normalized = build_payload_from_education_data_record(edu_data)
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
        
        # 7. 流式生成AI回复（先回包，再在流内执行工具调用/模型调用）
        async def generate():
            full_content = ""
            done_sent = False
            stream_outcome = "success"
            loop = asyncio.get_running_loop()
            chunk_queue: asyncio.Queue = asyncio.Queue()
            tool_calls_info = []

            try:
                yield f"data: {json.dumps({'conversation_id': conversation.id, 'done': False})}\n\n"
                if trace_id:
                    yield f"data: {json.dumps({'trace_id': trace_id, 'done': False})}\n\n"

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
                                    message_meta={"tool_calls": tool_calls_info}
                                )
                                db.add(ai_msg)
                                db.commit()

                                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'tool_calls': tool_calls_info})}\n\n"
                                done_sent = True
                                return
                    except Exception as e:
                        logger.warning(f"工具调用失败，降级为流式: {e}")

                # 7.2 工具调用不可用/失败时：走 chat_stream
                def sync_producer():
                    try:
                        for chunk in model_svc.chat_stream(history_for_model, education_context=edu_context):
                            loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)
                    except Exception as e:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, f"[错误: {str(e)}]")
                    finally:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

                producer_thread = threading.Thread(target=sync_producer, daemon=True)
                producer_thread.start()

                while True:
                    try:
                        chunk = await asyncio.wait_for(chunk_queue.get(), timeout=10)
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'ping': True, 'stage': 'model_stream', 'done': False})}\n\n"
                        continue

                    if chunk is None:
                        break
                    full_content += chunk
                    yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                if not full_content.strip():
                    full_content = "本次未获取到有效回复，请重试。"
                    yield f"data: {json.dumps({'content': full_content, 'done': False})}\n\n"

                ai_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_content,
                    message_meta={"tool_calls": tool_calls_info} if tool_calls_info else None
                )
                db.add(ai_msg)
                db.commit()

                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"
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
                        content=full_content or error_text
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
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
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
                    content=error_text
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
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )
