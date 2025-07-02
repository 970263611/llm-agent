import os
import json
import logging
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain_core.messages import ToolMessage, BaseMessage
from langgraph.graph import StateGraph, END
from workflow_nodes import (
    agent_node, tool_node, user_inquiry_node, 
    require_confirmation, route
)
from workflow_nodes import(AgentState)
from langchain_core.messages import ToolMessage


# ================= 日志配置 =================
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_execution.log'),
        logging.StreamHandler()
    ]
)

# ================= 创建工作流,节点连线形成图 =================
def create_workflow():
    logger = logging.getLogger(__name__)
    logger.info("初始化工作流...")
    
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
    workflow.config = {"recursion_limit": 45}
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

    try:
        while True:
            # 获取用户输入
            user_input = input("\n> ").strip()
            if not user_input:
                continue

            # 创建新状态时保留所有历史消息
            state["messages"].append(HumanMessage(content=user_input))

            # 执行工作流
            output = app.invoke(state)
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
    except Exception as e:
        logger.error(f"系统错误: {str(e)}")
        print(f"\n发生系统错误: {str(e)}")


if __name__ == "__main__":
    main()