import os
import json
import subprocess
import logging
from datetime import datetime
from typing import Dict, Any
from langchain.tools import tool

logger = logging.getLogger(__name__)

# =================工具函数 =================
class ProjectTools:
    # 类变量缓存工具实例
    tools_cache = None

    @classmethod
    def get_all_tools(cls) -> list:
        """获取所有工具实例"""
        if cls.tools_cache is None:
            cls.tools_cache = [
                cls.create_file,
                cls.run_command,
                cls.get_directory_structure
            ]
            logger.info("工具列表初始化完成")
        return cls.tools_cache
    
    @tool
    def create_file(file_path: str, content: str) -> Dict[str, Any]:
        """创建文件并写入内容"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            result = {
                "status": "success",
                "message": f"文件创建成功: {file_path}",
                "file_path": os.path.abspath(file_path)
            }
            logger.info(f"工具调用成功: create_file {json.dumps(result, ensure_ascii=False)}")
            return result
        except Exception as e:
            error_msg = f"文件创建失败: {str(e)}"
            logger.error(f"工具调用失败: create_file {error_msg}")
            return {"status": "error", "message": error_msg}
    @tool
    def run_command(command: str, path: str = ".") -> Dict[str, Any]:
        """在指定目录执行终端命令"""
        try:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                os.makedirs(abs_path, exist_ok=True)

            # 在终端执行命令返回结果
            result = subprocess.run(
                command,
                cwd=abs_path,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15
            )

            def safe_decode(byte_data):
                if not byte_data: 
                    return None
                try:
                    return byte_data.decode('utf-8')
                except UnicodeDecodeError:
                     # 中文Windows默认编码
                    return byte_data.decode('gbk', errors='replace') 
            # 得到结果输出,适配不同的操作编码环境
            stdout = safe_decode(result.stdout)
            stderr = safe_decode(result.stderr)

            # 返回给tool_node节点
            output = {
                "status": "success" if result.returncode == 0 else "error",
                "command": command,
                "output": (stdout or "")[:500], 
                "error": (stderr or "")[:500] if result.returncode != 0 else None
            }
            
            logger.info(f"命令执行结果: {json.dumps(output, ensure_ascii=False)}")
            return output
        except Exception as e:
            error_msg = f"命令执行异常: {str(e)}"
            logger.error(f"命令执行失败: {error_msg}", exc_info=True)
            return {"status": "error", "message": error_msg}
        
    @tool
    def get_directory_structure(path: str = ".") -> Dict[str, Any]:
        """
        获取原始目录结构数据（不包含任何分析逻辑）
        返回包含完整目录树和文件信息的JSON结构
        """
        def scan_directory(directory: str, max_depth: int = 3, current_depth: int = 0) -> Dict:
            if current_depth >= max_depth:
                return {
                    "name": os.path.basename(directory),
                    "type": "directory",
                    "path": directory,
                    "note": f"目录深度超过{max_depth}层已折叠"
                }
            
            structure = {
                "name": os.path.basename(directory),
                "type": "directory",
                "path": directory,
                "items": []
            }
            
            try:
                for item in sorted(os.listdir(directory)):
                    item_path = os.path.join(directory, item)
                    if os.path.isdir(item_path):
                        structure["items"].append(
                            scan_directory(item_path, max_depth, current_depth + 1)
                        )
                    else:
                        structure["items"].append({
                            "name": item,
                            "type": "file",
                            "path": item_path,
                            "size": os.path.getsize(item_path),
                            "extension": os.path.splitext(item)[1].lower()
                        })
            except PermissionError:
                structure["error"] = "权限不足"
            
            return structure

        try:
            abs_path = os.path.abspath(path)
            return {
                "status": "success",
                "path": abs_path,
                "structure": scan_directory(abs_path),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }   

