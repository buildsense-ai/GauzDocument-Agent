# AI长文生成代理 (AI Long-Form Document Generation Agent)

本项目是一个功能完备的、由AI驱动的自动化长文生成系统。其核心能力是接收一个简单的写作请求，然后通过一系列自主的规划、资料检索、内容创作和迭代优化，最终生成一篇结构完整、内容详实的深度报告，并将其同步保存为`.docx`格式和上传到云端。

---

## 核心特性

- **🤖 自主规划与大纲生成**: AI能够理解用户需求，自主生成一份逻辑清晰、结构化的文档大纲。
- **🧠 知识检索与整合**: 在大纲构建和内容创作的多个阶段，系统会主动调用外部向量数据库，获取精准的背景知识来丰富内容，确保事实准确性。
- **🔄 迭代式自我评审与优化**: 系统内置了“AI编辑”角色，会对生成的大纲进行多轮批判性评审和自我修正，直到大纲足够完善。
- **✍️ 自动化内容创作**: 系统能够根据最终确定的多层级大纲，逐章、逐节地生成连贯、流畅的详细内容。
- **📄 多格式产出**: 任务成功后，会自动生成一份包含所有过程数据的`.json`存档文件，以及一份排版好的`.docx`文档。
- **☁️ 云端同步**: 生成的`.docx`文档会自动上传到指定的MinIO云存储，并返回一个可公开访问的URL。
- **🛡️ 健壮的容错与状态管理**: 整个流程由状态机驱动，每一步的进度都被实时保存。即使中途失败，任务也能从断点处恢复，避免重复工作和API调用。

---

## 项目工作流

本项目的工作流程被设计为一个精密的状态机，确保任务能够稳定、有序地执行。


[用户输入] -> [1. 准备阶段] -> [2. 生成初始大纲] -> [3. 大纲精炼循环] -> [4. 逐章内容生成] -> [5. 整合与输出] -> [任务完成]
|               |                   |                  |                  |
|               |                   |                  |                  |--> 生成.docx并上传MinIO
|               |                   |                  |
|               |                   |                  |--> 调用向量数据库 & DeepSeek
|               |                   |
|               |                   |--> 调用向量数据库 & DeepSeek (循环)
|               |
|               |--> 调用 DeepSeek API
|
|--> 调用 DeepSeek API, 提炼创作指令和项目主题


---

## 项目文件结构

项目代码经过精心解耦，被拆分为多个职责单一的模块：

- **`main.py`**: **项目主入口**。负责接收初始请求，启动生成任务，并演示如何轮询最终的任务状态。
- **`generator.py`**: **核心业务逻辑**。包含了驱动整个流程的状态机（`LongDocumentGenerator`类）和负责文件读写的状态管理（`TaskState`类）。
- **`services.py`**: **外部服务接口**。封装了所有与外部世界的交互，例如对DeepSeek AI模型和向量数据库API的调用。
- **`cloud_upload.py`**: **云上传模块**。封装了与MinIO云存储交互的逻辑，负责上传文件。
- **`config.py`**: **全局配置文件**。集中管理所有可配置的参数，如API密钥、服务器地址、存储桶名称等。

---

## API接口说明

本系统主要依赖以下两个外部API：

### 1. 向量数据库 (Vector Database)

- **功能**: 用于根据关键词检索相关的知识片段。
- **端点**: `GET http://43.139.19.144:3000/search-drawings`
- **参数**:
    - `query` (string, 必需): 查询的关键词，例如“1号住宅楼 结构设计理念”。
    - `top_k` (integer, 必需): 希望返回的结果数量。
- **响应**: 一个JSON对象，系统会从中提取`results`数组里的`content`字段。

### 2. DeepSeek AI

- **功能**: 作为系统的“大脑”，负责生成大纲、评审、整合知识和撰写内容。
- **端点**: `https://api.deepseek.com/v1`
- **交互方式**: 通过`openai`官方库进行调用，详见`services.py`。

---

## 配置项说明 (`config.py`)

所有需要您根据自己环境进行修改的配置都在此文件中。

| 变量名 | 说明 | 示例 |
| :--- | :--- | :--- |
| `TASKS_DIR` | 用于存放任务状态文件(.json)和输出文档(.docx)的本地目录。 | `"tasks"` |
| `DEEPSEEK_API_KEY` | 您的DeepSeek API密钥。**强烈建议**通过环境变量设置。 | `os.getenv("DEEPSEEK_API_KEY")` |
| `DEEPSEEK_API_BASE` | DeepSeek API的服务器地址。 | `"https://api.deepseek.com/v1"` |
| `AI_MODEL_NAME` | 使用的DeepSeek模型标识符。 | `"deepseek-chat"` |
| `MAX_REFINEMENT_CYCLES` | 大纲精炼步骤的最大循环次数，防止无限循环。 | `3` |
| `SEARCH_API_BASE` | 向量数据库的API根地址。 | `"http://43.139.19.144:3000"` |
| `SEARCH_API_TOP_K` | 每次查询向量数据库时默认返回的结果数量。 | `5` |
| `MINIO_ENDPOINT` | 您的MinIO服务器地址和端口。 | `"43.139.19.144:9000"` |
| `MINIO_ACCESS_KEY` | MinIO的访问密钥 (用户名)。 | `"minioadmin"` |
| `MINIO_SECRET_KEY` | MinIO的秘密密钥 (密码)。 | `"minioadmin"` |
| `MINIO_BUCKET_NAME` | 用于存放上传文档的MinIO存储桶名称。 | `"docs"` |
| `MINIO_USE_SECURE` | 是否使用HTTPS连接MinIO。 | `False` |

---

## 如何运行

1.  **安装依赖库**:
    ```bash
    pip install openai requests python-docx minio
    ```

2.  **设置环境变量**:
    在运行脚本前，必须在您的终端中设置DeepSeek API密钥。
    ```bash
    # 在 Linux 或 macOS
    export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"

    # 在 Windows (CMD)
    set DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
    ```
    请将`sk-xxxxxxxx...`替换为您的真实密钥。

3.  **启动任务**:
    进入项目根目录，直接运行`main.py`文件。
    ```bash
    python main.py
    ```

4.  **查看产出**:
    - **终端日志**: 您会看到任务执行的实时进度。
    - **本地文件**: 任务结束后，在`tasks/`目录下会生成一个`task_[ID].json`和一个`task_[ID].docx`文件。
    - **云端链接**: 在终端的最终输出中，您会看到一个`docxPublicUrl`字段，这就是上传到MinIO后的文件下载链接。
