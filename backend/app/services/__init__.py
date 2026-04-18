"""
服务模块
"""

def _build_unavailable_chat_service():
    class _UnavailableQwenService:
        available = False

        def chat(self, *_args, **_kwargs):
            return {"success": False, "message": "AI服务未配置或依赖缺失"}

        def chat_stream(self, *_args, **_kwargs):
            yield "[AI服务未配置或依赖缺失]"

        def chat_with_tools(self, *_args, **_kwargs):
            return {"success": False, "message": "AI服务未配置或依赖缺失"}

        def generate_embedding(self, *_args, **_kwargs):
            return None

    return _UnavailableQwenService()


def _build_unavailable_vector_store():
    class _UnavailableVectorStore:
        available = False

        def search(self, *_args, **_kwargs):
            return []

        def upsert_user_data(self, *_args, **_kwargs):
            return False

    return _UnavailableVectorStore()


try:
    from app.services.qwen_service import QwenService, get_qwen_service
except Exception:
    QwenService = None
    _dummy_qwen_service = _build_unavailable_chat_service()

    def get_qwen_service():
        return _dummy_qwen_service

try:
    from app.services.vector_store import VectorStore, get_vector_store
except Exception:
    VectorStore = None
    _dummy_vector_store = _build_unavailable_vector_store()

    def get_vector_store():
        return _dummy_vector_store

__all__ = [
    "VectorStore",
    "get_vector_store",
    "QwenService",
    "get_qwen_service",
]
