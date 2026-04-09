"""
向量数据库服务 - Milvus 集成
"""

from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class VectorStore:
    """Milvus 向量存储服务"""
    
    def __init__(self):
        self.host = os.getenv("MILVUS_HOST", "localhost")
        self.port = os.getenv("MILVUS_PORT", "19530")
        self.collection_name = os.getenv("MILVUS_COLLECTION", "campus_knowledge")
        self.collection = None
        self._connect()
    
    def _connect(self):
        """连接 Milvus"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            logger.info(f"✅ Milvus 连接成功: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ Milvus 连接失败: {str(e)}")
            raise
    
    def create_collection(self, dim: int = 1024):
        """创建集合（如果不存在）"""
        try:
            if utility.has_collection(self.collection_name):
                logger.info(f"集合 {self.collection_name} 已存在")
                self.collection = Collection(self.collection_name)
                return
            
            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="user_id", dtype=DataType.INT64, description="用户ID"),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096, description="文本内容"),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim, description="向量"),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=100, description="数据来源"),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=2048, description="元数据JSON"),
            ]
            
            # 创建集合
            schema = CollectionSchema(fields, description="校园AI知识库")
            self.collection = Collection(self.collection_name, schema)
            
            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            self.collection.create_index(field_name="embedding", index_params=index_params)
            
            logger.info(f"✅ 集合 {self.collection_name} 创建成功")
            
        except Exception as e:
            logger.error(f"❌ 创建集合失败: {str(e)}")
            raise
    
    def add_documents(self, user_id: int, texts: List[str], embeddings: List[List[float]], 
                      sources: List[str], metadatas: Optional[List[Dict]] = None) -> List[int]:
        """添加文档到向量库"""
        try:
            if not self.collection:
                self.create_collection(dim=len(embeddings[0]))
            
            # 准备数据
            entities = [
                [user_id] * len(texts),  # user_id
                texts,  # text
                embeddings,  # embedding
                sources,  # source
                [json.dumps(m) if m else "" for m in (metadatas or [{}] * len(texts))]  # metadata
            ]
            
            # 插入数据
            insert_result = self.collection.insert(entities)
            self.collection.flush()
            
            logger.info(f"✅ 插入 {len(texts)} 条文档，ID: {insert_result.primary_keys}")
            return insert_result.primary_keys
            
        except Exception as e:
            logger.error(f"❌ 插入文档失败: {str(e)}")
            raise
    
    def search(self, user_id: int, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """搜索相似文档"""
        try:
            if not self.collection:
                self.collection = Collection(self.collection_name)
            
            self.collection.load()
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 执行搜索
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=f"user_id == {user_id}",
                output_fields=["text", "source", "metadata"]
            )
            
            # 格式化结果
            hits = []
            for result in results:
                for hit in result:
                    hits.append({
                        "id": hit.id,
                        "text": hit.entity.get("text"),
                        "source": hit.entity.get("source"),
                        "metadata": json.loads(hit.entity.get("metadata") or "{}"),
                        "score": hit.score
                    })
            
            logger.info(f"✅ 搜索完成，找到 {len(hits)} 条相关文档")
            return hits
            
        except Exception as e:
            logger.error(f"❌ 搜索失败: {str(e)}")
            return []
    
    def delete_user_data(self, user_id: int):
        """删除用户的所有数据"""
        try:
            if not self.collection:
                self.collection = Collection(self.collection_name)
            
            self.collection.delete(expr=f"user_id == {user_id}")
            logger.info(f"✅ 删除用户 {user_id} 的所有向量数据")
            
        except Exception as e:
            logger.error(f"❌ 删除数据失败: {str(e)}")
            raise
    
    def close(self):
        """关闭连接"""
        connections.disconnect("default")
        logger.info("✅ Milvus 连接已关闭")


# 全局实例
vector_store = VectorStore()
