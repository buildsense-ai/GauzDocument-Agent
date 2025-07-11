# GauzDocument-Agent

AI智能文档生成和处理系统

## 🚀 功能特性

### 核心功能
- **AI思考过程显示**: 实时显示AI的推理过程，包含Thought、Action和Observation
- **项目级别隔离**: 支持基于项目的知识库隔离和管理
- **智能文档生成**: 基于RAG技术的智能长文档生成
- **PDF解析处理**: 高级PDF解析，支持文本、图片、表格提取
- **多模态检索**: 支持文本、图片、表格的语义检索

### 系统架构
- **后端**: FastAPI + ReAct Agent + DeepSeek AI
- **前端**: 现代化Web界面，支持项目选择和对话
- **存储**: ChromaDB向量数据库 + MinIO对象存储
- **处理**: 智能PDF解析 + VLM图片描述

## 📦 安装和配置

### 环境要求
- Python 3.12
- Node.js 16+
- 足够的磁盘空间用于文档存储

### 快速启动

1. **安装Python依赖**
```bash
pip install -r requirements.txt
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，添加API密钥
```

3. **启动后端服务**
```bash
cd server
python main.py
```

4. **启动前端服务**
```bash
cd ui_iterations-main
node start_direct_frontend.js
```

5. **访问应用**
```
前端: http://localhost:3000
后端API: http://localhost:8000
```

## 🔧 配置说明

### 必需的API密钥
- `DEEPSEEK_API_KEY`: DeepSeek AI模型API密钥
- `OPENROUTER_API_KEY`: OpenRouter API密钥（可选）

### 存储配置
- ChromaDB: 本地向量数据库
- MinIO: 对象存储服务（已预配置）

## 📚 使用指南

### 项目隔离功能
1. 访问项目选择页面
2. 选择或创建项目
3. 上传项目相关文档
4. 系统自动进行项目级别的知识库隔离

### AI思考过程
- 后端Terminal显示完整的推理过程
- 前端显示精简版的思考过程和最终答案
- 支持多轮对话和复杂推理

### 文档生成
- 支持基于已有文档的智能生成
- 自动图片检索和插入
- 多格式输出（Markdown、DOCX）

## 🛠️ 开发

### 项目结构
```
├── src/                    # 核心Python代码
│   ├── enhanced_react_agent.py    # ReAct智能体
│   ├── pdf_embedding_service.py   # PDF向量化服务
│   ├── rag_tool_chroma.py         # RAG检索工具
│   └── ...
├── server/                 # FastAPI后端
├── frontend/              # 基础前端
├── ui_iterations-main/    # 主要前端界面
└── requirements.txt       # Python依赖
```

### 主要组件
- **EnhancedReActAgent**: 增强版ReAct智能体，支持思考过程收集
- **PDFEmbeddingService**: PDF文档向量化和项目隔离
- **RAGTool**: 智能检索工具，支持文本、图片、表格搜索

## 🔬 技术特色

### AI思考过程显示
- 非流式输出，完整显示推理链
- 前端精简显示，只展示核心思考内容
- 支持Markdown格式的美观渲染

### 项目隔离机制
- 基于文件名的智能项目名称提取
- 严格的项目级别知识库隔离
- 智能项目识别和自动匹配

### 多模态处理
- PDF文档智能解析
- VLM支持的图片描述生成
- 表格内容的结构化处理

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📞 支持

如有问题，请通过GitHub Issues联系我们。 