from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from langchain.schema import AIMessage
import os
import tempfile
from tools import ProjectTools
from llm_service import llm
import json
import re

app = FastAPI()

@app.post("/analyze-file")
async def analyze_file(
    file: UploadFile = File(...),
    analysis_instructions: str = Form("请分析此文件内容")
):
    """
    上传并分析文件的HTTP接口
    参数:
        file: 上传的文件 (PDF, Excel, Word, CSV等)
        analysis_instructions: 对LLM的具体分析指令
        
    返回:
        包含文件内容摘要和元数据的JSON响应，适合LLM进一步处理
    """
    try:
        # 获取原始文件名和扩展名
        original_filename = file.filename
        file_ext = os.path.splitext(original_filename)[1].lower()
        
        # 创建保留原始扩展名的临时文件
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext, 
            prefix="upload_",  
            dir=tempfile.gettempdir() 
        ) as temp_file:
            # 保存上传的文件内容到临时文件
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        print(f"临时文件路径: {temp_path} (保留原始扩展名: {file_ext})")

        # 调用您现有的解析方法
        analysis_result = ProjectTools.upload_and_analyze_file(
            file_path=temp_path,
            analysis_instructions=analysis_instructions
        )
        
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass
        
        prompt = """
                            请严格遵循以下要求：
                            1. 只返回一个合法的JSON对象，不要包含任何额外文本、Markdown代码块或解释
                            2. JSON必须符合以下结构：{json_schema}
                            3. 如果无法完成请求，返回格式：{{"error": "原因"}}

                            输入内容：
                            {input_text}

                            分析要求：
                            {instructions}
                            """

        # 2. 提供JSON Schema示例（可选）
        json_schema = {
            "文档名称": "string",
            "报告期末按行业分类的境内股票投资组合": [
                {
                    "行业类别": "string",
                    "占基金资产净值比例（%）": "float"
                }
            ],
            # ...其他字段...
        }
        if analysis_result["status"] == "success":
            # 构造包含文件内容的消息
            file_content = f"""
            [文件分析结果]
            文件名: {analysis_result["file_name"]}
            文件大小: {analysis_result["file_size"]}字节
            内容预览:
            {analysis_result["content"]} 
            要求指令:
            {analysis_result["instructions"]} 
            """
            llm_messages = []
            llm_messages.append({"role": "system", "content": str(prompt)})
            llm_messages.append({"role": "user", "content": str(file_content)})
            response = llm.chat(llm_messages)
          
            if isinstance(response, AIMessage):
                return JSONResponse(content=response.content)        
        else:
            raise HTTPException(status_code=400, detail=analysis_result["message"])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")
    
def parse_llm_json_response(llm_response: str) -> dict:

    # 情况1：如果已经是dict直接返回
    if isinstance(llm_response, dict):
        return llm_response
    
    # 情况2：处理包含```json标记的响应
    if "```json" in llm_response:
        # 使用正则表达式提取json内容
        json_str = re.search(r'```json\n(.*?)\n```', llm_response, re.DOTALL)
        if json_str:
            return json.loads(json_str.group(1))
    
    # 情况3：尝试直接解析（可能是纯JSON字符串）
    try:
        return json.loads(llm_response)
    except json.JSONDecodeError:
        # 情况4：处理没有标记但格式良好的JSON
        cleaned = llm_response.strip().strip('`')
        return json.loads(cleaned)
