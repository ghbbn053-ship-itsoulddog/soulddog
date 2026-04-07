from typing import Optional
from loguru import logger
from pymilvus import MilvusClient
import dashscope
from dashscope import Generation

from app.core.config import settings


class RAGService:
    """RAG 检索增强生成服务"""
    
    def __init__(self):
        self.milvus_client: Optional[MilvusClient] = None
        self.collection_name = settings.MILVUS_COLLECTION
        self.embedding_model = None
        # 设置千问 API Key
        dashscope.api_key = settings.QWEN_API_KEY
    
    async def _ensure_milvus(self):
        """确保 Milvus 连接"""
        if self.milvus_client is None:
            self.milvus_client = MilvusClient(
                uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
            )
            await self._ensure_collection()
    
    async def _ensure_collection(self):
        """确保集合存在"""
        if not self.milvus_client.has_collection(self.collection_name):
            self.milvus_client.create_collection(
                collection_name=self.collection_name,
                dimension=384,
                auto_id=True,
                metric_type="COSINE",
            )
            logger.info(f"创建 Milvus 集合: {self.collection_name}")
    
    def _get_embedding(self, text: str) -> list[float]:
        """获取文本向量"""
        if self.embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        
        embedding = self.embedding_model.encode(text)
        return embedding.tolist()
    
    async def add_document(
        self,
        user_id: int,
        doc_id: str,
        content: str,
        metadata: dict,
    ):
        """向知识库添加文档"""
        await self._ensure_milvus()
        
        embedding = self._get_embedding(content)
        
        self.milvus_client.insert(
            collection_name=self.collection_name,
            data=[{
                "id": doc_id,
                "vector": embedding,
                "content": content,
                "user_id": user_id,
                "data_type": metadata.get("data_type", ""),
                "semester": metadata.get("semester", ""),
                **metadata,
            }],
        )
        
        logger.info(f"添加文档到知识库: user_id={user_id}, doc_id={doc_id}")
    
    async def search(
        self,
        query: str,
        user_id: int,
        top_k: int = 5,
    ) -> list[dict]:
        """在知识库中搜索相关文档"""
        await self._ensure_milvus()
        
        query_embedding = self._get_embedding(query)
        
        results = self.milvus_client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            filter=f'user_id == {user_id}',
            limit=top_k,
            output_fields=["content", "data_type", "semester"],
        )
        
        return results[0] if results else []
    
    async def chat(
        self,
        user_id: int,
        query: str,
    ) -> dict:
        """使用 RAG 进行对话"""
        # 1. 检索相关知识
        relevant_docs = await self.search(query, user_id)
        
        # 2. 构建上下文
        context = ""
        sources = []
        for i, doc in enumerate(relevant_docs):
            content = doc.get('entity', {}).get('content', '')
            context += f"\n[文档{i+1}]\n{content}\n"
            sources.append({
                "content": content[:100] + "...",
                "data_type": doc.get("entity", {}).get("data_type", ""),
                "score": doc.get("distance", 0),
            })
        
        # 3. 构建提示词
        system_prompt = """你是一个校园 AI 助手，帮助学生解答关于教务系统的问题。
请根据以下知识库内容回答用户问题。如果知识库中没有相关信息，请根据你的常识回答。

知识库内容：
""" + context if context else "你是一个校园 AI 助手，帮助学生解答问题。"
        
        # 4. 调用千问 API
        try:
            response = Generation.call(
                model=settings.QWEN_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                result_format="message",
            )
            
            if response.status_code == 200:
                answer = response.output.choices[0].message.content
                logger.info(f"RAG 对话成功, user_id={user_id}")
                
                return {
                    "answer": answer,
                    "sources": sources,
                }
            else:
                logger.error(f"千问 API 错误: {response.message}")
                return {
                    "answer": "抱歉，AI 服务暂时不可用，请稍后再试。",
                    "sources": [],
                }
            
        except Exception as e:
            logger.error(f"调用千问 API 失败: {e}")
            return {
                "answer": "抱歉，我暂时无法回答这个问题，请稍后再试。",
                "sources": [],
            }
    
    async def delete_user_documents(self, user_id: int):
        """删除用户的所有文档"""
        await self._ensure_milvus()
        
        self.milvus_client.delete(
            collection_name=self.collection_name,
            filter=f'user_id == {user_id}',
        )
        
        logger.info(f"删除用户文档: user_id={user_id}")


# 全局实例
rag_service = RAGService()
