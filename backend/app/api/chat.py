"""
对话 API - AI 聊天接口（支持 Function Calling）
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

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
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """删除对话"""
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        db.delete(conversation)
        db.commit()
        
        return {"success": True, "message": "对话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除对话失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除对话失败")
