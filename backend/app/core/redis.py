import redis.asyncio as redis
from typing import Optional
from .config import settings


class RedisClient:
    """Redis 客户端封装"""
    
    _instance: Optional['RedisClient'] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self):
        """连接 Redis"""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
    
    async def disconnect(self):
        """断开 Redis 连接"""
        if self._client:
            await self._client.close()
            self._client = None
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    # 会话管理
    async def set_session(self, user_id: str, session_data: dict, expire: int = 86400):
        """存储用户会话"""
        import json
        await self.client.setex(
            f"session:{user_id}",
            expire,
            json.dumps(session_data, ensure_ascii=False),
        )
    
    async def get_session(self, user_id: str) -> Optional[dict]:
        """获取用户会话"""
        import json
        data = await self.client.get(f"session:{user_id}")
        if data:
            return json.loads(data)
        return None
    
    async def delete_session(self, user_id: str):
        """删除用户会话"""
        await self.client.delete(f"session:{user_id}")
    
    # 对话历史缓存
    async def add_message(self, session_id: str, role: str, content: str, max_history: int = 20):
        """添加对话消息到历史"""
        import json
        import time
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        await self.client.lpush(
            f"chat:{session_id}",
            json.dumps(message, ensure_ascii=False),
        )
        # 保留最近 N 条消息
        await self.client.ltrim(f"chat:{session_id}", 0, max_history - 1)
    
    async def get_messages(self, session_id: str, limit: int = 10) -> list:
        """获取对话历史"""
        import json
        messages = await self.client.lrange(f"chat:{session_id}", 0, limit - 1)
        return [json.loads(msg) for msg in messages]
    
    # 验证码缓存
    async def set_captcha(self, session_id: str, captcha_image: str, expire: int = 300):
        """缓存验证码图片（base64）"""
        await self.client.setex(f"captcha:{session_id}", expire, captcha_image)
    
    async def get_captcha(self, session_id: str) -> Optional[str]:
        """获取验证码图片"""
        return await self.client.get(f"captcha:{session_id}")


# 全局实例
redis_client = RedisClient()
