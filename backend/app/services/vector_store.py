"""
向量数据库服务 - Milvus 集成
"""

try:
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
    MILVUS_IMPORT_OK = True
except Exception:  # pragma: no cover - optional dependency
    connections = Collection = FieldSchema = CollectionSchema = DataType = utility = None  # type: ignore
    MILVUS_IMPORT_OK = False
import os
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import math

logger = logging.getLogger(__name__)


def _normalize_metadata_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


class VectorStore:
    """Milvus 向量存储服务"""
    
    def __init__(self):
        self.host = os.getenv("MILVUS_HOST", "localhost")
        self.port = os.getenv("MILVUS_PORT", "19530")
        self.collection_name = os.getenv("MILVUS_COLLECTION", "campus_knowledge")
        self.collection = None
        self.available = False
        self._connect()
    
    def _connect(self):
        """连接 Milvus"""
        if not MILVUS_IMPORT_OK:
            self.available = False
            logger.warning("⚠️ pymilvus 未安装，Milvus 后端不可用")
            return
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            self.available = True
            logger.info(f"✅ Milvus 连接成功: {self.host}:{self.port}")
        except Exception as e:
            self.available = False
            logger.warning(f"⚠️ Milvus 连接失败（服务不可用）: {str(e)}")
    
    def create_collection(self, dim: int = 1536):
        """创建集合（如果不存在）"""
        if not self.available:
            logger.warning("⚠️ Milvus 不可用，跳过创建集合")
            return
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
        """添加文档到向量库（自动去重）"""
        if not self.available:
            logger.warning("⚠️ Milvus 不可用，跳过添加文档")
            return []
        try:
            if not self.collection:
                self.create_collection(dim=len(embeddings[0]))
            if not self.collection:
                logger.warning("⚠️ Collection 初始化失败，跳过添加文档")
                return []
            
            # 确保 Collection 已加载
            self.collection.load()
            
            # 查询已存在的文本（去重）
            existing_texts = set()
            try:
                # 获取该用户的所有文本
                existing_results = self.collection.query(
                    expr=f"user_id == {user_id}",
                    output_fields=["text", "metadata"]
                )
                existing_texts = {
                    (
                        item.get("text"),
                        str(_normalize_metadata_payload(item.get("metadata")).get("sync_key", "")),
                    )
                    for item in existing_results
                }
                logger.info(f"📊 用户 {user_id} 已有 {len(existing_texts)} 条数据")
            except Exception as e:
                logger.warning(f"⚠️ 查询已有数据失败: {str(e)}")
            
            # 过滤掉已存在的文本
            new_texts = []
            new_embeddings = []
            new_sources = []
            new_metadatas = []
            
            for i, text in enumerate(texts):
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                sync_key = str((metadata or {}).get("sync_key", ""))
                if (text, sync_key) not in existing_texts:
                    new_texts.append(text)
                    new_embeddings.append(embeddings[i])
                    new_sources.append(sources[i])
                    new_metadatas.append(metadata)
            
            if not new_texts:
                logger.info(f"ℹ️ 用户 {user_id} 没有新数据需要添加")
                return []
            
            logger.info(f"📝 准备插入 {len(new_texts)} 条新数据（过滤掉 {len(texts) - len(new_texts)} 条重复）")
            
            # 准备数据
            entities = [
                [user_id] * len(new_texts),  # user_id
                new_texts,  # text
                new_embeddings,  # embedding
                new_sources,  # source
                [json.dumps(m) if m else "" for m in new_metadatas]  # metadata
            ]
            
            # 插入数据
            insert_result = self.collection.insert(entities)
            self.collection.flush()
            
            logger.info(f"✅ 插入 {len(new_texts)} 条新文档，ID: {insert_result.primary_keys}")
            return insert_result.primary_keys
            
        except Exception as e:
            logger.error(f"❌ 插入文档失败: {str(e)}")
            raise
    
    def search(
        self,
        user_id: int,
        query_embedding: List[float],
        top_k: int = 5,
        data_types: Optional[List[str]] = None,
        semester: str = "",
        sync_key: str = "",
    ) -> List[Dict]:
        """搜索相似文档"""
        if not self.available:
            logger.warning("⚠️ Milvus 不可用，跳过搜索")
            return []
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
                    metadata = json.loads(hit.entity.get("metadata") or "{}")
                    if data_types:
                        hit_type = metadata.get("data_type") or metadata.get("type")
                        if hit_type not in data_types:
                            continue
                    if semester:
                        hit_sem = str(metadata.get("semester", "")).strip()
                        if hit_sem and hit_sem != semester:
                            continue
                    if sync_key:
                        hit_sync_key = str(metadata.get("sync_key", "")).strip()
                        if hit_sync_key != sync_key:
                            continue
                    hits.append({
                        "id": hit.id,
                        "text": hit.entity.get("text"),
                        "source": hit.entity.get("source"),
                        "metadata": metadata,
                        "score": hit.score
                    })
            
            logger.info(f"✅ 搜索完成，找到 {len(hits)} 条相关文档")
            return hits
            
        except Exception as e:
            logger.error(f"❌ 搜索失败: {str(e)}")
            return []
    
    def delete_user_data(self, user_id: int, exclude_sync_key: Optional[str] = None):
        """删除用户的所有数据"""
        if not self.available:
            logger.warning("⚠️ Milvus 不可用，跳过删除")
            return
        try:
            # 检查 Collection 是否存在
            if not utility.has_collection(self.collection_name):
                logger.info(f"ℹ️ Collection '{self.collection_name}' 不存在，跳过删除用户 {user_id} 数据")
                return
            
            # 确保 Collection 已加载
            if not self.collection:
                self.collection = Collection(self.collection_name)
            
            # 加载 Collection 到内存
            self.collection.load()

            if not exclude_sync_key:
                self.collection.delete(expr=f"user_id == {user_id}")
                self.collection.flush()
                logger.info(f"✅ 删除用户 {user_id} 的所有向量数据")
                return

            rows = self.collection.query(
                expr=f"user_id == {user_id}",
                output_fields=["id", "metadata"],
            )
            removable_ids = []
            for row in rows:
                metadata = _normalize_metadata_payload(row.get("metadata"))
                row_sync_key = str(metadata.get("sync_key", "")).strip()
                if row_sync_key != exclude_sync_key:
                    removable_ids.append(str(row.get("id")))

            if removable_ids:
                self.collection.delete(expr=f"id in [{','.join(removable_ids)}]")
                self.collection.flush()
            logger.info(f"✅ 删除用户 {user_id} 的旧向量数据: {len(removable_ids)} 条")
            
        except Exception as e:
            logger.error(f"❌ 删除数据失败: {str(e)}")
            # 不抛出异常，避免阻塞后续流程
            return
    
    def close(self):
        """关闭连接"""
        if MILVUS_IMPORT_OK:
            connections.disconnect("default")
            logger.info("✅ Milvus 连接已关闭")


class TxtaiVectorStore:
    """
    轻量向量存储后端（txtai 风格，文件持久化）。
    说明：
    - 使用现有外部 embedding（保持与当前模型层兼容）
    - 无需 Milvus，适合本地开发/低资源部署
    """

    def __init__(self):
        self.data_path = Path(os.getenv("TXTAI_DATA_PATH", "backend/data/txtai_vectors.json"))
        self.available = True
        self._rows: List[Dict[str, Any]] = []
        self._next_id = 1
        self._load()

    def _load(self):
        try:
            if self.data_path.exists():
                payload = json.loads(self.data_path.read_text(encoding="utf-8"))
                self._rows = payload.get("rows", []) or []
                self._next_id = int(payload.get("next_id", len(self._rows) + 1))
        except Exception as e:
            logger.warning(f"⚠️ TxtaiStore 加载失败，使用空存储: {e}")
            self._rows = []
            self._next_id = 1

    def _save(self):
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"next_id": self._next_id, "rows": self._rows}
            self.data_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"⚠️ TxtaiStore 持久化失败: {e}")

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return -1.0
        dot = 0.0
        na = 0.0
        nb = 0.0
        for x, y in zip(a, b):
            dot += x * y
            na += x * x
            nb += y * y
        if na <= 0 or nb <= 0:
            return -1.0
        return dot / (math.sqrt(na) * math.sqrt(nb))

    def create_collection(self, dim: int = 1536):
        # 兼容接口，无需显式建库
        return

    def add_documents(
        self,
        user_id: int,
        texts: List[str],
        embeddings: List[List[float]],
        sources: List[str],
        metadatas: Optional[List[Dict]] = None,
    ) -> List[int]:
        ids: List[int] = []
        existing = {(r.get("user_id"), r.get("text")) for r in self._rows}
        for i, text in enumerate(texts):
            if (user_id, text) in existing:
                continue
            rid = self._next_id
            self._next_id += 1
            row = {
                "id": rid,
                "user_id": user_id,
                "text": text,
                "embedding": embeddings[i],
                "source": sources[i] if i < len(sources) else "",
                "metadata": metadatas[i] if metadatas and i < len(metadatas) else {},
            }
            self._rows.append(row)
            ids.append(rid)
        self._save()
        logger.info(f"✅ TxtaiStore 插入 {len(ids)} 条文档")
        return ids

    def search(
        self,
        user_id: int,
        query_embedding: List[float],
        top_k: int = 5,
        data_types: Optional[List[str]] = None,
        semester: str = "",
        sync_key: str = "",
    ) -> List[Dict]:
        candidates: List[Dict[str, Any]] = []
        for r in self._rows:
            if int(r.get("user_id", -1)) != int(user_id):
                continue
            meta = r.get("metadata") or {}
            if data_types:
                hit_type = meta.get("data_type") or meta.get("type")
                if hit_type not in data_types:
                    continue
            if semester:
                hit_sem = str(meta.get("semester", "")).strip()
                if hit_sem and hit_sem != semester:
                    continue
            if sync_key:
                hit_sync_key = str(meta.get("sync_key", "")).strip()
                if hit_sync_key != sync_key:
                    continue
            score = self._cosine(query_embedding, r.get("embedding") or [])
            if score < 0:
                continue
            candidates.append(
                {
                    "id": r.get("id"),
                    "text": r.get("text"),
                    "source": r.get("source"),
                    "metadata": meta,
                    "score": float(score),
                }
            )
        candidates.sort(key=lambda x: x["score"], reverse=True)
        hits = candidates[: max(1, top_k)]
        logger.info(f"✅ TxtaiStore 搜索完成，找到 {len(hits)} 条相关文档")
        return hits

    def delete_user_data(self, user_id: int, exclude_sync_key: Optional[str] = None):
        before = len(self._rows)
        self._rows = [
            r for r in self._rows
            if not (
                int(r.get("user_id", -1)) == int(user_id)
                and (
                    exclude_sync_key is None
                    or str((r.get("metadata") or {}).get("sync_key", "")).strip() != exclude_sync_key
                )
            )
        ]
        removed = before - len(self._rows)
        self._save()
        logger.info(f"✅ TxtaiStore 删除用户 {user_id} 向量数据: {removed} 条")

    def close(self):
        self._save()


# 全局实例（懒加载）
_vector_store = None

def get_vector_store() -> VectorStore:
    """获取向量库实例（懒加载）"""
    global _vector_store
    if _vector_store is None:
        backend = (os.getenv("VECTOR_BACKEND", "milvus") or "milvus").strip().lower()
        if backend == "txtai":
            _vector_store = TxtaiVectorStore()
            logger.info("✅ 向量后端已切换: txtai(轻量本地)")
        else:
            _vector_store = VectorStore()
    return _vector_store
