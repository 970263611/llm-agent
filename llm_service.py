import json
import logging
from langgraph.graph.message import add_messages
from openai import OpenAI
from typing import List, Dict, Any
from langchain.schema import AIMessage
from langchain.tools import BaseTool
from tools import ProjectTools

logger = logging.getLogger(__name__)

# =================连接llm =================
class QwenLLM:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化连接"""
        self.model = "qwen-plus"
        self.client = OpenAI(
            api_key="",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        tools = ProjectTools.get_all_tools()
        self.openai_tools = [self._convert_tool(tool) for tool in tools]
        logger.info("QwenLLM 连接初始化完成")

    def _convert_tool(self, tool: BaseTool) -> Dict[str, Any]:
        """将LangChain工具转换为OpenAI兼容格式"""
        tool_schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
            }
        }
        
        if hasattr(tool, 'args_schema'):
            args_schema = tool.args_schema
            
            if hasattr(args_schema, 'model_json_schema'):
                tool_schema["function"]["parameters"] = args_schema.model_json_schema()
            elif hasattr(args_schema, 'schema'):
                tool_schema["function"]["parameters"] = args_schema.schema()
            else:
                tool_schema["function"]["parameters"] = {"type": "object", "properties": {}}
        else:
            tool_schema["function"]["parameters"] = {"type": "object", "properties": {}}
        
        return tool_schema
    
    def chat(self, messages: List[Dict[str, str]]) -> AIMessage:
        """使用持久化连接生成响应"""
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.openai_tools,
                tool_choice="auto",
                timeout=30  
            )
            msg = completion.choices[0].message
            
            return AIMessage(
                content=msg.content or "",
                tool_calls=[
                    {
                        "name": call.function.name,
                        "args": json.loads(call.function.arguments),
                        "id": call.id
                    }
                    for call in msg.tool_calls
                ] if msg.tool_calls else []
            )
        except Exception as e:
            logger.error(f"LLM请求失败: {str(e)}")
            raise


# 全局单例实例
llm = QwenLLM()

        
    

