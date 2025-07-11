// Web Server for MCP Client Frontend
import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { MCPClient } from './MCPClient.js';

import { config } from './config.js';
import fs from 'fs/promises';
import fsSync from 'fs';
import multer from 'multer';
import http from 'http';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Create uploads directory if it doesn't exist
const uploadsDir = path.join(__dirname, 'uploads');
try {
    await fs.access(uploadsDir);
} catch {
    await fs.mkdir(uploadsDir, { recursive: true });
    console.log('📁 Created uploads directory');
}

// Configure multer for memory storage (we'll upload to MinIO)
const upload = multer({
    storage: multer.memoryStorage(),
    limits: {
        fileSize: Infinity // 移除文件大小限制
    },
    fileFilter: function (req, file, cb) {
        // Accept common document formats
        const allowedTypes = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'application/json',
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ];

        if (allowedTypes.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error(`File type ${file.mimetype} not allowed`), false);
        }
    }
});

async function makeHttpRequest(url, options) {
    return new Promise((resolve, reject) => {
        const urlParts = new URL(url);
        const postData = options.body;
        
        const requestOptions = {
            hostname: urlParts.hostname,
            port: urlParts.port,
            path: urlParts.pathname,
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': postData ? Buffer.byteLength(postData) : 0,
                ...options.headers
            },
            timeout: 0 // No timeout
        };

        const req = http.request(requestOptions, (res) => {
            let data = '';
            res.on('data', (chunk) => {
                data += chunk;
            });
            res.on('end', () => {
                resolve({
                    ok: res.statusCode >= 200 && res.statusCode < 300,
                    status: res.statusCode,
                    json: async () => JSON.parse(data),
                    body: {
                        getReader: () => {
                            const chunks = [data];
                            let index = 0;
                            return {
                                read: async () => {
                                    if (index >= chunks.length) {
                                        return { done: true };
                                    }
                                    const chunk = chunks[index++];
                                    return { 
                                        done: false, 
                                        value: new TextEncoder().encode(chunk) 
                                    };
                                }
                            };
                        }
                    }
                });
            });
        });

        req.on('error', (err) => {
            reject(err);
        });

        req.on('timeout', () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });

        if (postData) {
            req.write(postData);
        }
        req.end();
    });
}

async function makeStreamingHttpRequest(url, options) {
    return new Promise((resolve, reject) => {
        const urlParts = new URL(url);
        const postData = options.body;
        
        const requestOptions = {
            hostname: urlParts.hostname,
            port: urlParts.port,
            path: urlParts.pathname,
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': postData ? Buffer.byteLength(postData) : 0,
                ...options.headers
            },
            timeout: 0 // No timeout
        };

        const req = http.request(requestOptions, (res) => {
            resolve({
                ok: res.statusCode >= 200 && res.statusCode < 300,
                status: res.statusCode,
                body: res // Return the response stream directly
            });
        });

        req.on('error', (err) => {
            reject(err);
        });

        req.on('timeout', () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });

        if (postData) {
            req.write(postData);
        }
        req.end();
    });
}

class MCPWebServer {
    constructor() {
        this.app = express();
        this.port = 3000;
        this.mcpClient = null;


        this.setupMiddleware();
        this.setupRoutes();
    }

    setupMiddleware() {
        // 安全头部设置
        this.app.use((req, res, next) => {
            res.setHeader('X-Content-Type-Options', 'nosniff');
            res.setHeader('X-Frame-Options', 'DENY');
            res.setHeader('X-XSS-Protection', '1; mode=block');
            res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
            next();
        });

        // Parse JSON bodies without size limits
        this.app.use(express.json({
            limit: '50mb', // 增大JSON请求体限制以支持大文件元数据
            type: 'application/json'
        }));

        // 简单的限流中间件 (针对配置API)
        const configApiLimiter = new Map();
        this.app.use('/api/servers', (req, res, next) => {
            const ip = req.ip || req.connection.remoteAddress;
            const now = Date.now();
            const windowMs = 60000; // 1分钟
            const maxRequests = 20; // 每分钟最多20个请求

            if (!configApiLimiter.has(ip)) {
                configApiLimiter.set(ip, { count: 1, resetTime: now + windowMs });
                next();
                return;
            }

            const limiter = configApiLimiter.get(ip);
            if (now > limiter.resetTime) {
                limiter.count = 1;
                limiter.resetTime = now + windowMs;
                next();
            } else if (limiter.count >= maxRequests) {
                res.status(429).json({
                    success: false,
                    error: 'Too many requests. Please try again later.'
                });
            } else {
                limiter.count++;
                next();
            }
        });

        // Serve static files from frontend directory
        this.app.use(express.static(path.join(__dirname, './')));

        // CORS for development and deployment (supports cpolar tunnels and cloud)
        this.app.use((req, res, next) => {
            const origin = req.headers.origin;
            const host = req.headers.host;

            // Allow requests from:
            // 1. Same origin (when origin header exists)
            // 2. Direct access (no origin header)
            // 3. Local development
            // 4. Cpolar tunnels (*.cpolar.cn)
            // 5. Cloud deployments
            const allowedOrigins = [
                'http://localhost:3000',
                'http://127.0.0.1:3000',
                ...(host ? [`http://${host}`, `https://${host}`] : [])
            ];

            const isOriginAllowed = !origin || // No origin header (direct access)
                allowedOrigins.includes(origin) || // Explicitly allowed origins
                /^https?:\/\/.*\.cpolar\.(cn|top)$/.test(origin) || // Cpolar tunnels
                /^https?:\/\/.*\.herokuapp\.com$/.test(origin) || // Heroku
                /^https?:\/\/.*\.vercel\.app$/.test(origin) || // Vercel
                /^https?:\/\/.*\.netlify\.app$/.test(origin); // Netlify

            if (isOriginAllowed) {
                res.header('Access-Control-Allow-Origin', origin || '*');
            }

            res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
            res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');

            if (req.method === 'OPTIONS') {
                res.sendStatus(200);
            } else {
                next();
            }
        });
    }

    setupRoutes() {
        // Serve the main page
        this.app.get('/', (req, res) => {
            res.sendFile(path.join(__dirname, 'index.html'));
        });

        // API Routes
        this.app.post('/api/connect', this.handleConnect.bind(this));
        this.app.get('/api/tools', this.handleGetTools.bind(this));
        this.app.get('/api/servers', this.handleGetServers.bind(this));
        this.app.post('/api/servers/:serverName/toggle', this.handleToggleServer.bind(this));

        // Server management routes
        this.app.post('/api/servers', this.handleAddServer.bind(this));
        this.app.put('/api/servers/:serverName', this.handleUpdateServer.bind(this));
        this.app.delete('/api/servers/:serverName', this.handleDeleteServer.bind(this));
        this.app.post('/api/chat', this.handleChat.bind(this));
        this.app.post('/api/chat/stream', this.handleChatStream.bind(this));
        this.app.post('/api/upload', upload.single('file'), this.handleFileUpload.bind(this));
        this.app.get('/api/files/:filename', this.handleFileAccess.bind(this));
        this.app.post('/api/files/convert', this.handleFileConvert.bind(this));
        this.app.get('/api/cpolar/test', this.handleCpolarTest.bind(this));
        this.app.get('/api/status', this.handleStatus.bind(this));

        // Serve uploaded files
        this.app.use('/uploads', express.static(uploadsDir));

        // Error handling
        this.app.use(this.errorHandler.bind(this));
    }

    async handleConnect(req, res) {
        try {
            console.log('🔗 Web API: Connecting to MCP servers...');

            // Initialize MCP client if not already done
            if (!this.mcpClient) {
                this.mcpClient = new MCPClient(config.openRouterApiKey);
                await this.mcpClient.initialize();
            }

            // Get server information
            const servers = this.getServerInfo();

            res.json({
                success: true,
                message: 'Connected to MCP servers',
                servers: servers,
                toolCount: this.mcpClient.allTools.length
            });

        } catch (error) {
            console.error('❌ Connection error:', error);
            res.status(500).json({
                success: false,
                error: 'Failed to connect to MCP servers: ' + error.message
            });
        }
    }

    async handleGetTools(req, res) {
        try {
            if (!this.mcpClient) {
                throw new Error('MCP client not initialized');
            }

            const tools = this.mcpClient.allTools.map(tool => ({
                name: tool.name,
                description: tool.description,
                serverName: tool.serverName,
                enabled: true // All discovered tools are considered enabled
            }));

            res.json({
                success: true,
                tools: tools,
                count: tools.length
            });

        } catch (error) {
            console.error('❌ Get tools error:', error);
            res.status(500).json({
                success: false,
                error: 'Failed to get tools: ' + error.message
            });
        }
    }

    async handleGetServers(req, res) {
        try {
            const configPath = path.join(__dirname, 'mcp-server-config.json');
            const data = await fs.readFile(configPath, 'utf8');
            const servers = JSON.parse(data);
            res.json({ success: true, servers });
        } catch (error) {
            console.error('❌ Get servers error:', error);
            res.status(500).json({
                success: false,
                error: 'Failed to get servers: ' + error.message,
            });
        }
    }

    async handleToggleServer(req, res) {
        try {
            const { serverName } = req.params;
            const { enabled } = req.body;

            console.log(`🔄 Web API: Toggle server ${serverName} to ${enabled ? 'enabled' : 'disabled'}`);

            // Persist the change to the JSON config file
            const configPath = path.join(__dirname, 'mcp-server-config.json');
            const data = await fs.readFile(configPath, 'utf8');
            const servers = JSON.parse(data);

            const serverConfig = servers.find(s => s.name === serverName);
            if (!serverConfig) {
                throw new Error(`Server ${serverName} not found`);
            }

            serverConfig.isOpen = enabled;

            await fs.writeFile(configPath, JSON.stringify(servers, null, 2), 'utf8');
            console.log(`✅ Wrote updated server config to ${configPath}`);

            // Dynamically connect or disconnect the client
            const fullServerConfig = { ...serverConfig, apiKey: this.mcpClient.openRouterApiKey };

            if (enabled) {
                await this.mcpClient.connectToServer(fullServerConfig);
            } else {
                this.mcpClient.disconnectFromServer(serverName);
            }

            res.json({
                success: true,
                message: `Server ${serverName} ${enabled ? 'enabled' : 'disabled'}`,
                toolCount: this.mcpClient.allTools.length
            });

        } catch (error) {
            console.error('❌ Toggle server error:', error);
            res.status(500).json({
                success: false,
                error: 'Failed to toggle server: ' + error.message
            });
        }
    }

    async handleAddServer(req, res) {
        try {
            const { name, type, url, isOpen } = req.body;

            // 严格输入验证和清理
            if (!name || !type || !url) {
                throw new Error('Server name, type, and URL are required');
            }

            // 验证服务器名称格式 (防止注入攻击)
            const nameRegex = /^[a-zA-Z0-9_-]+$/;
            if (!nameRegex.test(name) || name.length > 50) {
                throw new Error('Server name must contain only letters, numbers, underscores, and hyphens (max 50 chars)');
            }

            // 验证服务器类型白名单
            const allowedTypes = ['fastapi-mcp', 'standard'];
            if (!allowedTypes.includes(type)) {
                throw new Error('Invalid server type. Must be "fastapi-mcp" or "standard"');
            }

            // 验证URL格式和协议
            let parsedUrl;
            try {
                parsedUrl = new URL(url);
                if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
                    throw new Error('URL must use HTTP or HTTPS protocol');
                }
                // 防止内网地址攻击 (可选，根据需求调整)
                if (parsedUrl.hostname === 'localhost' || parsedUrl.hostname === '127.0.0.1') {
                    console.warn(`⚠️ Warning: Adding localhost server ${name}`);
                }
            } catch (error) {
                throw new Error('Invalid URL format');
            }

            console.log(`➕ Web API: Adding new server ${name} (${type}) at ${url}`);

            // Load current config
            const configPath = path.join(__dirname, 'mcp-server-config.json');
            const data = await fs.readFile(configPath, 'utf8');
            const servers = JSON.parse(data);

            // Check if server name already exists
            const existingServer = servers.find(s => s.name === name);
            if (existingServer) {
                throw new Error(`Server with name "${name}" already exists`);
            }

            // Create new server config
            const newServer = {
                name: name.trim(),
                type: type.trim(),
                url: url.trim(),
                isOpen: Boolean(isOpen)
            };

            // Add to servers array
            servers.push(newServer);

            // 创建配置文件备份
            const backupPath = configPath + '.backup';
            try {
                await fs.copyFile(configPath, backupPath);
            } catch (backupError) {
                console.warn('⚠️ Failed to create backup:', backupError.message);
            }

            // Save updated config (原子性写入)
            const tempPath = configPath + '.tmp';
            await fs.writeFile(tempPath, JSON.stringify(servers, null, 2), 'utf8');
            await fs.rename(tempPath, configPath);
            console.log(`✅ Added server ${name} to config file`);

            // Try to connect immediately if enabled
            if (newServer.isOpen && this.mcpClient) {
                try {
                    const fullServerConfig = { ...newServer, apiKey: this.mcpClient.openRouterApiKey };
                    await this.mcpClient.connectToServer(fullServerConfig);
                    console.log(`✅ Connected to new server ${name}`);
                } catch (connectError) {
                    console.warn(`⚠️ Added server ${name} but failed to connect:`, connectError.message);
                }
            }

            res.json({
                success: true,
                message: `Server "${name}" added successfully`,
                server: newServer,
                toolCount: this.mcpClient?.allTools?.length || 0
            });

        } catch (error) {
            console.error('❌ Add server error:', error);
            res.status(400).json({
                success: false,
                error: 'Failed to add server: ' + error.message
            });
        }
    }

    async handleUpdateServer(req, res) {
        try {
            const { serverName } = req.params;
            const { type, url, isOpen } = req.body;

            // 验证服务器名称 (防止路径遍历攻击)
            const nameRegex = /^[a-zA-Z0-9_-]+$/;
            if (!nameRegex.test(serverName) || serverName.length > 50) {
                throw new Error('Invalid server name format');
            }

            // Validate required fields
            if (!type || !url) {
                throw new Error('Server type and URL are required');
            }

            // 验证服务器类型白名单
            const allowedTypes = ['fastapi-mcp', 'standard'];
            if (!allowedTypes.includes(type)) {
                throw new Error('Invalid server type. Must be "fastapi-mcp" or "standard"');
            }

            // 验证URL格式和协议
            let parsedUrl;
            try {
                parsedUrl = new URL(url);
                if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
                    throw new Error('URL must use HTTP or HTTPS protocol');
                }
            } catch (error) {
                throw new Error('Invalid URL format');
            }

            console.log(`✏️ Web API: Updating server ${serverName}`);

            // Load current config
            const configPath = path.join(__dirname, 'mcp-server-config.json');
            const data = await fs.readFile(configPath, 'utf8');
            const servers = JSON.parse(data);

            // Find the server to update
            const serverIndex = servers.findIndex(s => s.name === serverName);
            if (serverIndex === -1) {
                throw new Error(`Server "${serverName}" not found`);
            }

            const oldServer = servers[serverIndex];

            // Update server config
            servers[serverIndex] = {
                name: serverName, // Keep the original name
                type: type.trim(),
                url: url.trim(),
                isOpen: Boolean(isOpen)
            };

            // 创建配置文件备份
            const backupPath = configPath + '.backup';
            try {
                await fs.copyFile(configPath, backupPath);
            } catch (backupError) {
                console.warn('⚠️ Failed to create backup:', backupError.message);
            }

            // Save updated config (原子性写入)
            const tempPath = configPath + '.tmp';
            await fs.writeFile(tempPath, JSON.stringify(servers, null, 2), 'utf8');
            await fs.rename(tempPath, configPath);
            console.log(`✅ Updated server ${serverName} in config file`);

            // Handle connection changes if MCP client is available
            if (this.mcpClient) {
                // Disconnect old server
                this.mcpClient.disconnectFromServer(serverName);

                // Connect to updated server if enabled
                if (servers[serverIndex].isOpen) {
                    try {
                        const fullServerConfig = { ...servers[serverIndex], apiKey: this.mcpClient.openRouterApiKey };
                        await this.mcpClient.connectToServer(fullServerConfig);
                        console.log(`✅ Reconnected to updated server ${serverName}`);
                    } catch (connectError) {
                        console.warn(`⚠️ Updated server ${serverName} but failed to connect:`, connectError.message);
                    }
                }
            }

            res.json({
                success: true,
                message: `Server "${serverName}" updated successfully`,
                server: servers[serverIndex],
                toolCount: this.mcpClient?.allTools?.length || 0
            });

        } catch (error) {
            console.error('❌ Update server error:', error);
            res.status(400).json({
                success: false,
                error: 'Failed to update server: ' + error.message
            });
        }
    }

    async handleDeleteServer(req, res) {
        try {
            const { serverName } = req.params;

            // 验证服务器名称 (防止路径遍历攻击)
            const nameRegex = /^[a-zA-Z0-9_-]+$/;
            if (!nameRegex.test(serverName) || serverName.length > 50) {
                throw new Error('Invalid server name format');
            }

            console.log(`🗑️ Web API: Deleting server ${serverName}`);

            // Load current config (带错误处理)
            const configPath = path.join(__dirname, 'mcp-server-config.json');
            let data;
            try {
                data = await fs.readFile(configPath, 'utf8');
            } catch (error) {
                throw new Error('Configuration file not found or inaccessible');
            }

            let servers;
            try {
                servers = JSON.parse(data);
            } catch (error) {
                throw new Error('Invalid configuration file format');
            }

            // Find the server to delete
            const serverIndex = servers.findIndex(s => s.name === serverName);
            if (serverIndex === -1) {
                throw new Error(`Server "${serverName}" not found`);
            }

            // Remove server from array
            const deletedServer = servers.splice(serverIndex, 1)[0];

            // 创建配置文件备份
            const backupPath = configPath + '.backup';
            try {
                await fs.copyFile(configPath, backupPath);
            } catch (backupError) {
                console.warn('⚠️ Failed to create backup:', backupError.message);
            }

            // Save updated config (原子性写入)
            const tempPath = configPath + '.tmp';
            await fs.writeFile(tempPath, JSON.stringify(servers, null, 2), 'utf8');
            await fs.rename(tempPath, configPath);
            console.log(`✅ Deleted server ${serverName} from config file`);

            // Disconnect from server if MCP client is available
            if (this.mcpClient) {
                this.mcpClient.disconnectFromServer(serverName);
                console.log(`🔌 Disconnected from deleted server ${serverName}`);
            }

            res.json({
                success: true,
                message: `Server "${serverName}" deleted successfully`,
                deletedServer: deletedServer,
                toolCount: this.mcpClient?.allTools?.length || 0
            });

        } catch (error) {
            console.error('❌ Delete server error:', error);
            res.status(400).json({
                success: false,
                error: 'Failed to delete server: ' + error.message
            });
        }
    }

    async handleChat(req, res) {
        try {
            const { message, files } = req.body;

            if (!message || typeof message !== 'string') {
                throw new Error('Message is required');
            }

            console.log(`💬 Web API: Processing chat message: "${message}"`);
            if (files && files.length > 0) {
                console.log(`📎 With ${files.length} uploaded files:`, files.map(f => f.name));
            }

            // 处理文件路径，优先使用本地路径
            let processedFiles = files || [];
            if (processedFiles.length > 0) {
                processedFiles = processedFiles.map(file => {
                    // 优先使用reactAgentPath，然后是localPath
                    let filePath = file.reactAgentPath || file.localPath || file.path;
                    
                    // 确保路径是绝对路径
                    if (filePath && !path.isAbsolute(filePath)) {
                        filePath = path.resolve(uploadsDir, filePath);
                    }
                    
                    console.log(`📄 处理文件路径: ${file.name || file.originalName} -> ${filePath}`);
                    
                    return {
                        ...file,
                        path: filePath,
                        // 确保ReAct Agent能够识别的路径格式
                        reactAgentPath: filePath
                    };
                });
            }

            // 直接调用ReactAgent后端的/react_solve端点，传递文件信息
            const reactResponse = await makeHttpRequest('http://localhost:8000/react_solve', {
                method: 'POST',
                body: JSON.stringify({ 
                    problem: message,
                    files: processedFiles
                })
            });
            
            if (!reactResponse.ok) {
                throw new Error(`ReactAgent request failed: ${reactResponse.status}`);
            }

            const reactResult = await reactResponse.json();
            
            if (reactResult.isError) {
                throw new Error(reactResult.content[0]?.text || 'ReactAgent处理失败');
            }

            // 提取响应文本
            const responseText = reactResult.content[0]?.text || '没有响应内容';
            
            // 模拟原有的result结构以保持兼容性
            const result = {
                response: responseText,
                totalIterations: 1
            };

            // Handle local file paths 
            const localPathMatch = result.response.match(/`([^`]*\.(docx|pdf|txt|xlsx|doc))`/i);

            let responseData = {
                success: true,
                response: result.response,
                iterations: result.totalIterations
            };

            // Handle local paths (quoted)
            if (localPathMatch) {
                const filename = localPathMatch[1].split('/').pop();
                responseData.downloadUrl = `${req.protocol}://${req.get('host')}/api/files/${filename}`;
                responseData.filename = filename;
                responseData.message = "Document generated successfully";

                // Update response text to include download link
                responseData.response = result.response.replace(
                    localPathMatch[0],
                    `[Download ${filename}](${responseData.downloadUrl})`
                );
            }

            res.json(responseData);

        } catch (error) {
            console.error('❌ Chat error:', error);
            res.status(500).json({
                success: false,
                error: 'Chat request failed: ' + error.message
            });
        }
    }

    async handleChatStream(req, res) {
        try {
            const { message, files } = req.body;

            if (!message || typeof message !== 'string') {
                throw new Error('Message is required');
            }

            console.log(`💬 Web API: Processing streaming chat message: "${message}"`);
            if (files && files.length > 0) {
                console.log(`📎 With ${files.length} uploaded files:`, files.map(f => f.name));
            }

            // 处理文件路径，优先使用本地路径
            let processedFiles = files || [];
            if (processedFiles.length > 0) {
                processedFiles = processedFiles.map(file => {
                    // 优先使用reactAgentPath，然后是localPath
                    let filePath = file.reactAgentPath || file.localPath || file.path;
                    
                    // 确保路径是绝对路径
                    if (filePath && !path.isAbsolute(filePath)) {
                        filePath = path.resolve(uploadsDir, filePath);
                    }
                    
                    console.log(`📄 处理文件路径: ${file.name || file.originalName} -> ${filePath}`);
                    
                    return {
                        ...file,
                        path: filePath,
                        // 确保ReAct Agent能够识别的路径格式
                        reactAgentPath: filePath
                    };
                });
            }

            // 设置SSE响应头
            res.writeHead(200, {
                'Content-Type': 'text/plain',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            });

            // 调用ReactAgent的流式端点
            console.log('🔄 正在连接到ReactAgent后端流式端点...');
            const reactResponse = await makeStreamingHttpRequest('http://localhost:8000/react_solve_stream', {
                method: 'POST',
                body: JSON.stringify({ 
                    problem: message,
                    files: processedFiles
                })
            });

            if (!reactResponse.ok) {
                console.error(`❌ ReactAgent streaming request failed: ${reactResponse.status}`);
                throw new Error(`ReactAgent streaming request failed: ${reactResponse.status}`);
            }

            console.log('✅ 已连接到ReactAgent后端，开始处理流式响应...');
            
            // 读取流式响应并转发给前端
            const responseStream = reactResponse.body;
            let dataReceived = false;
            
            try {
                let heartbeatInterval;
                
                // 设置心跳，防止连接超时
                heartbeatInterval = setInterval(() => {
                    try {
                        res.write(' '); // 发送空格保持连接活跃
                    } catch (e) {
                        console.log('❌ 心跳写入失败，连接可能已断开');
                        clearInterval(heartbeatInterval);
                    }
                }, 30000); // 每30秒发送一次心跳
                
                responseStream.on('data', (chunk) => {
                    dataReceived = true;
                    const chunkStr = chunk.toString();
                    console.log(`📡 接收到流式数据: ${chunkStr.substring(0, 100)}...`);
                    res.write(chunk);
                });
                
                responseStream.on('end', () => {
                    console.log('✅ 流式响应完成');
                    clearInterval(heartbeatInterval);
                    res.end();
                });
                
                responseStream.on('error', (error) => {
                    console.error('❌ 流式响应错误:', error);
                    clearInterval(heartbeatInterval);
                    if (!dataReceived) {
                        // 如果没有接收到任何数据，发送错误消息
                        const errorData = {
                            type: "error",
                            content: `Stream error: ${error.message}`
                        };
                        res.write(`data: ${JSON.stringify(errorData)}\n\n`);
                    }
                    res.end();
                });
                
            } catch (error) {
                console.error('❌ Stream processing error:', error);
                const errorData = {
                    type: "error",
                    content: `Stream processing error: ${error.message}`
                };
                res.write(`data: ${JSON.stringify(errorData)}\n\n`);
                res.end();
            }

        } catch (error) {
            console.error('❌ Chat stream error:', error);
            
            // 如果还没有发送响应头，发送错误响应
            if (!res.headersSent) {
                res.status(500).json({
                    success: false,
                    error: 'Chat stream request failed: ' + error.message
                });
            } else {
                // 如果已经开始流式响应，发送错误数据
                const errorData = {
                    type: "error",
                    content: 'Chat stream request failed: ' + error.message
                };
                res.write(`data: ${JSON.stringify(errorData)}\n\n`);
                res.end();
            }
        }
    }

    async handleFileUpload(req, res) {
        try {
            if (!req.file) {
                throw new Error('No file uploaded');
            }

            const file = req.file;
            console.log(`📁 Web API: Uploading file to local storage - ${file.originalname} (${file.size} bytes)`);

            // --- Correctly handle UTF-8 filenames ---
            // Multer provides the original name in latin1, we need to convert it back to UTF-8
            const originalName = Buffer.from(file.originalname, 'latin1').toString('utf8');
            
            const timestamp = Date.now();
            const fileExtension = path.extname(originalName);
            const baseName = path.basename(originalName, fileExtension);
            
            // Sanitize filename to prevent path traversal and other attacks
            const cleanBaseName = baseName.replace(/[<>:"/\\|?*]/g, '_');
            const safeFileName = `${timestamp}_${cleanBaseName}${fileExtension}`;
            
            const localFilePath = path.join(uploadsDir, safeFileName);
            await fs.writeFile(localFilePath, file.buffer);
            
            console.log(`📄 Decoded Original Filename: ${originalName}`);
            console.log(`📄 Sanitized Safe Filename: ${safeFileName}`);
            console.log(`📄 Saved to Local Path: ${localFilePath}`);

            res.json({
                success: true,
                message: 'File uploaded to local storage successfully',
                filePath: localFilePath,
                localPath: localFilePath,
                originalName: originalName, // Send the correctly decoded name back
                size: file.size,
                mimetype: file.mimetype,
                fileName: safeFileName,
                reactAgentPath: localFilePath
            });

        } catch (error) {
            console.error('❌ File upload error:', error);
            res.status(500).json({
                success: false,
                error: 'File upload failed: ' + error.message
            });
        }
    }

    async handleFileAccess(req, res) {
        try {
            const { filename } = req.params;

            // Fallback to local storage for backward compatibility
            const filePath = path.join(uploadsDir, filename);
            await fs.access(filePath);
            res.sendFile(path.resolve(filePath));

        } catch (error) {
            console.error('❌ File access error:', error);
            res.status(404).json({
                success: false,
                error: 'File not found: ' + error.message
            });
        }
    }

    async handleFileConvert(req, res) {
        try {
            // Implementation of file conversion logic
            res.status(501).json({
                success: false,
                error: 'File conversion logic not implemented'
            });
        } catch (error) {
            console.error('❌ File conversion error:', error);
            res.status(500).json({
                success: false,
                error: 'Failed to convert file: ' + error.message
            });
        }
    }



    async handleCpolarTest(req, res) {
        try {
            console.log('🌐 Web API: Testing server connectivity...');

            // 简化的服务器连接测试
            const configPath = path.join(__dirname, 'mcp-server-config.json');
            const data = await fs.readFile(configPath, 'utf8');
            const servers = JSON.parse(data);

            const results = [];

            for (const server of servers) {
                if (!server.isOpen) {
                    results.push({
                        name: server.name,
                        url: server.url,
                        status: 'disabled'
                    });
                    continue;
                }

                try {
                    const baseUrl = server.url.replace('/mcp', '');
                    const healthUrl = `${baseUrl}/health`;

                    const response = await fetch(healthUrl, {
                        method: 'GET',
                        timeout: 5000
                    });

                    if (response.ok) {
                        results.push({
                            name: server.name,
                            url: server.url,
                            status: 'healthy'
                        });
                    } else {
                        results.push({
                            name: server.name,
                            url: server.url,
                            status: 'error',
                            error: `HTTP ${response.status}`
                        });
                    }
                } catch (error) {
                    results.push({
                        name: server.name,
                        url: server.url,
                        status: 'unreachable',
                        error: error.message
                    });
                }
            }

            res.json({
                success: true,
                results: results,
                summary: {
                    total: results.length,
                    healthy: results.filter(r => r.status === 'healthy').length,
                    enabled: results.filter(r => r.status !== 'disabled').length
                }
            });

        } catch (error) {
            console.error('❌ Server connectivity test error:', error);
            res.status(500).json({
                success: false,
                error: 'Server connectivity test failed: ' + error.message
            });
        }
    }

    async handleStatus(req, res) {
        try {
            const status = {
                mcpClient: !!this.mcpClient,
                connected: this.mcpClient ? this.mcpClient.clients.size > 0 : false,
                servers: this.getServerInfo(),
                tools: this.mcpClient ? this.mcpClient.allTools.length : 0,
                uptime: process.uptime()
            };

            res.json({
                success: true,
                status: status
            });

        } catch (error) {
            console.error('❌ Status error:', error);
            res.status(500).json({
                success: false,
                error: 'Failed to get status: ' + error.message
            });
        }
    }







    getServerInfo() {
        // Read directly from the JSON config file to ensure fresh data
        try {
            const configPath = path.join(__dirname, 'mcp-server-config.json');
            // Use synchronous fs with proper ES module syntax
            const data = fsSync.readFileSync(configPath, 'utf8');
            const mcpServers = JSON.parse(data);
            return mcpServers.map(server => ({
                name: server.name,
                url: server.url,
                type: server.type,
                isOpen: server.isOpen || false,
                connected: this.mcpClient ? this.mcpClient.clients.has(server.name) : false
            }));
        } catch (error) {
            console.error('Failed to load server configs:', error);
            return [];
        }
    }

    errorHandler(error, req, res, next) {
        console.error('❌ Web server error:', error);
        res.status(500).json({
            success: false,
            error: 'Internal server error'
        });
    }

    async start() {
        try {
            // Initialize MCP client on startup
            console.log('🚀 Initializing MCP Client...');
            this.mcpClient = new MCPClient(config.openRouterApiKey);
            await this.mcpClient.initialize();
            console.log('✅ MCP Client initialized');

            // Start the web server
            this.app.listen(this.port, () => {
                console.log('\n' + '='.repeat(60));
                console.log('🌐 MCP Client Web Interface Started!');
                console.log('='.repeat(60));
                console.log(`📱 Frontend: http://localhost:${this.port}`);
                console.log(`🔧 API Base: http://localhost:${this.port}/api`);
                console.log(`🛠️  Tools Available: ${this.mcpClient.allTools.length}`);
                console.log(`🔗 Servers Connected: ${this.mcpClient.clients.size}`);
                console.log('='.repeat(60));
                console.log('💡 Open your browser and start chatting with AI!');
                console.log('💡 Use the side panel to manage MCP tools and servers.');
            });

        } catch (error) {
            console.error('❌ Failed to start web server:', error);
            process.exit(1);
        }
    }

    async stop() {
        console.log('🛑 Shutting down MCP Web Server...');

        if (this.mcpClient) {
            await this.mcpClient.close();
        }

        process.exit(0);
    }
}

// Create and start the server
const server = new MCPWebServer();

// Handle graceful shutdown
process.on('SIGINT', () => server.stop());
process.on('SIGTERM', () => server.stop());

// Start the server
server.start();

export { MCPWebServer };