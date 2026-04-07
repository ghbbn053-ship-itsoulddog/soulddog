from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.services.auth import get_current_user
from app.services.rag import RAGService

router = APIRouter(prefix="/chat", tags=["对话"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    conversation_id: int
    message: str
    sources: list[dict]


class ConversationResponse(BaseModel):
    id: int
    title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[list[dict]]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == data.conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    else:
        conversation = Conversation(
            user_id=current_user.id,
            title=data.message[:50] + "..." if len(data.message) > 50 else data.message,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
    
    user_message = Message(conversation_id=conversation.id, role="user", content=data.message)
    db.add(user_message)
    await db.commit()
    
    rag_service = RAGService()
    response = await rag_service.chat(user_id=current_user.id, query=data.message)
    
    ai_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response["answer"],
        sources=response.get("sources", []),
    )
    db.add(ai_message)
    await db.commit()
    
    return ChatResponse(
        conversation_id=conversation.id,
        message=response["answer"],
        sources=response.get("sources", []),
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def get_conversations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(conversation_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    
    await db.delete(conversation)
    await db.commit()
    return {"message": "对话已删除"}
