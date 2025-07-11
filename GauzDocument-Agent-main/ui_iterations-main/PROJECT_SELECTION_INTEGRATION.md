# 项目选择页面集成文档

## 概述

本文档详细说明了项目选择页面与现有前端系统的集成，以及项目级别知识库隔离功能的实现。

## 功能特性

### 1. 项目选择入口
- **项目选择页面**: `project_select_v3_clean.html`
- **功能**: 用户可以选择具体的项目（如"刘氏宗祠"、"医灵古庙"）
- **跳转**: 点击项目后跳转到对话页面，携带项目信息

### 2. 项目级别知识库隔离
- **RAG工具项目过滤**: 根据项目名称过滤知识库检索结果
- **智能项目识别**: 自动从查询中提取项目名称
- **项目上下文传递**: 在整个对话过程中保持项目上下文

## 前端修改

### 1. 项目选择页面 (`project_select_v3_clean.html`)

**修改内容**:
```javascript
// 原始跳转逻辑
function selectProject(projectId) {
    console.log('选择项目:', projectId);
    alert(`已选择项目: ${projectId}\n即将跳转到对话页面...`);
    // window.location.href = `frontend_v1_purple.html?project=${projectId}`;
}

// 修改后的跳转逻辑
function selectProject(projectId) {
    // 获取项目信息
    const projectCard = event.target.closest('.project-card');
    const projectTitle = projectCard.querySelector('.project-title').textContent;
    const projectType = projectCard.querySelector('.project-type').textContent;
    
    console.log('选择项目:', projectId, projectTitle);
    
    // 跳转到对话页面，传递项目信息
    const params = new URLSearchParams({
        project: projectId,
        projectName: projectTitle,
        projectType: projectType
    });
    
    window.location.href = `frontend_v2_upgraded.html?${params.toString()}`;
}
```

### 2. 对话页面 (`frontend_v2_upgraded.html`)

**HTML结构修改**:
```html
<!-- 原始聊天标题 -->
<div class="chat-header">
    <div class="chat-title">AI 对话助手</div>
    <div class="status-indicator">
        <div class="status-dot"></div>
        <span id="connectionStatus">已连接</span>
    </div>
</div>

<!-- 修改后的聊天标题 -->
<div class="chat-header">
    <div class="chat-title-section">
        <div class="chat-title">AI 对话助手</div>
        <div class="project-info" id="projectInfo" style="display: none;">
            <span class="project-icon">🏗️</span>
            <span class="project-name" id="projectName"></span>
            <span class="project-type" id="projectType"></span>
        </div>
    </div>
    <div class="status-indicator">
        <div class="status-dot"></div>
        <span id="connectionStatus">已连接</span>
    </div>
</div>
```

**CSS样式添加**:
```css
.chat-title-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.project-info {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
}

.project-icon {
    color: var(--primary-color);
}

.project-name {
    font-weight: 500;
    color: var(--primary-color);
}

.project-type {
    color: var(--text-secondary);
    background: var(--bg-secondary);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
}
```

### 3. 前端脚本 (`frontend_v2_script.js`)

**新增全局变量**:
```javascript
let currentProject = null; // 当前选中的项目信息
```

**新增函数**:
```javascript
// 初始化项目信息
function initializeProject() {
    // 从URL参数中读取项目信息
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project');
    const projectName = urlParams.get('projectName');
    const projectType = urlParams.get('projectType');

    if (projectId && projectName) {
        currentProject = {
            id: projectId,
            name: projectName,
            type: projectType || '项目'
        };

        console.log('🏗️ 初始化项目:', currentProject);

        // 显示项目信息
        displayProjectInfo();

        // 更新欢迎消息
        updateWelcomeMessage();
    } else {
        console.log('📋 未指定项目，使用通用模式');
    }
}

// 显示项目信息
function displayProjectInfo() {
    if (!currentProject) return;

    const projectInfo = document.getElementById('projectInfo');
    const projectName = document.getElementById('projectName');
    const projectType = document.getElementById('projectType');

    if (projectInfo && projectName && projectType) {
        projectName.textContent = currentProject.name;
        projectType.textContent = currentProject.type;
        projectInfo.style.display = 'flex';
        
        console.log('✅ 项目信息已显示:', currentProject.name);
    }
}

// 更新欢迎消息
function updateWelcomeMessage() {
    if (!currentProject) return;

    const welcomeTitle = document.querySelector('.welcome-title');
    const welcomeSubtitle = document.querySelector('.welcome-subtitle');

    if (welcomeTitle && welcomeSubtitle) {
        welcomeTitle.textContent = `欢迎来到 ${currentProject.name} 项目`;
        welcomeSubtitle.textContent = `您正在处理 ${currentProject.type} 相关的文档。点击左侧"新建对话"开始，或选择下方场景快速开始`;
    }
}
```

**修改聊天发送逻辑**:
```javascript
// 在sendMessage函数中添加项目信息传递
const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        message: message,
        files: currentFiles,
        project: currentProject  // 传递项目信息
    })
});
```

**修改文件上传逻辑**:
```javascript
// 在文件上传函数中添加项目信息
const formData = new FormData();
formData.append('file', file);

// 如果有项目信息，添加到FormData中
if (currentProject) {
    formData.append('project', JSON.stringify(currentProject));
}
```

### 4. 前端服务器 (`start_direct_frontend.js`)

**文件上传API修改**:
```javascript
// 获取项目信息
let projectInfo = null;
if (req.body.project) {
    try {
        projectInfo = JSON.parse(req.body.project);
        console.log(`🏗️ 文件上传包含项目信息: ${projectInfo.name}`);
    } catch (e) {
        console.warn('⚠️ 项目信息解析失败:', e);
    }
}

const fileInfo = {
    success: true,
    message: '文件上传到本地存储成功',
    originalName: originalName,
    filePath: localFilePath,
    localPath: localFilePath,
    reactAgentPath: localFilePath,
    size: file.size,
    mimetype: file.mimetype,
    fileName: path.basename(localFilePath),
    project: projectInfo // 包含项目信息
};
```

**流式聊天API修改**:
```javascript
// 接收项目信息
const { message, files = [], project } = req.body;

// 如果有项目信息，添加到问题描述中
if (project && project.name) {
    requestData.problem = `[项目: ${project.name}] ${message}`;
    console.log(`🏗️ 添加项目上下文: ${project.name}`);
}
```

## 后端修改

### 1. ReactAgent系统 (`server/main.py`)

**StreamingReActAgent类修改**:
```python
class StreamingReActAgent:
    def __init__(self, deepseek_client, tool_registry, max_iterations=10, verbose=True, enable_memory=True):
        self.client = deepseek_client
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.enable_memory = enable_memory
        self.current_project = None  # 当前项目上下文
        
        # 构建系统提示词
        self.system_prompt = self._build_system_prompt()
```

**问题解析修改**:
```python
async def solve_stream(self, problem):
    """流式解决问题"""
    try:
        # 提取项目信息
        self.current_project = None
        if problem.startswith('[项目: '):
            # 从问题中提取项目信息
            end_bracket = problem.find(']')
            if end_bracket != -1:
                project_info = problem[1:end_bracket]  # 去掉开头的 '['
                if project_info.startswith('项目: '):
                    self.current_project = project_info[4:]  # 去掉 '项目: '
                    print(f"🏗️ 提取到项目信息: {self.current_project}")
                    # 移除项目前缀，保留原始问题
                    problem = problem[end_bracket + 1:].strip()
```

**工具执行修改**:
```python
async def _execute_action(self, action, action_input):
    """执行工具行动 (异步，使用线程池处理阻塞I/O)"""
    try:
        # ... 现有代码 ...
        
        # 🆕 如果是RAG工具且有项目上下文，自动添加项目信息
        if action == "rag_tool" and self.current_project:
            if tool_action in ["search", "search_images", "search_tables"]:
                # 为搜索操作添加项目过滤
                params["project_name"] = self.current_project
                print(f"🏗️ 为RAG工具添加项目上下文: {self.current_project}")
            elif tool_action == "process_parsed_folder":
                # 为文件夹处理操作添加项目名称
                if "project_name" not in params:
                    params["project_name"] = self.current_project
                    print(f"🏗️ 为PDF解析文件夹处理添加项目名称: {self.current_project}")
        
        # 调用工具，第一个参数是action，其余通过kwargs传递
        return await run_in_threadpool(tool.execute, tool_action, **params)
```

### 2. RAG工具 (`src/rag_tool_chroma.py`)

**已有的项目过滤功能**:
- `_search_documents`: 支持 `project_name` 参数进行项目隔离搜索
- `_search_images`: 支持 `project_name` 参数进行图片搜索的项目隔离
- `_search_tables`: 支持 `project_name` 参数进行表格搜索的项目隔离
- `_extract_project_name_from_query`: 智能从查询中提取项目名称

**智能项目识别功能**:
```python
def _extract_project_name_from_query(self, query: str) -> Optional[str]:
    """
    从查询中智能提取项目名称
    """
    try:
        # 获取所有可用项目
        if hasattr(self.pdf_embedding_service, 'get_available_projects'):
            available_projects = self.pdf_embedding_service.get_available_projects()
            
            # 按长度排序，优先匹配更长的项目名称
            available_projects = sorted(available_projects, key=len, reverse=True)
            
            # 检查查询是否包含项目名称
            for project in available_projects:
                if query in project:
                    return project
            
            # 智能关键词匹配
            for project in available_projects:
                project_core = project.replace("设计方案", "").replace("修缮设计方案", "").replace("项目", "").replace("文物", "").strip()
                
                if project_core and query in project_core:
                    return project
                
                if project_core and project_core in query:
                    return project
        
        return None
        
    except Exception as e:
        logger.warning(f"项目名称提取失败: {e}")
        return None
```

## 使用流程

### 1. 项目选择流程
1. 用户访问 `project_select_v3_clean.html` 页面
2. 点击具体项目卡片（如"某市政工程项目"）
3. 页面跳转到 `frontend_v2_upgraded.html?project=project1&projectName=某市政工程项目&projectType=市政工程`
4. 前端读取URL参数，初始化项目信息
5. 界面显示项目信息，更新欢迎消息

### 2. 项目隔离对话流程
1. 用户在对话界面输入消息
2. 前端将消息和项目信息发送到后端
3. 后端提取项目信息，添加到问题前缀
4. ReactAgent解析问题，提取项目上下文
5. 当调用RAG工具时，自动添加项目过滤参数
6. RAG工具根据项目名称过滤知识库检索结果
7. 返回特定项目的搜索结果

### 3. 文件上传项目标识流程
1. 用户上传文件时，前端携带项目信息
2. 后端接收文件和项目信息
3. 文件存储时关联项目信息
4. 后续RAG处理时使用项目标识

## 测试方式

### 1. 项目选择测试
1. 访问 `http://localhost:3001/project_select_v3_clean.html`
2. 点击任意项目卡片
3. 验证是否正确跳转到对话页面
4. 检查URL参数是否正确传递

### 2. 项目信息显示测试
1. 从项目选择页面进入对话页面
2. 验证聊天标题下方是否显示项目信息
3. 检查欢迎消息是否包含项目名称

### 3. 项目隔离测试
1. 先上传不同项目的文件到知识库
2. 从项目选择页面进入特定项目
3. 进行知识库搜索
4. 验证搜索结果是否只包含当前项目的内容

## 注意事项

1. **项目名称匹配**: RAG工具中的项目名称必须与上传文件时的项目名称完全匹配
2. **URL参数编码**: 项目名称包含中文时需要正确的URL编码
3. **项目信息传递**: 确保在整个对话过程中项目信息正确传递
4. **后端兼容性**: 后端需要支持项目信息的解析和处理

## 扩展功能

### 1. 项目管理
- 添加项目创建/编辑/删除功能
- 项目配置管理
- 项目成员权限管理

### 2. 知识库管理
- 项目级别的知识库统计
- 文件分类和标签管理
- 项目知识库导入/导出

### 3. 界面优化
- 项目切换功能
- 项目历史记录
- 项目收藏功能

## 结论

通过本次集成，成功实现了：
1. 项目选择入口页面
2. 项目级别的知识库隔离
3. 项目信息在前后端的完整传递
4. 智能的项目识别和过滤

这样的设计使得用户可以在不同项目之间进行隔离的对话和文档处理，提高了系统的实用性和数据安全性。 