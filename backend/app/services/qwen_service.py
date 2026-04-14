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
        self.available = False
        
        if not self.api_key:
            logger.warning("⚠️ QWEN_API_KEY 未配置，AI 服务不可用")
            return
        
        dashscope.api_key = self.api_key
        self.available = True
        
        # 系统提示词
        self.system_prompt = """你是广东财经大学的校园AI助手，专门帮助学生查询教务信息、解答学业相关问题。

你的职责：
1. 根据提供的教务数据，准确回答学生的问题
2. 当学生询问成绩、课表、考试、个人信息等教务数据时，使用工具查询最新数据
3. 保持友好、专业的语气
4. 对于敏感信息（如密码），绝不存储或泄露

回答格式：
- 直接给出答案，不要过多寒暄
- 涉及数据时，可以简要列出关键信息
- 如有需要，可以建议学生查看具体页面

当前时间：2026年"""

        # 工具定义（千问 function calling 格式）
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "query_personal_info",
                    "description": "查询学生的个人信息，包括姓名、学号、专业、班级、学院等",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_grades",
                    "description": "查询学生的课程成绩，可按课程名称或学期筛选",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "course_name": {
                                "type": "string",
                                "description": "课程名称（可选，模糊匹配）"
                            },
                            "semester": {
                                "type": "string",
                                "description": "学期，如 2024-2025-2（可选）"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_schedule",
                    "description": "查询学生的课程表，可按学期筛选",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "semester": {
                                "type": "string",
                                "description": "学期，如 2024-2025-2（可选）"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_exam_schedule",
                    "description": "查询学生的考试安排，包括考试时间、地点、座位号",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "semester": {
                                "type": "string",
                                "description": "学期（可选）"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_academic_progress",
                    "description": "查询学生的学业进度，包括已修学分、还需学分等",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_training_plan",
                    "description": "查询学生的培养方案，包括课程体系结构、各学期课程安排、学分要求、必修/选修课列表等",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "semester": {
                                "type": "string",
                                "description": "学期，如 2024-2025-1（可选，不指定则返回所有学期）"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "refresh_all_data",
                    "description": "重新爬取教务系统最新数据，当用户要求刷新或更新数据时使用",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict:
        """与千问对话"""
        if not self.available:
            return {"success": False, "message": "AI服务未配置"}
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
    
    def chat_with_tools(self, messages: List[Dict], tools_context: Dict = None) -> Dict:
        """
        带工具调用的对话
        
        Args:
            messages: 对话历史
            tools_context: 工具执行所需的上下文 {"session": ..., "server_url": ..., "username": ...}
        
        Returns:
            {"success": True, "content": "...", "tool_calls": [...], "usage": {...}}
        """
        if not self.available:
            return {"success": False, "message": "AI服务未配置"}
        
        try:
            full_messages = [{"role": "system", "content": self.system_prompt}] + messages
            
            # 第一步：发送带工具定义的请求
            response = Generation.call(
                model=self.model,
                messages=full_messages,
                tools=self.tools,
                temperature=0.7,
                result_format="message"
            )
            
            if response.status_code != 200:
                logger.error(f"❌ 千问工具调用失败: {response.message}")
                return {"success": False, "message": f"AI服务错误: {response.message}"}
            
            assistant_msg = response.output.choices[0].message
            
            # 检查是否有工具调用（兼容dict和对象两种格式）
            if isinstance(assistant_msg, dict):
                tool_calls = assistant_msg.get('tool_calls', None)
            else:
                tool_calls = getattr(assistant_msg, 'tool_calls', None)
            
            logger.info(f"【工具调用】assistant_msg类型: {type(assistant_msg)}, tool_calls: {tool_calls}")
            
            if not tool_calls:
                # 没有工具调用，直接返回回答
                return {
                    "success": True,
                    "content": assistant_msg.content or "",
                    "tool_calls": [],
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            
            # 有工具调用，执行工具
            logger.info(f"【工具调用】AI 请求调用 {len(tool_calls)} 个工具")
            
            # 将 assistant 的工具调用消息加入历史
            full_messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", ""),
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"] if isinstance(tc, dict) else tc.function.name,
                            "arguments": tc["function"]["arguments"] if isinstance(tc, dict) else tc.function.arguments
                        }
                    }
                    for tc in tool_calls
                ]
            })
            
            # 执行每个工具调用
            tool_results = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func_name = tc["function"]["name"]
                    func_args_str = tc["function"]["arguments"]
                    tc_id = tc.get("id", "")
                else:
                    func_name = tc.function.name
                    func_args_str = tc.function.arguments
                    tc_id = getattr(tc, "id", "")
                
                try:
                    func_args = json.loads(func_args_str) if func_args_str else {}
                except json.JSONDecodeError:
                    func_args = {}
                
                logger.info(f"【工具调用】执行: {func_name}({func_args})")
                
                # 执行工具
                tool_result = self._execute_tool(func_name, func_args, tools_context)
                tool_results.append({"name": func_name, "result": tool_result})
                
                # 将工具结果加入消息历史
                full_messages.append({
                    "role": "tool",
                    "content": json.dumps(tool_result, ensure_ascii=False),
                    "name": func_name
                })
            
            # 第二步：将工具结果发回千问，获取最终回答
            response2 = Generation.call(
                model=self.model,
                messages=full_messages,
                tools=self.tools,
                temperature=0.7,
                result_format="message"
            )
            
            if response2.status_code != 200:
                logger.error(f"❌ 千问第二次调用失败: {response2.message}")
                return {"success": False, "message": f"AI服务错误: {response2.message}"}
            
            final_msg = response2.output.choices[0].message
            total_usage = {
                "input_tokens": response.usage.input_tokens + response2.usage.input_tokens,
                "output_tokens": response.usage.output_tokens + response2.usage.output_tokens,
                "total_tokens": response.usage.total_tokens + response2.usage.total_tokens
            }
            
            logger.info(f"✅ 工具调用完成，消耗token: {total_usage['total_tokens']}")
            
            return {
                "success": True,
                "content": final_msg.content or "",
                "tool_calls": [{"name": tr["name"]} for tr in tool_results],
                "sources": [tr["name"] for tr in tool_results],
                "usage": total_usage
            }
            
        except Exception as e:
            logger.error(f"❌ 工具调用异常: {str(e)}")
            return {"success": False, "message": f"AI工具调用异常: {str(e)}"}
    
    def _execute_tool(self, func_name: str, args: Dict, context: Dict = None) -> Dict:
        """执行具体的工具函数"""
        if not context:
            return {"error": "未登录教务系统，无法查询数据"}
        
        session = context.get("session")
        server_url = context.get("server_url")
        username = context.get("username")
        
        if not session or not server_url:
            return {"error": "用户未登录教务系统，请先登录"}
        
        try:
            from scraper import JwxtScraper
            scraper = JwxtScraper(session, server_url)
            
            if func_name == "query_personal_info":
                result = scraper.get_personal_info()
                return result.get("data", {}) if result.get("success") else {"error": result.get("message", "查询失败")}
            
            elif func_name == "query_grades":
                result = scraper.get_grades(
                    kcmc=args.get("course_name", ""),
                    kksj=args.get("semester", "")
                )
                if result.get("success"):
                    return {
                        "成绩列表": result.get("data", []),
                        "总数": result.get("count", 0),
                        "统计": result.get("stats", {})
                    }
                return {"error": result.get("message", "查询失败")}
            
            elif func_name == "query_schedule":
                result = scraper.get_schedule(
                    semester=args.get("semester", "")
                )
                if result.get("success"):
                    return {
                        "课表": result.get("data", []),
                        "总数": result.get("count", 0)
                    }
                return {"error": result.get("message", "查询失败")}
            
            elif func_name == "query_exam_schedule":
                result = scraper.get_exam_schedule(
                    semester=args.get("semester", "")
                )
                if result.get("success"):
                    return {
                        "考试安排": result.get("data", []),
                        "总数": result.get("count", 0)
                    }
                return {"error": result.get("message", "查询失败")}
            
            elif func_name == "query_academic_progress":
                result = scraper.get_academic_progress()
                if result.get("success"):
                    return result.get("data", {})
                return {"error": result.get("message", "查询失败")}
            
            elif func_name == "query_training_plan":
                result = scraper.get_my_training_plan()
                if result.get("success"):
                    data = result.get("data", {})
                    courses = data.get("课程列表", [])
                    
                    # 如果指定了学期，过滤
                    semester_filter = args.get("semester", "")
                    if semester_filter:
                        courses = [c for c in courses if c.get("学期") == semester_filter]
                    
                    return {
                        "培养方案": courses,
                        "总课程数": len(courses),
                        "学期分布": list(set(c.get("学期", "") for c in courses))
                    }
                return {"error": result.get("message", "查询失败")}
            
            elif func_name == "refresh_all_data":
                # 触发全量重新爬取
                result = scraper.get_all_data_for_vectorization()
                if result.get("success"):
                    # 同时更新数据库和向量库
                    self._update_stored_data(username, result["data"])
                    return {"状态": "数据已刷新", "数据概览": {
                        "个人信息": bool(result["data"].get("个人信息")),
                        "成绩数量": len(result["data"].get("成绩信息", {}).get("成绩列表", [])),
                        "课表数量": len(result["data"].get("课表信息", [])),
                        "考试数量": len(result["data"].get("考试安排", []))
                    }}
                return {"error": result.get("message", "刷新失败")}
            
            else:
                return {"error": f"未知工具: {func_name}"}
                
        except Exception as e:
            logger.error(f"【工具执行】{func_name} 失败: {e}")
            return {"error": f"工具执行失败: {str(e)}"}
    
    def _update_stored_data(self, username: str, raw_data: Dict):
        """刷新数据后更新数据库和向量库"""
        try:
            from app.models import get_db, User
            from app.services.data_processor import data_processor
            
            db = next(get_db())
            try:
                data_processor.process_and_store(username, raw_data, db)
                user = db.query(User).filter(User.username == username).first()
                if user:
                    data_processor.vectorize_and_store(user.id, username, raw_data)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"【数据更新】失败: {e}")

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


# 全局实例（懒加载）
_qwen_service = None

def get_qwen_service() -> QwenService:
    """获取千问服务实例（懒加载）"""
    global _qwen_service
    if _qwen_service is None:
        _qwen_service = QwenService()
    return _qwen_service
