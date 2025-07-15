import os
import json
import logging
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain_core.messages import ToolMessage, BaseMessage
from langgraph.graph import StateGraph, END
from tools import ProjectTools
from workflow_nodes import (
    agent_node, tool_node, user_inquiry_node, 
    require_confirmation, route
)
from workflow_nodes import(AgentState)
from langchain_core.messages import ToolMessage
from config_loader import CONFIG
import logging


log_config = CONFIG["log_config"]

# 仅在日志启用时配置
if log_config["enabled"]:
    handlers = [logging.FileHandler(log_config["filename"])]
    if log_config["console_output"]:
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=getattr(logging, log_config["level"]),
        format=log_config["format"],
        handlers=handlers
    )

logger = logging.getLogger(__name__)

# ================= 创建工作流,节点连线形成图 =================
def create_workflow():
    logger = logging.getLogger(__name__)
    logger.debug("初始化工作流...")
    
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("user_inquiry", user_inquiry_node)
    workflow.add_node("require_confirmation", require_confirmation)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        route,
        {
            "agent": "agent",
            "tools": "tools",
            "user_inquiry": "user_inquiry",
            "require_confirmation": "require_confirmation",
            "end": END
        }
    )

    workflow.add_edge("tools", "agent")
    workflow.add_edge("user_inquiry", "agent")
    workflow.add_edge("require_confirmation", "agent")
    return workflow.compile()


# ================= 主程序 =================
def main():
    print("智能编程项目助手 (输入'退出'结束或'继续'确认)")
    # 创建工作流
    app = create_workflow()
    # 获取系统信息
    sys_info = {
        "os": os.name,
        "cwd": os.getcwd(),
        "path_sep": os.sep
    }
    system_message = SystemMessage(
        content=f"""
        你是一个专业的项目创建助手。你的任务是帮助用户创建、配置和运行项目。
        [系统环境]
        - 操作系统: {sys_info['os']}
        - 工作目录: {sys_info['cwd']}
        - 路径分隔符: '{sys_info['path_sep']}'
        
        [系统规则]
        1. 所有路径必须相对于: {sys_info['cwd']}
        2. 禁止使用需要提升权限的命令
        3. 自动转换路径分隔符

        [工作流程]:
        1. 首先确认项目需求(名称、包名、依赖等)
        2. 创建项目结构
        3. 生成必要的配置文件
        4. 创建启动类和业务类
        5. 测试项目是否可以正常运行

        [工作规则]:
        - 默认路径为当前路径
        - 使用Maven构建项目
        - 不要调用任何第三方库，手动创建项目结构
        - 每次只执行一个明确的步骤
        - 尽量减少与用户的交流，能自主一次完成,就避免询问用户

        [文件处理能力]
        - 你现在可以分析用户上传的文件，用户通过输入 #文件路径 的方式上传文件。
        - 文件内容会直接提供给你，你可以根据内容进行分析和回答。
        - 文件分析后的返回结构，采用标准的JSON格式返回

        响应格式:
        - 对于操作执行: 使用工具函数
        - 对于信息询问: 直接回复用户
        """
    )
    # 初始状态包含系统消息
    state = AgentState(
        messages=[system_message],
        project_path=None,
        recursion_count=0,
        should_terminate=False,
        is_waiting_response=False
    )

    while True:
        try:
            # 获取用户输入
            user_input = input("\n> ").strip()
            if not user_input:
                continue

            # 检查是否是文件上传指令
            if user_input.startswith('#'):
                file_path = user_input[1:].strip()
                if not file_path:
                    print("\n错误: 请提供有效的文件路径")
                    continue
                
                # 调用文件分析工具
                print(f"\n正在分析文件: {file_path}")
                analysis_result = ProjectTools.upload_and_analyze_file(file_path)
                
                if analysis_result["status"] == "success":
                    # 构造包含文件内容的消息
                    file_content = f"""
                    [文件分析结果]
                    文件名: {analysis_result["file_name"]}
                    文件大小: {analysis_result["file_size"]}字节
                    内容预览:
                    {analysis_result["content"]} 
                    """
                    state["messages"].append(HumanMessage(content=file_content))
                    print("\n文件内容已加载，请告诉我如何分析")
                    continue
                else:
                    print(f"\n文件分析失败: {analysis_result['message']}")
                    continue

            # 创建新状态时保留所有历史消息
            state["messages"].append(HumanMessage(content=user_input))

            # 执行工作流
            output = app.invoke(state, config={"recursion_limit": 1000})
            state = output
            last_message = state["messages"][-1]

            if isinstance(last_message, AIMessage):
                if hasattr(last_message, "tool_calls"):
                    print("\n正在执行操作...")
                else:
                    print(f"\n助手: {last_message.content}")

            elif isinstance(last_message, ToolMessage):
                result = json.loads(last_message.content)
                print(f"\n[操作结果 {result.get('status', 'unknown')}]: {result.get('message', '')}")

            if state.get("should_terminate", False):
                print("\n会话已结束")
                break
        except KeyboardInterrupt:
            print("\n会话已终止")
            break
        except Exception as e:
            logger.error(f"系统错误: {str(e)}")
            continue
        


if __name__ == "__main__":
    main()