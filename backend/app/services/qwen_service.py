"""
千问 AI 服务 - DashScope 集成
"""

import dashscope
from dashscope import Generation
import os
import logging
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)


class QwenService:
    """千问大模型服务"""
    
    def __init__(self):
        self.api_key = os.getenv("QWEN_API_KEY")
        self.model = os.getenv("QWEN_MODEL", "qwen-plus")
        dashscope.api_key = self.api_key
        
        # 系统提示词
        self.system_prompt = """你是广东财经大学的校园AI助手，专门帮助学生查询教务信息、解答学业相关问题。

你的职责：
1. 根据提供的教务数据，准确回答学生的问题
2. 如果数据不足，告知学生需要先同步教务数据
3. 保持友好、专业的语气
4. 对于敏感信息（如密码），绝不存储或泄露

回答格式：
- 直接给出答案，不要过多寒暄
- 涉及数据时，可以简要列出关键信息
- 如有需要，可以建议学生查看具体页面

当前时间：2026年"""
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict:
        """
        与千问对话
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}, ...]
            temperature: 温度参数，控制创造性
        
        Returns:
            {"success": True, "content": "...", "usage": {...}}
        """
        try:
            # 添加系统提示
            full_messages = [{"role": "system", "content": self.system_prompt}] + messages
            
            response = Generation.call(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                result_format="message"
            )
            
            if response.status_code == 200:
                result = response.output.choices[0].message
                usage = response.usage
                
                logger.info(f"✅ 千问调用成功，消耗token: {usage.total_tokens}")
                
                return {
                    "success": True,
                    "content": result.content,
                    "role": result.role,
                    "usage": {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.total_tokens
                    }
                }
            else:
                logger.error(f"❌ 千问调用失败: {response.message}")
                return {
                    "success": False,
                    "message": f"AI服务错误: {response.message}"
                }
                
        except Exception as e:
            logger.error(f"❌ 千问服务异常: {str(e)}")
            return {
                "success": False,
                "message": f"AI服务异常: {str(e)}"
            }
    
    def chat_with_rag(self, question: str, context: List[Dict], conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        RAG 增强对话
        
        Args:
            question: 用户问题
            context: 检索到的相关文档 [{"text": "...", "source": "...", "score": 0.9}, ...]
            conversation_history: 历史对话
        """
        try:
            # 构建上下文
            context_text = "\n\n".join([
                f"【{i+1}】{item['text']}\n来源: {item['source']}"
                for i, item in enumerate(context)
            ])
            
            # 构建提示词
            prompt = f"""基于以下教务数据，回答学生的问题：

=== 相关数据 ===
{context_text}

=== 学生问题 ===
{question}

请根据以上数据回答问题。如果数据不足以回答问题，请说明需要同步更多数据。"""
            
            # 构建消息
            messages = []
            if conversation_history:
                messages.extend(conversation_history[-6:])  # 最近3轮对话
            messages.append({"role": "user", "content": prompt})
            
            # 调用千问
            result = self.chat(messages)
            
            if result["success"]:
                return {
                    "success": True,
                    "content": result["content"],
                    "usage": result["usage"],
                    "sources": [item["source"] for item in context]  # 返回引用来源
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"❌ RAG对话失败: {str(e)}")
            return {
                "success": False,
                "message": f"RAG对话失败: {str(e)}"
            }
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        生成文本向量（使用千问的embedding模型）
        
        注意：千问目前主要提供文本生成，embedding可以使用其他模型
        这里使用简单的文本特征作为示例，实际项目中可以使用：
        - sentence-transformers
        - OpenAI embedding
        - 或其他开源embedding模型
        """
        try:
            # 由于dashscope的embedding可能需要单独配置，这里返回空列表
            # 实际使用时需要接入具体的embedding服务
            from dashscope import TextEmbedding
            
            response = TextEmbedding.call(
                model="text-embedding-v2",
                input=text
            )
            
            if response.status_code == 200:
                embedding = response.output["embeddings"][0]["embedding"]
                return embedding
            else:
                logger.error(f"❌ Embedding生成失败: {response.message}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Embedding服务异常: {str(e)}")
            return []


# 全局实例
qwen_service = QwenService()
