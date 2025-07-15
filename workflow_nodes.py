import os
import json
import logging
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain_core.messages import ToolMessage, BaseMessage
from langchain.schema import SystemMessage, HumanMessage
from llm_service import llm
from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from tools import ProjectTools

logger = logging.getLogger(__name__)

# =================类型定义 =================
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    project_path: Optional[str]
    recursion_count: int
    should_terminate: bool
    is_waiting_response: bool

 

# =================工作流节点 =================
def agent_node(state: AgentState):
    ("\n[AGENT_NODE] 进入agent节点")
    recursion_count = state.get("recursion_count", 0)

    # 确保至少包含系统消息和用户输入
    if len(state["messages"]) < 2:
        logger.debug("[ERROR] 消息历史不完整！")
        return state

    if state.get("should_terminate", False):
        return state
    
    # 转换消息格式时确保包含所有历史
    messages = state["messages"]
    llm_messages = []
    for m in messages:
        if isinstance(m, SystemMessage):
            llm_messages.append({"role": "system", "content": str(m.content)})
        elif isinstance(m, HumanMessage):
            llm_messages.append({"role": "user", "content": str(m.content)})
        elif isinstance(m, AIMessage):
            new_msg = {"role": "assistant", "content": str(m.content)}
            if hasattr(m, "tool_calls") and m.tool_calls:
                new_msg["tool_calls"] = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call["args"])
                        }
                    }
                    for call in m.tool_calls
                ]
            llm_messages.append(new_msg)
        elif isinstance(m, ToolMessage):
            llm_messages.append({
                "role": "tool",
                "content": str(m.content),
                "tool_call_id": m.tool_call_id
            })


    response = llm.chat(llm_messages)
    logger.debug(f"LLM响应: {response.content[:200]}...")

    return {
        # 保留完整历史+新响应
        "messages": messages + [response],
        "recursion_count": recursion_count + 1,
        "should_terminate": False,
        "is_waiting_response": False
    }

def route(state: AgentState):
    logger.debug("进入了route")
    last_message = state["messages"][-1]
    recursion_count = state.get("recursion_count", 0)
    # 优先处理终止条件（用户输入exit/quit）
    if isinstance(last_message, HumanMessage):
        if last_message.content.lower() in ["exit", "quit", "退出"]:
            return "end"

    # 检查是否在等待用户响应
    if state.get("is_waiting_response", False):
        return "user_inquiry"  

    # 检查工具调用
    if isinstance(last_message, AIMessage):
        tool_calls = getattr(last_message, "tool_calls", [])
        if tool_calls and len(tool_calls) > 0:  
            return "tools"
        # 其他AI回复默认需要用户确认
        return "user_inquiry"

    # 递归限制检查
    if recursion_count >= 45:
        return "require_confirmation"

    return "agent"

def tool_node(state: AgentState):
    logger.debug("\n[TOOL_NODE] 进入tool节点")
    recursion_count = state.get("recursion_count", 0)

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls"):
        return state
    tool_messages = []
    tools = ProjectTools.get_all_tools()
    for tool_call in last_message.tool_calls:
        tool_func = next((t for t in tools if t.name == tool_call["name"]), None)

        if tool_func:
            logger.info(f"执行工具: {tool_call['name']}")
            try:
                # 反射执行函数,将结果封装成ToolMessage,返回给工作流
                result = tool_func.invoke(tool_call["args"])
                tool_messages.append(ToolMessage(
                    content=json.dumps(result),
                    tool_call_id=tool_call["id"]
                ))

                if "file_path" in result:
                    state["project_path"] = os.path.dirname(result["file_path"])
            except Exception as e:
                logger.error(f"工具执行异常: {str(e)}")
                tool_messages.append(ToolMessage(
                    content=json.dumps({"status": "error", "message": str(e)}),
                    tool_call_id=tool_call["id"]
                ))

    return {
        "messages": state["messages"] + tool_messages,
        "recursion_count": recursion_count + 1,
        "should_terminate": False,
        "is_waiting_response": False
    }

def user_inquiry_node(state: AgentState):
    """处理用户询问节点：
    1. 显示AI的询问消息给用户
    2. 获取用户输入
    3. 将用户响应加入消息历史
    """
    last_ai_message = state["messages"][-1]
    # 1. 显示AI的询问消息
    if isinstance(last_ai_message, AIMessage):
        print(f"\n助手: {last_ai_message.content}")

    # 2. 获取用户输入
    try:
        user_input = input("> ").strip()
        if not user_input:
            user_input = "[无输入]"
    except KeyboardInterrupt:
        user_input = "exit"

    return {
        "messages": state["messages"] + [HumanMessage(content=user_input)],
        "recursion_count": 0,
        "should_terminate": user_input.lower() in ["exit", "quit", "退出"],
        "is_waiting_response": False
    }

def require_confirmation(state: AgentState):
    logger.debug("达到操作限制，等待用户确认")
    return {
        "messages": [AIMessage(content="【确认】已达到操作限制，是否继续？(继续/退出)")],
        "recursion_count": 0,
        "should_terminate": False,
        "is_waiting_response": True
    }

