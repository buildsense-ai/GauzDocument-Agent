const express = require('express');
const path = require('path');
const multer = require('multer');
const fs = require('fs');
const { createProxyMiddleware } = require('http-proxy-middleware');

// 🆕 环境配置 - ReactAgent后端地址
const REACT_AGENT_URL = process.env.REACT_AGENT_URL || 'http://localhost:8001';

console.log(`🔗 ReactAgent后端地址: ${REACT_AGENT_URL}`);

const app = express();
const PORT = process.env.PORT || 3003;

// 创建上传目录
const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) {
    fs.mkdirSync(uploadsDir, { recursive: true });
}

// 配置文件上传 - 参考原来的frontend实现
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, uploadsDir);
    },
    filename: function (req, file, cb) {
        // 正确处理UTF-8文件名 - 参考原来的实现
        const originalName = Buffer.from(file.originalname, 'latin1').toString('utf8');
        const timestamp = Date.now();
        const fileExtension = path.extname(originalName);
        const baseName = path.basename(originalName, fileExtension);

        // 清理文件名，防止路径穿越攻击
        const cleanBaseName = baseName.replace(/[<>:"/\\|?*]/g, '_');
        const safeFileName = `${timestamp}_${cleanBaseName}${fileExtension}`;

        console.log(`📄 原始文件名: ${originalName}`);
        console.log(`📄 安全文件名: ${safeFileName}`);

        cb(null, safeFileName);
    }
});

const upload = multer({
    storage: storage,
    limits: {
        fileSize: Infinity // 移除文件大小限制
    },
    fileFilter: (req, file, cb) => {
        // 接受常见文档格式
        const allowedTypes = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'application/json',
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'image/jpeg',
            'image/png',
            'image/gif'
        ];

        if (allowedTypes.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error(`文件类型 ${file.mimetype} 不被允许`), false);
        }
    }
});

// 解析JSON请求体
app.use(express.json({ limit: '50mb' }));

// 静态文件服务
app.use(express.static(__dirname));

// 文件上传API - 转发到后端MinIO服务
app.post('/api/upload', upload.single('file'), async (req, res) => {
    try {
        if (!req.file) {
            throw new Error('No file uploaded');
        }

        const file = req.file;

        // 正确处理UTF-8文件名
        const originalName = Buffer.from(file.originalname, 'latin1').toString('utf8');
        const localFilePath = file.path;

        // 🆕 提取项目信息 - 优先从请求头获取，然后从body获取
        const projectId = req.headers['x-project-id'];
        const projectName = req.headers['x-project-name'] ? decodeURIComponent(req.headers['x-project-name']) : null;

        console.log(`📁 接收文件上传: ${originalName} (${file.size} bytes)`);
        console.log(`🏗️ 项目信息: ID=${projectId}, Name=${projectName}`);

        // 🚀 修复：使用axios代替fetch来正确处理multipart/form-data
        const axios = require('axios');
        const FormData = require('form-data');
        const fs = require('fs');

        // 创建新的FormData，包含文件和项目信息
        const formData = new FormData();
        formData.append('file', fs.createReadStream(localFilePath), {
            filename: originalName,
            contentType: file.mimetype
        });

        console.log(`🌐 转发文件上传到后端MinIO API...`);

        // 使用axios转发到后端MinIO API
        const backendResponse = await axios.post('http://localhost:8001/api/upload', formData, {
            headers: {
                // 转发项目信息到后端
                ...(projectId && { 'X-Project-ID': projectId }),
                ...(projectName && { 'X-Project-Name': encodeURIComponent(projectName) }),
                // 让form-data库自动设置正确的Content-Type
                ...formData.getHeaders()
            },
            maxContentLength: Infinity,
            maxBodyLength: Infinity,
            timeout: 30000  // 30秒超时
        });

        console.log(`📡 后端MinIO API响应状态: ${backendResponse.status}`);
        console.log(`✅ 后端MinIO上传成功:`, backendResponse.data);

        // 🧹 清理本地临时文件
        try {
            fs.unlinkSync(localFilePath);
            console.log(`🧹 已清理本地临时文件: ${localFilePath}`);
        } catch (cleanupError) {
            console.warn(`⚠️ 清理临时文件失败: ${cleanupError.message}`);
        }

        // 返回后端的响应，但添加一些前端特有的信息
        const responseData = {
            ...backendResponse.data,
            // 保持与原前端API兼容的字段
            localPath: null, // 不再保存到本地
            fileName: originalName,
            fileSize: file.size,
            mimetype: file.mimetype,
            // 标记为已转发到MinIO
            uploadedToMinio: true,
            forwardedToBackend: true
        };

        res.json(responseData);

    } catch (error) {
        console.error('❌ 文件上传处理失败:', error);

        // 检查是否是axios错误
        if (error.response) {
            console.error('后端错误响应:', error.response.status, error.response.data);
        }

        // 尝试清理可能的临时文件
        if (req.file && req.file.path) {
            try {
                require('fs').unlinkSync(req.file.path);
            } catch (cleanupError) {
                console.warn('⚠️ 清理失败的上传文件时出错:', cleanupError);
            }
        }

        res.status(500).json({
            success: false,
            error: error.message,
            message: '文件上传失败',
            details: error.response?.data || null
        });
    }
});

// 聊天API - 参考原来的frontend实现
app.post('/api/chat', async (req, res) => {
    try {
        const { message, files = [], project } = req.body;

        if (!message || typeof message !== 'string') {
            throw new Error('Message is required');
        }

        // 🆕 提取请求头中的项目信息并解码中文字符
        const projectId = req.headers['x-project-id'];
        const projectName = req.headers['x-project-name'] ? decodeURIComponent(req.headers['x-project-name']) : null;

        console.log(`💬 Web API: 处理聊天消息: "${message}"`);
        console.log('🏗️ 接收到项目信息:', {
            fromHeaders: { projectId, projectName },
            fromBody: project
        });

        if (files && files.length > 0) {
            console.log(`📎 包含 ${files.length} 个上传文件:`, files.map(f => f.name || f.originalName || 'unnamed'));
            console.log('📋 文件详细信息:', files);
        }

        // 处理文件路径，优先使用本地路径 - 参考原来的实现
        let processedFiles = files || [];
        if (processedFiles.length > 0) {
            processedFiles = processedFiles.map(file => {
                // 优先使用reactAgentPath，然后是localPath
                let filePath = file.reactAgentPath || file.localPath || file.filePath;

                // 确保路径是绝对路径
                if (filePath && !path.isAbsolute(filePath)) {
                    filePath = path.resolve(uploadsDir, filePath);
                }

                console.log(`📄 处理文件路径: ${file.name || file.originalName || 'unnamed'} -> ${filePath}`);

                return {
                    name: file.name || file.originalName || 'unnamed',
                    path: filePath,
                    type: file.mimetype || file.type,
                    // 确保ReAct Agent能够识别的路径格式
                    reactAgentPath: filePath
                };
            });
        }

        // 🆕 构建发送给ReactAgent的数据，包含项目上下文
        const requestData = {
            problem: message,
            files: processedFiles,
            // 🆕 添加项目上下文信息
            project_context: {
                project_id: projectId,
                project_name: projectName,
                description: projectId ? `当前工作项目: ${projectName} (ID: ${projectId})` : null
            }
        };

        console.log('发送到ReactAgent:', requestData);

        // 直接调用ReactAgent后端的/react_solve端点，并转发项目信息
        const response = await fetch('http://localhost:8001/react_solve', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // 🆕 转发项目ID到ReactAgent请求头，对项目名称进行编码
                ...(projectId && { 'X-Project-ID': projectId }),
                ...(projectName && { 'X-Project-Name': encodeURIComponent(projectName) })
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('ReactAgent错误响应:', errorText);
            throw new Error(`ReactAgent请求失败: ${response.status}`);
        }

        const reactResult = await response.json();

        if (reactResult.isError) {
            throw new Error(reactResult.content[0]?.text || 'ReactAgent处理失败');
        }

        // 提取响应文本 - 参考原来的实现
        const responseText = reactResult.content[0]?.text || '没有响应内容';

        // 🆕 提取思考过程
        const thinkingProcess = reactResult.thinking_process || [];
        const totalIterations = reactResult.total_iterations || 1;

        // 模拟原有的result结构以保持兼容性
        const result = {
            response: responseText,
            totalIterations: totalIterations,
            thinkingProcess: thinkingProcess
        };

        let responseData = {
            success: true,
            response: result.response,
            iterations: result.totalIterations,
            thinking_process: result.thinkingProcess  // 🆕 添加思考过程
        };

        res.json(responseData);

    } catch (error) {
        console.error('❌ 聊天错误:', error);
        res.status(500).json({
            success: false,
            error: '聊天请求失败: ' + error.message
        });
    }
});

// 🌊 流式聊天API - 代理到ReactAgent后端
app.post('/api/start_stream', async (req, res) => {
    try {
        const { problem, files = [], project_context } = req.body;

        // 🆕 提取请求头中的项目信息并解码中文字符
        const projectId = req.headers['x-project-id'];
        const projectName = req.headers['x-project-name'] ? decodeURIComponent(req.headers['x-project-name']) : null;

        console.log(`🌊 Web API: 启动流式会话: "${problem}"`);
        console.log('🏗️ 接收到项目信息:', {
            fromHeaders: { projectId, projectName },
            fromBody: project_context
        });

        // 🆕 构建发送给ReactAgent的数据，包含项目上下文
        const requestData = {
            problem: problem,
            files: files,
            // 🆕 添加项目上下文信息
            project_context: {
                project_id: projectId,
                project_name: projectName,
                description: projectId ? `当前工作项目: ${projectName} (ID: ${projectId})` : null,
                ...project_context
            }
        };

        console.log('🌊 转发流式请求到ReactAgent:', requestData);

        // 直接调用ReactAgent后端的/start_stream端点，并转发项目信息
        const response = await fetch('http://localhost:8001/start_stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // 🆕 转发项目ID到ReactAgent请求头，对项目名称进行编码
                ...(projectId && { 'X-Project-ID': projectId }),
                ...(projectName && { 'X-Project-Name': encodeURIComponent(projectName) })
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('ReactAgent流式请求错误响应:', errorText);
            throw new Error(`ReactAgent流式请求失败: ${response.status}`);
        }

        const reactResult = await response.json();
        console.log('🌊 流式会话创建成功:', reactResult.session_id);

        res.json(reactResult);

    } catch (error) {
        console.error('❌ 流式会话启动错误:', error);
        res.status(500).json({
            success: false,
            error: '启动流式会话失败: ' + error.message
        });
    }
});

// 🌊 流式思考SSE代理 - 使用http-proxy-middleware
app.use('/api/stream', createProxyMiddleware({
    target: 'http://localhost:8001',
    changeOrigin: true,
    pathRewrite: {
        '^/api/stream': '/stream'
    },
    onError: (err, req, res) => {
        console.error('❌ SSE代理错误:', err);
        res.status(500).json({
            success: false,
            error: 'SSE连接失败: ' + err.message
        });
    },
    onProxyReq: (proxyReq, req, res) => {
        console.log('🌊 SSE代理请求:', req.url);
    },
    onProxyRes: (proxyRes, req, res) => {
        // 确保SSE响应头正确设置
        if (req.url.includes('/thoughts/')) {
            console.log('🌊 设置SSE响应头');
            proxyRes.headers['content-type'] = 'text/event-stream';
            proxyRes.headers['cache-control'] = 'no-cache';
            proxyRes.headers['connection'] = 'keep-alive';
            proxyRes.headers['access-control-allow-origin'] = '*';
            proxyRes.headers['access-control-allow-headers'] = '*';
        }
    }
}));

// 状态检查API - 直接转发到ReactAgent 服务器
app.get('/api/status', async (req, res) => {
    try {
        const response = await fetch('http://localhost:8001/health');
        if (!response.ok) {
            throw new Error(`ReactAgent服务器不可用: ${response.status}`);
        }

        const data = await response.json();
        res.json({
            success: true,
            status: {
                reactAgentMcp: data.status === 'healthy',
                connected: data.react_agent_ready,
                tools: data.tools_count,
                uptime: process.uptime()
            }
        });
    } catch (error) {
        console.error('状态检查错误:', error);
        res.status(500).json({
            success: false,
            error: error.message || '无法连接到ReactAgent MCP服务器'
        });
    }
});

// 任务状态查询API - 代理到文档生成服务
app.get('/api/tasks/:task_id', async (req, res) => {
    try {
        const taskId = req.params.task_id;
        console.log(`📋 查询任务状态: ${taskId}`);

        // 转发到文档生成服务的 GET /tasks/{task_id} 接口
        const response = await fetch(`http://43.139.19.144:8002/tasks/${taskId}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            // 根据不同的HTTP状态码返回相应的错误
            if (response.status === 404) {
                console.log(`📋 任务${taskId}不存在 (404)`);
                return res.status(404).json({
                    success: false,
                    error: `任务 ${taskId} 不存在或已过期`,
                    task_id: taskId,
                    status: 'not_found'
                });
            } else if (response.status === 500) {
                console.error(`❌ 文档生成服务内部错误 (500)`);
                return res.status(500).json({
                    success: false,
                    error: '文档生成服务暂时不可用',
                    task_id: taskId,
                    status: 'service_error'
                });
            } else {
                console.error(`❌ 任务状态查询失败: ${response.status}`);
                return res.status(response.status).json({
                    success: false,
                    error: `任务状态查询失败: ${response.status}`,
                    task_id: taskId,
                    status: 'query_error'
                });
            }
        }

        const taskData = await response.json();
        console.log(`✅ 任务状态查询成功:`, taskData);

        // 返回标准化的响应格式
        res.json({
            success: true,
            task_id: taskData.task_id,
            status: taskData.status,
            progress: taskData.progress,
            created_at: taskData.created_at,
            updated_at: taskData.updated_at,
            request: taskData.request,
            result: taskData.result,
            error: taskData.error
        });

    } catch (error) {
        console.error('任务状态查询异常:', error);
        res.status(500).json({
            success: false,
            error: error.message || '无法查询任务状态',
            status: 'exception_error'
        });
    }
});

// 工具列表API
app.get('/api/tools', async (req, res) => {
    try {
        const response = await fetch('http://localhost:8001/tools');
        if (!response.ok) {
            throw new Error(`获取工具列表失败: ${response.status}`);
        }

        const data = await response.json();
        res.json({
            success: true,
            tools: data.tools || []
        });
    } catch (error) {
        console.error('获取工具列表错误:', error);
        res.status(500).json({
            success: false,
            error: error.message || '无法获取工具列表'
        });
    }
});

// 🆕 项目管理API代理
app.get('/api/projects', async (req, res) => {
    try {
        console.log('📋 代理项目列表请求');
        const response = await fetch('http://localhost:8001/api/projects');

        if (!response.ok) {
            throw new Error(`获取项目列表失败: ${response.status}`);
        }

        const data = await response.json();
        console.log(`✅ 成功获取 ${data.projects?.length || 0} 个项目`);
        res.json(data);
    } catch (error) {
        console.error('❌ 获取项目列表错误:', error);
        res.status(500).json({
            success: false,
            error: error.message || '无法获取项目列表'
        });
    }
});

app.post('/api/projects', async (req, res) => {
    try {
        console.log('📋 代理创建项目请求:', req.body);
        const response = await fetch('http://localhost:8001/api/projects', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(req.body)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`创建项目失败: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        console.log(`✅ 成功创建项目: ${req.body.name}`);
        res.json(data);
    } catch (error) {
        console.error('❌ 创建项目错误:', error);
        res.status(500).json({
            success: false,
            error: error.message || '无法创建项目'
        });
    }
});

app.get('/api/projects/:identifier/summary', async (req, res) => {
    try {
        const { identifier } = req.params;
        const { by_name } = req.query;
        console.log(`📋 代理项目概要请求: ${identifier} (by_name: ${by_name})`);

        const url = `http://localhost:8001/api/projects/${encodeURIComponent(identifier)}/summary?by_name=${by_name || 'false'}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`获取项目概要失败: ${response.status}`);
        }

        const data = await response.json();
        res.json(data);
    } catch (error) {
        console.error('❌ 获取项目概要错误:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

app.get('/api/projects/:identifier/current-session', async (req, res) => {
    try {
        const { identifier } = req.params;
        const { by_name, limit } = req.query;
        console.log(`📋 代理当前会话请求: ${identifier} (by_name: ${by_name})`);

        const url = `http://localhost:8001/api/projects/${encodeURIComponent(identifier)}/current-session?by_name=${by_name || 'false'}&limit=${limit || '20'}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`获取当前会话失败: ${response.status}`);
        }

        const data = await response.json();
        res.json(data);
    } catch (error) {
        console.error('❌ 获取当前会话错误:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// 🆕 保存/更新消息到数据库API
app.post('/api/projects/:identifier/messages', async (req, res) => {
    try {
        const { identifier } = req.params;
        const { session_id, role, content, extra_data, by_name } = req.body;

        console.log(`💾 代理保存消息请求: 项目=${identifier}, 角色=${role}, 内容长度=${content?.length || 0}`);

        // 构建后端API URL - 使用适当的项目标识符
        const baseUrl = by_name ?
            `http://localhost:8001/api/projects/by-name/${encodeURIComponent(identifier)}/messages` :
            `http://localhost:8001/api/projects/${encodeURIComponent(identifier)}/messages`;

        const response = await fetch(baseUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id,
                role,
                content,
                extra_data
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`保存消息失败: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        console.log(`✅ 消息保存成功: 消息ID=${data.message_id || 'unknown'}`);

        res.json({
            success: true,
            message: '消息保存成功',
            data
        });

    } catch (error) {
        console.error('❌ 保存消息错误:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// 🆕 删除项目API代理
app.delete('/api/projects/:identifier', async (req, res) => {
    try {
        const { identifier } = req.params;
        const { by_name } = req.query;
        console.log(`🗑️ 代理删除项目请求: ${identifier} (by_name: ${by_name})`);

        const url = `http://localhost:8001/api/projects/${encodeURIComponent(identifier)}?by_name=${by_name || 'false'}`;
        const response = await fetch(url, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`删除项目失败: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        console.log(`✅ 成功删除项目: ${identifier}`);
        res.json(data);
    } catch (error) {
        console.error('❌ 删除项目错误:', error);
        res.status(500).json({
            success: false,
            error: error.message || '无法删除项目'
        });
    }
});

// 🆕 获取项目文件列表的API代理
app.get('/api/projects/:identifier/files', async (req, res) => {
    try {
        const { identifier } = req.params;
        const { by_name } = req.query;

        const url = `http://localhost:8001/api/projects/${encodeURIComponent(identifier)}/files?by_name=${by_name || 'false'}`;
        console.log(`🔗 代理文件列表请求到后端: ${url}`);

        const response = await fetch(url);

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`获取文件列表失败: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        console.log(`✅ 成功获取项目文件列表: ${data.total || 0}个文件`);
        res.json(data);
    } catch (error) {
        console.error('❌ 获取文件列表错误:', error);
        res.status(500).json({
            success: false,
            files: [],
            total: 0,
            error: error.message || '无法获取文件列表'
        });
    }
});

// 默认路由 - 项目选择页面（入口）
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'project_selector.html'));
});

// 对话页面路由
app.get('/chat', (req, res) => {
    res.sendFile(path.join(__dirname, 'ai_chat_interface.html'));
});

// 兼容性路由 - 直接访问对话页面
app.get('/ai_chat_interface.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'ai_chat_interface.html'));
});

// 测试页面路由
app.get('/test', (req, res) => {
    res.sendFile(path.join(__dirname, 'test_frontend.html'));
});

// 启动服务器
app.listen(PORT, () => {
    console.log('\n' + '='.repeat(60));
    console.log('🚀 工程AI助手 - 项目化工作模式已启动!');
    console.log('='.repeat(60));
    console.log(`🏠 项目选择页面: http://localhost:${PORT}/`);
    console.log(`💬 对话页面: http://localhost:${PORT}/chat`);
    console.log(`🔗 后端服务: ReactAgent MCP服务器 (端口 8000)`);
    console.log('='.repeat(60));
    console.log('📋 使用流程:');
    console.log('   1. 访问首页选择项目');
    console.log('   2. 自动跳转到项目对话页面');
    console.log('   3. 享受项目级别的知识库隔离');
    console.log('='.repeat(60));
    console.log('💡 新特性: 项目级别文档管理和知识库隔离!');
    console.log('='.repeat(60));
    console.log('');
});

// 优雅关闭
process.on('SIGINT', () => {
    console.log('\n🛑 正在关闭服务器...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('\n🛑 正在关闭服务器...');
    process.exit(0);
}); 