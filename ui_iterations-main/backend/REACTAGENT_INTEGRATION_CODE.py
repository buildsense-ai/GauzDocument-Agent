# ReactAgent后端项目ID集成代码

import urllib.parse
from fastapi import FastAPI, Request, HTTPException
from enhanced_react_agent import EnhancedReActAgent

# 需要在实际使用时初始化这些变量
# app = FastAPI()
# deepseek_client = DeepSeekClient(...)
# tool_registry = ToolRegistry(...)

@app.post("/react_solve")
async def react_solve(request: Request):
    """处理ReactAgent请求，包含项目上下文"""
    try:
        # 🆕 第一步：提取请求头中的项目信息
        project_id = request.headers.get('x-project-id')
        project_name_encoded = request.headers.get('x-project-name')
        
        # 🆕 第二步：解码项目名称（处理中文字符）
        project_name = None
        if project_name_encoded:
            project_name = urllib.parse.unquote(project_name_encoded)
            
        print(f"🏗️ ReactAgent接收项目上下文: ID={project_id}, Name={project_name}")
        
        # 解析请求体
        body = await request.json()
        problem = body.get('problem', '')
        files = body.get('files', [])
        project_context = body.get('project_context', {})
        
        # 🆕 第三步：合并项目信息到上下文
        if project_id:
            project_context.update({
                'project_id': project_id,
                'project_name': project_name
            })
            
        print(f"🔄 最终项目上下文: {project_context}")
        
        # 🆕 第四步：初始化Agent时传入项目上下文
        agent = EnhancedReActAgent(
            deepseek_client=deepseek_client,
            tool_registry=tool_registry,
            max_iterations=10,
            verbose=True,
            enable_memory=True
        )
        
        # 🆕 设置项目上下文到工具注册表
        if hasattr(tool_registry, 'project_context'):
            tool_registry.project_context = project_context
        
        # 处理问题求解
        result = await agent.solve_problem_async(problem)
        
        return {
            "success": True,
            "content": [{"text": result.response}],
            "thinking_process": result.thinking_process,
            "total_iterations": result.total_iterations,
            "project_info": {  # 🆕 返回项目信息确认
                "project_id": project_id,
                "project_name": project_name
            }
        }
        
    except Exception as e:
        print(f"❌ ReactAgent处理错误: {e}")
        return {
            "isError": True,
            "content": [{"text": f"处理失败: {str(e)}"}]
        } 