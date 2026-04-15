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

from app.models import get_db, User, Conversation, Message, EducationData
from app.services import get_qwen_service, get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["对话"])


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
        qwen_svc = get_qwen_service()
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
        
        # 5. 构建工具上下文（从 app.state.sessions 获取用户 session）
        sessions = getattr(http_request.app.state, 'sessions', {})
        user_session_data = sessions.get(request.username)
        
        tools_context = None
        if user_session_data:
            tools_context = {
                "session": user_session_data["session"],
                "server_url": user_session_data["server_url"],
                "username": request.username
            }
        
        ai_result = None
        
        # 6. 优先使用工具调用（Function Calling）
        if qwen_svc.available and tools_context:
            logger.info(f"【Chat】用户 {request.username} 使用工具调用模式")
            ai_result = qwen_svc.chat_with_tools(
                messages=history,
                tools_context=tools_context
            )
        
        # 7. 工具调用不可用或失败时，尝试 RAG 兜底
        if not ai_result or not ai_result.get("success"):
            edu_data = db.query(EducationData).filter(EducationData.user_id == user.id).first()
            context = []
            if edu_data and vec_store.available and qwen_svc.available:
                try:
                    query_embedding = qwen_svc.generate_embedding(request.message)
                    if query_embedding:
                        context = vec_store.search(user.id, query_embedding, top_k=5)
                except Exception as e:
                    logger.warning(f"向量检索失败: {e}")
            
            if context:
                logger.info(f"【Chat】用户 {request.username} 使用 RAG 模式")
                ai_result = qwen_svc.chat_with_rag(
                    question=request.message,
                    context=context,
                    conversation_history=history[:-1] if len(history) > 1 else None
                )
            elif qwen_svc.available:
                logger.info(f"【Chat】用户 {request.username} 使用纯对话模式")
                ai_result = qwen_svc.chat(history)
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
async def get_conversations(username: str, db: Session = Depends(get_db)):
    """获取用户的所有对话"""
    try:
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
    except Exception as e:
        logger.error(f"获取对话列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取对话列表失败")


@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: int, db: Session = Depends(get_db)):
    """获取对话历史"""
    try:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
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
    except Exception as e:
        logger.error(f"获取历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取历史失败")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, username: str = None, db: Session = Depends(get_db)):
    """删除对话及其所有消息"""
    try:
        # 1. 查找用户
        if not username:
            raise HTTPException(status_code=400, detail="缺少用户名参数")
        
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
    try:
        qwen_svc = get_qwen_service()
        
        if not qwen_svc.available:
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
        sessions = getattr(http_request.app.state, 'sessions', {})
        user_session_data = sessions.get(request.username)
        
        tools_context = None
        if user_session_data:
            tools_context = {
                "session": user_session_data["session"],
                "server_url": user_session_data["server_url"],
                "username": request.username
            }
        
        # 6. 尝试工具调用（非流式）获取教务数据
        tool_result = None
        if tools_context:
            try:
                tool_result = qwen_svc.chat_with_tools(messages=history, tools_context=tools_context)
                if tool_result and tool_result.get("success") and tool_result.get("tool_calls"):
                    # 工具调用成功，模拟流式输出结果
                    content = tool_result["content"]
                    tool_calls_info = tool_result.get("tool_calls", [])
                    
                    async def tool_stream():
                        yield f"data: {json.dumps({'conversation_id': conversation.id, 'done': False})}\n\n"
                        
                        # 分块发送内容（模拟流式）
                        chunk_size = 4
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i:i+chunk_size]
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                            await asyncio.sleep(0.02)
                        
                        # 保存AI回复
                        ai_msg = Message(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=content,
                            message_meta={"tool_calls": tool_calls_info}
                        )
                        db.add(ai_msg)
                        db.commit()
                        
                        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'tool_calls': tool_calls_info})}\n\n"
                    
                    return StreamingResponse(
                        tool_stream(),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
                    )
            except Exception as e:
                logger.warning(f"工具调用失败，降级为流式: {e}")
        
        # 7. 构建教务数据上下文（从数据库缓存）
        edu_context = ""
        try:
            edu_data = db.query(EducationData).filter(EducationData.user_id == user.id).first()
            if edu_data:
                context_parts = []
                if edu_data.personal_info:
                    context_parts.append(f"个人信息：{json.dumps(edu_data.personal_info, ensure_ascii=False)}")
                if edu_data.grades:
                    grades_data = edu_data.grades[:20] if isinstance(edu_data.grades, list) else edu_data.grades
                    context_parts.append(f"成绩数据：{json.dumps(grades_data, ensure_ascii=False)}")
                if edu_data.grade_stats:
                    context_parts.append(f"成绩统计：{json.dumps(edu_data.grade_stats, ensure_ascii=False)}")
                if edu_data.schedule:
                    context_parts.append(f"课表数据：{json.dumps(edu_data.schedule, ensure_ascii=False)}")
                if edu_data.academic_progress:
                    context_parts.append(f"学业进度：{json.dumps(edu_data.academic_progress, ensure_ascii=False)}")
                if edu_data.exam_schedule:
                    context_parts.append(f"考试安排：{json.dumps(edu_data.exam_schedule, ensure_ascii=False)}")
                if context_parts:
                    edu_context = "\n".join(context_parts)
        except Exception as e:
            logger.warning(f"加载教务数据缓存失败: {e}")
        
        # 8. 流式生成AI回复
        async def generate():
            full_content = ""
            
            yield f"data: {json.dumps({'conversation_id': conversation.id, 'done': False})}\n\n"
            
            # 流式调用AI（注入教务数据上下文）
            for chunk in qwen_svc.chat_stream(history, education_context=edu_context):
                full_content += chunk
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                await asyncio.sleep(0)  # 让出事件循环，确保即时刷新
            
            # 保存AI回复
            ai_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_content
            )
            db.add(ai_msg)
            db.commit()
            
            yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"
        
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
        raise HTTPException(status_code=500, detail=f"流式聊天失败: {str(e)}")
