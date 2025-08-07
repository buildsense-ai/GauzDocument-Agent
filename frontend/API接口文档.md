# API接口文档

本文档记录了 `ai_chat_interface.html` 和 `project_selector.html` 两个界面中使用的所有API接口。

## 概述

这两个界面主要通过以下方式调用API：
- **前端代理**：通过前端服务器(`frontend_server.js`)代理到后端API
- **直接调用**：部分功能直接调用后端API
- **统一请求函数**：使用`apiRequest`函数统一处理API请求

## 1. ai_chat_interface.html 使用的API接口

### 1.1 聊天相关API

#### 1.1.1 开始流式对话
- **接口**: `POST /api/start_stream`
- **用途**: 启动新的流式对话会话
- **调用位置**: `ai_chat_script.js` 第1025行
- **请求数据**: 
  ```javascript
  {
    message: string,
    files: array,
    project: object
  }
  ```

#### 1.1.2 流式思考过程
- **接口**: `GET /api/stream/thoughts/{session_id}`
- **用途**: 获取AI思考过程的实时流
- **调用位置**: `ai_chat_script.js` 第1042行
- **实现方式**: EventSource (Server-Sent Events)

#### 1.1.3 状态检查
- **接口**: `GET /api/status`
- **用途**: 检查后端服务状态
- **调用位置**: `ai_chat_script.js` 第453行

### 1.2 文件上传API

#### 1.2.1 单文件上传
- **接口**: `POST /api/upload`
- **用途**: 上传单个文件到MinIO存储
- **调用位置**: `ai_chat_script.js` 第547行、第636行
- **请求格式**: FormData
- **支持功能**: 
  - 文件上传进度跟踪
  - 上传状态监控
  - 错误处理

### 1.3 项目管理API

#### 1.3.1 项目验证
- **接口**: `POST /api/project/check`
- **用途**: 验证项目是否存在
- **调用位置**: `ai_chat_script.js` 第2164行

#### 1.3.2 获取项目当前会话
- **接口**: `GET /api/projects/{identifier}/current-session`
- **用途**: 加载项目的聊天历史记录
- **调用位置**: `ai_chat_script.js` 第1727行
- **查询参数**:
  - `by_name`: 是否按名称查询
  - `limit`: 限制返回消息数量

#### 1.3.3 保存消息到项目
- **接口**: `POST /api/projects/{identifier}/messages`
- **用途**: 将对话消息保存到项目数据库
- **调用位置**: `ai_chat_script.js` 第2950行、第3015行
- **支持**: 按项目名称或ID保存

#### 1.3.4 获取项目文件列表
- **接口**: `GET /api/projects/{identifier}/files`
- **用途**: 获取项目关联的文件列表
- **调用位置**: `ai_chat_script.js` 第3746行
- **查询参数**: `by_name=true`

### 1.4 任务管理API

#### 1.4.1 任务状态查询
- **接口**: `GET /api/tasks/{task_id}`
- **用途**: 查询长时间运行任务的状态
- **调用位置**: `ai_chat_script.js` 第2328行
- **功能**: 支持任务轮询和进度跟踪

### 1.5 AI编辑器API

#### 1.5.1 AI文本编辑处理
- **接口**: `POST /api/ai-editor/process`
- **完整URL**: `http://localhost:8000/api/ai-editor/process`
- **用途**: 处理AI文本编辑请求
- **调用位置**: `ai_editor.js` 第212行
- **调用方式**: 直接调用后端API (不通过前端代理)
- **请求数据**:
  ```javascript
  {
    plain_text: [string],
    request: string,
    project_name: string,
    search_type: "hybrid",
    top_k: 5
  }
  ```

## 2. project_selector.html 使用的API接口

### 2.1 项目CRUD操作

#### 2.1.1 获取所有项目
- **接口**: `GET /api/projects`
- **用途**: 加载所有项目列表
- **调用位置**: `project_selector.html` 第897行
- **返回数据**: 项目列表，包含文件数量、消息数量等统计信息

#### 2.1.2 创建新项目
- **接口**: `POST /api/projects`
- **用途**: 创建新的项目
- **调用位置**: `project_selector.html` 第835行
- **请求数据**:
  ```javascript
  {
    name: string,
    type: string,
    description: string
  }
  ```

#### 2.1.3 删除项目
- **接口**: `DELETE /api/projects/{projectId}`
- **用途**: 删除指定项目及其所有数据
- **调用位置**: `project_selector.html` 第873行
- **影响**: 删除项目的所有对话记录和文件

## 3. 前端服务器代理API

前端服务器(`frontend_server.js`)作为代理层，提供以下API端点：

### 3.1 代理配置

#### 3.1.1 流式API代理
- **代理路径**: `/api/stream/*` → `http://localhost:8000/stream/*`
- **用途**: 代理所有流式API请求

#### 3.1.2 AI编辑器代理
- **代理路径**: `/api/ai-editor/*` → `http://localhost:8000/api/ai-editor/*`
- **用途**: 代理AI编辑器相关请求

### 3.2 直接处理的API

#### 3.2.1 文件上传
- **接口**: `POST /api/upload`
- **处理**: 前端接收文件后转发到后端
- **功能**: 支持文件类型验证、大小限制

#### 3.2.2 聊天API
- **接口**: `POST /api/chat`
- **处理**: 处理聊天请求并转发到后端

#### 3.2.3 项目管理
- **接口群**: 
  - `GET /api/projects`
  - `POST /api/projects`
  - `DELETE /api/projects/:identifier`
  - `GET /api/projects/:identifier/summary`
  - `GET /api/projects/:identifier/current-session`
  - `POST /api/projects/:identifier/messages`
  - `GET /api/projects/:identifier/files`

## 4. API调用方式说明

### 4.1 两种调用方式

本系统中的API调用分为两种方式：

#### 4.1.1 通过前端代理调用 (推荐)
- **路径格式**: `/api/*`
- **实际访问**: `http://localhost:3003/api/*` → `http://localhost:8000/api/*`
- **优势**: 统一管理、错误处理、请求头自动添加
- **适用**: 大部分API接口

#### 4.1.2 直接调用后端API
- **路径格式**: `http://localhost:8000/api/*`
- **用途**: 特殊需求或独立功能
- **示例**: AI编辑器API
- **注意**: 需要手动处理跨域、错误处理等

## 5. API请求特点

### 5.1 统一请求处理
- **函数**: `apiRequest(url, options)`
- **位置**: `ai_chat_script.js` 第29行
- **功能**:
  - 自动添加项目ID和项目名称到请求头
  - 统一错误处理
  - 支持FormData和JSON格式

### 5.2 请求头管理
```javascript
// 自动添加的请求头
headers: {
  'X-Project-ID': currentProject.id,
  'X-Project-Name': encodeURIComponent(currentProject.name)
}
```

### 5.3 错误处理
- 网络错误重试机制
- 用户友好的错误提示
- 控制台详细错误日志

## 6. 数据流向

```
浏览器 → 前端服务器(3003) → 后端API服务器(8000)
       ↑                    ↑
   静态文件服务          API代理/处理
```

## 7. 安全考虑

- 项目名称进行URL编码处理
- 文件上传类型和大小验证
- 请求头中的项目信息验证
- 错误信息不暴露敏感数据

## 8. 性能优化

- 使用EventSource进行实时数据流
- 任务轮询机制避免长时间阻塞
- 本地存储缓存项目信息
- 分页加载聊天历史记录

---

**注意**: 本文档基于当前代码版本生成，API接口可能随版本更新而变化。建议定期更新此文档以保持同步。