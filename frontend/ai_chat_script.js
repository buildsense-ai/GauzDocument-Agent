// 全局变量
let chatStarted = false;
let currentChatId = null;
let chatHistory = [];
let currentFiles = [];
let currentProject = null; // 当前选中的项目信息
let isUploading = false; // 是否正在上传文件到MinIO
let userSettings = {
    theme: 'light',
    showThinking: true,
    autoSave: true  // 默认开启自动保存
};

// API基础URL - 指向当前前端服务器（会代理到后端）
const API_BASE = '/api';

// 通用API请求函数，自动添加项目ID到请求头
async function apiRequest(url, options = {}) {
    const headers = {
        ...options.headers
    };

    // 如果body不是FormData，添加Content-Type
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    // 如果有当前项目，添加项目ID到请求头
    if (currentProject && currentProject.id) {
        headers['X-Project-ID'] = currentProject.id;
        headers['X-Project-Name'] = encodeURIComponent(currentProject.name); // 编码中文字符
        console.log('📤 API请求添加项目ID:', currentProject.id, 'URL:', url);
    }

    return fetch(url, {
        ...options,
        headers
    });
}

// 初始化应用
document.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 前端应用启动');

    // 初始化项目信息
    initializeProject();

    // 初始化设置
    initializeSettings();

    // 初始化事件监听
    initializeEventListeners();

    // 检查连接状态
    checkConnectionStatus();

    // 🔧 移除全局的loadChatHistory调用，现在在initializeProject中处理
    // loadChatHistory(); // ❌ 已删除
});

// 初始化项目信息
function initializeProject() {
    // 首先从localStorage中读取项目信息
    const savedProject = localStorage.getItem('currentProject');

    // 从URL参数中读取项目信息
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project');
    const projectName = urlParams.get('projectName');
    const projectType = urlParams.get('projectType');

    // 优先使用URL参数，如果没有则使用localStorage
    if (projectId && projectName) {
        // 验证项目ID格式
        if (!validateProjectId(projectId)) {
            console.error('❌ 无效的项目ID格式:', projectId);
            showNotification('项目ID格式无效', 'error');
            return;
        }

        currentProject = {
            id: projectId,
            name: projectName,
            type: projectType || '项目'
        };

        // 将项目信息保存到localStorage
        localStorage.setItem('currentProject', JSON.stringify(currentProject));

        console.log('🏗️ 从URL初始化项目:', currentProject);
        showNotification(`已锁定项目: ${currentProject.name}`, 'success');
    } else if (savedProject) {
        try {
            currentProject = JSON.parse(savedProject);

            // 验证恢复的项目数据
            if (!currentProject.id || !validateProjectId(currentProject.id)) {
                console.warn('⚠️ localStorage中的项目数据无效，清除');
                clearProjectLock();
                return;
            }

            console.log('🏗️ 从localStorage恢复项目:', currentProject);
            showNotification(`恢复项目锁定: ${currentProject.name}`, 'info');
        } catch (error) {
            console.error('❌ 解析项目数据失败:', error);
            clearProjectLock();
            return;
        }
    }

    if (currentProject) {
        // 显示项目信息
        displayProjectInfo();

        // 更新欢迎消息
        updateWelcomeMessage();

        // 更新页面标题
        document.title = `${currentProject.name} - 工程AI助手`;

        // 🆕 加载项目专属的对话历史和文件列表
        loadChatHistory();
        loadProjectFiles();

        console.log(`🔄 项目${currentProject.name}数据加载完成`);
    } else {
        console.log('📋 未指定项目，使用通用模式');
        // 在通用模式下仍然加载数据
        loadChatHistory();
        loadProjectFiles();
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

// 初始化设置
function initializeSettings() {
    const savedSettings = localStorage.getItem('userSettings');
    if (savedSettings) {
        userSettings = { ...userSettings, ...JSON.parse(savedSettings) };
    }

    // 应用主题
    setTheme(userSettings.theme);

    // 更新设置界面
    updateSettingsUI();
}

// 初始化事件监听
function initializeEventListeners() {
    // 侧边栏切换
    document.getElementById('sidebarToggle').addEventListener('click', toggleSidebar);

    // 输入框事件
    const inputField = document.getElementById('inputField');
    inputField.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    inputField.addEventListener('input', function () {
        updateSendButton();
    });

    // 发送按钮
    document.getElementById('sendButton').addEventListener('click', sendMessage);

    // 文件上传
    document.getElementById('tempUploadBtn').addEventListener('click', function () {
        document.getElementById('tempFileInput').click();
    });

    // 创建隐藏的文件输入框
    const tempFileInput = document.createElement('input');
    tempFileInput.type = 'file';
    tempFileInput.id = 'tempFileInput';
    tempFileInput.style.display = 'none';
    tempFileInput.multiple = true;
    tempFileInput.accept = '.pdf,.doc,.docx,.txt,.json,.csv,.xlsx,.jpg,.jpeg,.png';
    document.body.appendChild(tempFileInput);

    tempFileInput.addEventListener('change', handleTempFileUpload);

    // 设置拖拽上传
    setupDragAndDrop();

    // 设置面板关闭
    document.getElementById('settingsOverlay').addEventListener('click', function (e) {
        if (e.target === this) {
            closeSettings();
        }
    });
}

// 设置拖拽上传
function setupDragAndDrop() {
    const uploadZone = document.getElementById('uploadZone');

    uploadZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--primary-color)';
    });

    uploadZone.addEventListener('dragleave', function (e) {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--border-color)';
    });

    uploadZone.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--border-color)';

        const files = e.dataTransfer.files;
        handlePersistentFileUpload({ target: { files } });
    });
}

// 检查连接状态
async function checkConnectionStatus() {
    try {
        const response = await apiRequest(`${API_BASE}/status`);
        const data = await response.json();

        if (data.success) {
            updateConnectionStatus('已连接', true);
        } else {
            updateConnectionStatus('连接异常', false);
        }
    } catch (error) {
        console.error('连接检查失败:', error);
        updateConnectionStatus('连接失败', false);
    }
}

// 更新连接状态
function updateConnectionStatus(text, connected) {
    const statusElement = document.getElementById('connectionStatus');

    if (statusElement) {
        const statusDot = statusElement.querySelector('.status-dot');

        statusElement.textContent = text;

        // 如果存在状态点，更新其颜色
        if (statusDot) {
            statusDot.style.background = connected ? '#4caf50' : '#f44336';
        }

        // 如果没有状态点，直接更新文本颜色
        if (!statusDot) {
            statusElement.style.color = connected ? '#4caf50' : '#f44336';
        }
    }
}

// 切换侧边栏
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');

    sidebar.classList.toggle('collapsed');
    toggle.innerHTML = sidebar.classList.contains('collapsed') ?
        '<span>▶</span>' : '<span>◀</span>';
}

// 切换标签页
function switchTab(tabName) {
    // 移除所有active类
    document.querySelectorAll('.sidebar-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    // 添加active类到当前标签
    event.target.classList.add('active');

    // 显示对应内容
    if (tabName === 'files') {
        document.getElementById('filesTab').classList.add('active');
    } else if (tabName === 'history') {
        document.getElementById('historyTab').classList.add('active');
    }
}

// 处理临时文件上传
async function handleTempFileUpload(event) {
    const files = event.target.files;
    if (files.length === 0) return;

    const uploadBtn = document.getElementById('tempUploadBtn');
    uploadBtn.innerHTML = '⏳';
    uploadBtn.disabled = true;

    // 🚀 关键修改：设置上传状态，触发漏斗
    isUploading = true;
    updateSendButton(); // 立即更新发送按钮状态

    try {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            // 如果有项目信息，添加到FormData中
            if (currentProject) {
                formData.append('project', JSON.stringify(currentProject));
            }

            // 🌐 使用后端MinIO上传API
            const response = await apiRequest(`http://localhost:8000/api/upload`, {
                method: 'POST',
                body: formData,
                headers: {} // 清空Content-Type，让浏览器自动设置multipart/form-data
            });

            const data = await response.json();

            if (data.success) {
                const fileInfo = {
                    name: data.originalName || data.original_filename,  // 兼容两种字段名
                    path: data.minio_path,  // 🌐 使用MinIO路径
                    reactAgentPath: data.minio_path,  // 🌐 AI agent使用MinIO路径
                    type: data.mimetype,
                    size: data.size,
                    isTemporary: true
                };

                currentFiles.push(fileInfo);
                console.log('📎 临时文件已添加到currentFiles:', fileInfo.name, '当前文件数量:', currentFiles.length);
                updateCurrentFilesUI();

                // 更新项目统计 - 文件数量
                updateProjectStats('files');

                // 添加到左侧文件树
                addFileToTree(fileInfo);

                showNotification(`文件 "${fileInfo.name}" 上传成功`, 'success');
            } else {
                showNotification(`文件 "${file.name}" 上传失败`, 'error');
            }
        }
    } catch (error) {
        console.error('文件上传失败:', error);
        showNotification('文件上传失败', 'error');
    } finally {
        uploadBtn.innerHTML = '📎';
        uploadBtn.disabled = false;
        event.target.value = '';

        // 🚀 关键修改：重置上传状态，恢复发送按钮
        isUploading = false;
        updateSendButton(); // 更新发送按钮状态
    }
}

// 处理持久化文件上传
async function handlePersistentFileUpload(event) {
    const files = event.target.files || event.dataTransfer?.files;
    if (!files || files.length === 0) return;

    const uploadZone = document.getElementById('uploadZone');
    if (uploadZone) {
        uploadZone.innerHTML = '<div>⏳ 正在上传...</div>';
    }

    // 🚀 关键修改：设置上传状态，触发漏斗
    isUploading = true;
    updateSendButton(); // 立即更新发送按钮状态

    try {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            // 如果有项目信息，添加到FormData中
            if (currentProject) {
                formData.append('project', JSON.stringify(currentProject));
            }

            // 🌐 使用后端MinIO上传API
            const response = await apiRequest(`http://localhost:8000/api/upload`, {
                method: 'POST',
                body: formData,
                headers: {} // 清空Content-Type，让浏览器自动设置multipart/form-data
            });

            const data = await response.json();

            if (data.success) {
                // 🆕 既添加到知识库，又添加到当前对话的文件列表
                const fileInfo = {
                    name: data.originalName || data.original_filename,
                    path: data.minio_path,  // 🌐 使用MinIO路径
                    reactAgentPath: data.minio_path,  // 🌐 AI agent使用MinIO路径
                    type: data.mimetype,
                    size: data.size,
                    isTemporary: false  // 标记为持久化文件
                };

                // 添加到当前对话文件列表
                currentFiles.push(fileInfo);
                console.log('📎 文件已添加到currentFiles:', fileInfo.name, '当前文件数量:', currentFiles.length);
                updateCurrentFilesUI();

                // 更新项目统计 - 文件数量
                updateProjectStats('files');

                // 添加到左侧文件树
                addFileToTree(fileInfo);

                showNotification(`文件 "${fileInfo.name}" 已上传并添加到对话中`, 'success');

                // 添加到知识库的逻辑
                await addToKnowledgeBase(data);

            } else {
                showNotification(`文件 "${file.name}" 上传失败`, 'error');
            }
        }
    } catch (error) {
        console.error('文件上传失败:', error);
        showNotification('文件上传失败', 'error');
    } finally {
        if (uploadZone) {
            uploadZone.innerHTML = `
                <div>📎 拖拽文件到这里</div>
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">上传文件并添加到对话</div>
            `;
        }
        if (event.target && event.target.value) {
            event.target.value = '';
        }

        // 🚀 关键修改：重置上传状态，恢复发送按钮
        isUploading = false;
        updateSendButton(); // 更新发送按钮状态
    }
}

// 添加到知识库
async function addToKnowledgeBase(fileData) {
    try {
        // 这里调用后端的知识库添加API
        // 根据后端的RAG工具实现
        console.log('添加到知识库:', fileData);
        // 实际实现需要根据后端API调整
    } catch (error) {
        console.error('添加到知识库失败:', error);
    }
}

// 更新当前文件列表UI
function updateCurrentFilesUI() {
    const currentFilesContainer = document.getElementById('currentFiles');
    const currentFilesList = document.getElementById('currentFilesList');

    if (currentFiles.length === 0) {
        currentFilesContainer.classList.remove('show');
        return;
    }

    currentFilesContainer.classList.add('show');
    currentFilesList.innerHTML = currentFiles.map((file, index) => `
        <div class="current-file-item">
            <span>${getFileIcon(file.type)}</span>
            <span>${file.name}</span>
            <div class="file-actions">
                ${file.isTemporary ? '<span class="file-action" onclick="addToKnowledgeFromTemp(' + index + ')">存库</span>' : ''}
                <span class="file-action" onclick="removeCurrentFile(' + index + ')">删除</span>
            </div>
        </div>
    `).join('');
}

// 获取文件图标
function getFileIcon(mimeType) {
    // 容错处理：如果mimeType为undefined或null，返回默认图标
    if (!mimeType || typeof mimeType !== 'string') return '📎';

    if (mimeType.startsWith('image/')) return '🖼️';
    if (mimeType.includes('pdf')) return '📄';
    if (mimeType.includes('word')) return '📝';
    if (mimeType.includes('excel')) return '📊';
    if (mimeType.includes('text')) return '📄';
    return '📎';
}

// 添加文件到左侧文件树
function addFileToTree(fileInfo) {
    // 文件已经添加到currentFiles数组，直接更新UI
    updateFileTreeUI();

    // 🆕 保存到项目文件列表
    saveProjectFiles();
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 从临时文件添加到知识库
async function addToKnowledgeFromTemp(index) {
    const file = currentFiles[index];
    if (!file) return;

    try {
        await addToKnowledgeBase(file);
        showNotification(`文件 "${file.name}" 已添加到知识库`, 'success');

        // 更新文件状态
        file.isTemporary = false;
        updateCurrentFilesUI();
    } catch (error) {
        showNotification('添加到知识库失败', 'error');
    }
}

// 移除当前文件
function removeCurrentFile(index) {
    currentFiles.splice(index, 1);
    updateCurrentFilesUI();
}

// 清空所有当前文件
function clearAllCurrentFiles() {
    if (currentFiles.length === 0) {
        showNotification('没有文件需要清空', 'info');
        return;
    }

    const fileCount = currentFiles.length;
    currentFiles = [];
    updateCurrentFilesUI();
    console.log('🗑️ 已清空所有当前文件');
    showNotification(`已清空 ${fileCount} 个文件`, 'success');
}

// 更新发送按钮状态
function updateSendButton() {
    const inputField = document.getElementById('inputField');
    const sendButton = document.getElementById('sendButton');

    const hasText = inputField.value.trim().length > 0;
    const hasFiles = currentFiles.length > 0;

    // 🚀 关键修改：在上传期间禁用发送按钮并显示漏斗
    if (isUploading) {
        sendButton.disabled = true;
        sendButton.innerHTML = '⏳'; // 漏斗状态
        sendButton.title = '正在上传文件到MinIO...';
    } else {
        sendButton.disabled = !hasText && !hasFiles;
        sendButton.innerHTML = '发送'; // 正常状态
        sendButton.title = '发送消息';
    }
}

// 发送消息
async function sendMessage() {
    const inputField = document.getElementById('inputField');
    const message = inputField.value.trim();

    if (!message && currentFiles.length === 0) return;

    console.log('📤 发送消息:', message);
    console.log('🆔 当前对话ID:', currentChatId);
    console.log('📊 对话状态 - chatStarted:', chatStarted);
    console.log('📎 当前文件列表 currentFiles:', currentFiles.length, currentFiles.map(f => f.name));

    if (!chatStarted) {
        console.log('🆕 对话未开始，创建新对话');
        startNewChat();
        // 等待新对话创建完成
        await new Promise(resolve => setTimeout(resolve, 150));
    }

    // 再次确认当前对话ID
    console.log('✅ 确认当前对话ID:', currentChatId);

    // 添加用户消息
    if (message) {
        console.log('👤 添加用户消息到对话界面');
        addMessage('user', message);
    }

    // 清空输入
    inputField.value = '';
    updateSendButton();

    // 显示思考过程
    const thinkingProcess = createThinkingProcess();

    try {
        // 构建请求数据
        const requestData = {
            message: message,
            files: currentFiles,
            project: currentProject  // 传递项目信息
        };

        console.log('📤 发送到API的数据:', requestData);
        console.log('📎 发送的文件详情:', currentFiles.map(f => ({ name: f.name, path: f.path, type: f.type })));

        // 🌊 使用流式思考输出
        const finalResponse = await handleStreamingThoughts(requestData, thinkingProcess);

        // 保存到历史记录
        if (finalResponse) {
            console.log('💾 保存消息到历史记录，对话ID:', currentChatId);
            saveToHistory(message, finalResponse);
        }

    } catch (error) {
        console.error('发送消息失败:', error);
        removeThinkingProcess(thinkingProcess);
        showNotification('发送失败: ' + error.message, 'error');
    }
}

// 新建对话
function startNewChat() {
    console.log('🔄 开始新建对话');

    // 重置对话状态
    chatStarted = true;
    currentChatId = generateChatId();

    console.log('📝 新对话ID:', currentChatId);

    // 强制清空对话区域
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '';
    chatMessages.scrollTop = 0;

    // 隐藏欢迎界面，显示聊天界面
    document.getElementById('welcomePrompts').classList.add('hidden');
    document.getElementById('chatMessages').classList.add('show');

    // 创建新的对话记录
    const chatRecord = {
        id: currentChatId,
        title: '新对话',
        startTime: new Date(),
        messages: []
    };

    chatHistory.unshift(chatRecord);
    console.log('💾 创建新对话记录，当前历史记录数量:', chatHistory.length);

    updateChatHistoryUI();

    // 更新项目统计 - 对话数量
    updateProjectStats('chats');

    // 🆕 不再清空当前文件列表，保留用户已上传的文件
    // currentFiles = [];
    // updateCurrentFilesUI();
    console.log('📎 保留已上传的文件，当前文件数量:', currentFiles.length);

    // 添加欢迎消息 - 确保在DOM更新后执行
    setTimeout(() => {
        console.log('🤖 添加欢迎消息到对话ID:', currentChatId);
        addMessage('ai', '您好！我是您的AI生成文档助手。请告诉我您需要什么帮助？您可以上传文档进行分析，或者让我帮您生成新的文档。');

        // 将欢迎消息添加到对话记录中
        const currentChat = chatHistory.find(c => c.id === currentChatId);
        if (currentChat) {
            currentChat.messages.push({
                sender: 'ai',
                content: '您好！我是您的AI生成文档助手。请告诉我您需要什么帮助？您可以上传文档进行分析，或者让我帮您生成新的文档。',
                timestamp: new Date()
            });
            saveChatHistory();
            console.log('✅ 欢迎消息已保存到对话记录');
        } else {
            console.error('❌ 无法找到当前对话记录');
        }
    }, 100);
}

// 开始特定类型的对话
function startChat(category) {
    if (!chatStarted) {
        startNewChat();

        // 等待欢迎消息显示完成后再添加场景消息
        setTimeout(() => {
            // 更新对话标题
            const currentChat = chatHistory.find(c => c.id === currentChatId);
            if (currentChat) {
                currentChat.title = category;
                updateChatHistoryUI();
            }

            // 添加场景相关消息
            addMessage('ai', `您选择了"${category}"相关的服务。我可以为您提供专业的文档处理和生成服务。`);

            // 保存场景消息到历史记录
            if (currentChat) {
                currentChat.messages.push({
                    sender: 'ai',
                    content: `您选择了"${category}"相关的服务。我可以为您提供专业的文档处理和生成服务。`,
                    timestamp: new Date()
                });
                saveChatHistory();
            }
        }, 200);
    } else {
        // 如果已经开始对话，直接添加场景消息
        addMessage('ai', `您选择了"${category}"相关的服务。我可以为您提供专业的文档处理和生成服务。`);
    }
}

// 🌊 处理流式思考输出
async function handleStreamingThoughts(requestData, thinkingProcess) {
    try {
        // 第一步：启动流式会话（显示思考过程）
        console.log('🌊 启动流式思考会话...');
        const startResponse = await apiRequest(`${API_BASE}/start_stream`, {
            method: 'POST',
            body: JSON.stringify({
                problem: requestData.message,
                files: requestData.files,
                project_context: requestData.project
            })
        });

        if (!startResponse.ok) {
            throw new Error(`启动流式会话失败: ${startResponse.status}`);
        }

        const sessionData = await startResponse.json();
        console.log('🆔 获得会话ID:', sessionData.session_id);

        // 第二步：连接SSE流显示思考过程
        const eventSource = new EventSource(`/api/stream/thoughts/${sessionData.session_id}`);

        let thoughtCount = 0;
        window.currentThoughtCount = 0;

        // 🔧 简化流式处理：只显示思考过程，不处理final_answer
        return new Promise((resolve) => {
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('🌊 收到流式数据:', data);

                    switch (data.type) {
                        case 'start':
                            console.log('🌊 思考开始');
                            break;

                        case 'iteration':
                            console.log(`🔄 第${data.round}轮思考`);
                            break;

                        case 'thought':
                            thoughtCount++;
                            window.currentThoughtCount = thoughtCount;
                            console.log(`💭 收到第${thoughtCount}个思考步骤:`, data.content);
                            if (userSettings.showThinking) {
                                handleThinkingEvent({
                                    type: 'thinking_step',
                                    step: thoughtCount,
                                    title: '推理思考',
                                    content: data.content,
                                    status: 'completed'
                                });
                            }
                            break;

                        case 'action':
                            console.log(`🔧 收到工具调用:`, data.content);
                            break;

                        case 'action_input':
                            console.log(`📝 收到工具输入参数:`, data.content);
                            break;

                        case 'observation':
                            console.log(`👁️ 收到观察结果:`, data.content.substring(0, 100) + '...');
                            break;

                        case 'final_answer':
                            // 🔧 不在流式中处理final_answer，交给后续的API调用
                            console.log('📋 流式中收到final_answer，但将通过API调用获取完整结果');
                            break;

                        case 'complete':
                        case 'timeout':
                        case 'error':
                            console.log(`🎉 思考流程结束: ${data.type}`);
                            completeThinking(thinkingProcess);
                            eventSource.close();

                            // 🚀 修改：直接使用后端发送的final_result，不重新调用API
                            if (data.type === 'complete' && data.final_result) {
                                const finalAnswer = data.final_result;

                                // 🔍 详细验证接收到的数据
                                console.log('📥 前端接收Final Answer详细信息:');
                                console.log('   - 接收长度:', finalAnswer.length, '字符');
                                console.log('   - 接收行数:', finalAnswer.split('\n').length, '行');
                                console.log('   - 开头100字符:', finalAnswer.substring(0, 100));
                                console.log('   - 结尾100字符:', finalAnswer.substring(Math.max(0, finalAnswer.length - 100)));
                                console.log('   - 是否包含"医灵古庙":', finalAnswer.includes('医灵古庙'));
                                console.log('   - 是否包含"历史沿革":', finalAnswer.includes('历史沿革'));

                                // 🆕 检测是否包含task_id，如果是文档生成任务，启动轮询
                                const taskIdMatch = finalAnswer.match(/任务ID[：:]\s*([a-zA-Z0-9_-]+)/);
                                if (taskIdMatch) {
                                    const taskId = taskIdMatch[1];
                                    console.log('🎯 检测到文档生成任务ID:', taskId);

                                    // 显示初始响应
                                    addMessage('ai', finalAnswer);

                                    // 开始轮询任务状态
                                    startTaskPolling(taskId, finalAnswer);

                                    resolve(finalAnswer);
                                } else {
                                    // 普通响应，直接显示
                                    addMessage('ai', finalAnswer);
                                    resolve(finalAnswer);
                                }

                                // 🔍 验证DOM中的显示
                                setTimeout(() => {
                                    const messages = document.querySelectorAll('.message.ai');
                                    const lastMessage = messages[messages.length - 1];
                                    if (lastMessage) {
                                        const content = lastMessage.querySelector('.message-content');
                                        if (content) {
                                            console.log('📋 DOM中显示验证:');
                                            console.log('   - DOM文本长度:', content.textContent.length, '字符');
                                            console.log('   - DOM HTML长度:', content.innerHTML.length, '字符');
                                            console.log('   - DOM是否包含"医灵古庙":', content.textContent.includes('医灵古庙'));
                                        }
                                    }
                                }, 200);

                            } else if (data.type === 'error') {
                                const errorMsg = data.message || '处理过程中出现错误';
                                console.error('❌ 流式处理错误:', errorMsg);
                                addMessage('ai', `❌ ${errorMsg}`);
                                resolve(errorMsg);
                            } else {
                                // 没有final_result的情况，使用默认消息
                                console.warn('⚠️ 没有收到final_result');
                                addMessage('ai', '✅ 思考完成，但未获得最终结果');
                                resolve('思考完成');
                            }
                            return;
                    }
                } catch (e) {
                    console.error('❌ 解析流式数据失败:', e, event.data);
                }
            };

            eventSource.onerror = (error) => {
                console.error('❌ EventSource错误:', error);
                completeThinking(thinkingProcess);
                eventSource.close();
                resolve('流式连接失败');
            };
        });

    } catch (error) {
        console.error('❌ 流式思考失败:', error);
        completeThinking(thinkingProcess);
        throw error;
    }
}

// 生成对话ID
function generateChatId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// 添加消息
function addMessage(sender, content) {
    console.log(`💬 addMessage: ${sender} - ${content.substring(0, 50)}...`);
    console.log('🎯 当前对话ID:', currentChatId);

    // 🔍 对于长内容，添加详细信息
    if (content.length > 500) {
        console.log('📏 长内容详细信息:');
        console.log('   - 内容长度:', content.length, '字符');
        console.log('   - 内容行数:', content.split('\n').length, '行');
        console.log('   - 内容预览:', content.substring(0, 200) + '...[truncated]...' + content.substring(Math.max(0, content.length - 100)));
    }

    const chatMessages = document.getElementById('chatMessages');

    // 确保聊天界面是显示状态
    if (!chatMessages.classList.contains('show')) {
        console.log('🔄 聊天界面未显示，强制显示');
        document.getElementById('welcomePrompts').classList.add('hidden');
        chatMessages.classList.add('show');
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.setAttribute('data-chat-id', currentChatId || 'unknown');

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = sender === 'ai' ? '🤖' : '👤';

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';

    // 🆕 优先使用marked.js，备用简单Markdown渲染
    if (typeof marked !== 'undefined') {
        console.log('✅ 使用marked.js渲染消息');
        messageContent.innerHTML = marked.parse(content);
    } else {
        console.log('⚠️ marked.js不可用，使用备用渲染方法');
        // 备用：增强的简单Markdown渲染，包含链接支持
        let formattedContent = content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // 加粗
            .replace(/\*(.*?)\*/g, '<em>$1</em>')             // 斜体
            .replace(/---/g, '<hr>')                          // 分隔线
            .replace(/`(.*?)`/g, '<code>$1</code>')           // 代码
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>'); // 链接

        messageContent.innerHTML = formattedContent;
    }

    // 🆕 处理预览链接，将其转换为可点击的按钮
    setTimeout(() => {
        // �� 修复：使用更准确的方式匹配预览链接
        const previewLinks = messageContent.querySelectorAll('a[href*="preview-"]');
        previewLinks.forEach(link => {
            // 从链接文本或href中提取taskId
            const linkHref = link.getAttribute('href') || '';
            const taskIdMatch = linkHref.match(/preview-([a-zA-Z0-9-]+)/);

            if (taskIdMatch) {
                const taskId = taskIdMatch[1];
                console.log('🔗 找到预览链接，任务ID:', taskId);

                link.href = 'javascript:void(0)';
                link.onclick = (e) => {
                    e.preventDefault();
                    previewMarkdownDocument(taskId);
                };
                link.style.cssText = `
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 6px 12px;
                    background: #8b5cf6;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-size: 14px;
                    margin: 4px 0;
                    transition: background 0.2s ease;
                    cursor: pointer;
                `;
                link.onmouseover = () => link.style.background = '#7c3aed';
                link.onmouseout = () => link.style.background = '#8b5cf6';
            }
        });
    }, 100);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);

    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;

    console.log('✅ 消息已添加到界面，当前消息数量:', chatMessages.children.length);

    // 🔍 对于长内容，验证DOM渲染结果
    if (content.length > 500) {
        console.log('🔍 DOM渲染验证:');
        console.log('   - messageContent.innerHTML长度:', messageContent.innerHTML.length);
        console.log('   - messageContent.textContent长度:', messageContent.textContent.length);
    }
}

// 创建思考过程
function createThinkingProcess() {
    if (!userSettings.showThinking) return null;

    const chatMessages = document.getElementById('chatMessages');

    // 直接创建思考过程，不要外层消息容器
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'thinking-process';
    thinkingDiv.innerHTML = `
        <div class="thinking-header" onclick="toggleThinkingProcess(this)">
            <div class="thinking-title">
                <span class="emoji">🤔</span>
                <span>AI正在思考中<span class="loading-dots"></span></span>
            </div>
            <button class="thinking-toggle">▼</button>
        </div>
        <div class="thinking-content" id="thinking-steps-container">
            <div class="thinking-step step-running">
                <div class="step-header">
                    <span class="step-title">⏳ 初始化思考过程</span>
                </div>
                <div class="step-content">正在分析您的问题，准备调用相关工具...</div>
            </div>
        </div>
    `;

    chatMessages.appendChild(thinkingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return thinkingDiv;
}

// 🆕 处理真实的思考事件
function handleThinkingEvent(data) {
    if (!userSettings.showThinking) return;

    const thinkingContainer = document.getElementById('thinking-steps-container');
    if (!thinkingContainer) return;

    console.log('🧠 处理思考事件:', data);

    // 根据事件类型创建不同的思考步骤
    if (data.type === 'thinking_step') {
        // 移除初始化步骤
        const initStep = thinkingContainer.querySelector('.step-running');
        if (initStep && initStep.textContent.includes('初始化')) {
            initStep.remove();
        }

        const stepDiv = document.createElement('div');
        stepDiv.className = `thinking-step step-${data.status || 'completed'}`;
        stepDiv.setAttribute('data-step', data.step || 0);
        stepDiv.setAttribute('data-status', data.status || 'completed');

        // 根据状态设置不同的图标和样式
        let statusIcon = '✅';
        let stepClass = 'step-completed';
        if (data.status === 'running') {
            statusIcon = '⏳';
            stepClass = 'step-running';
        } else if (data.status === 'error') {
            statusIcon = '❌';
            stepClass = 'step-error';
        }

        stepDiv.className = `thinking-step ${stepClass}`;

        let stepContent = `
            <div class="step-content">${data.content || ''}</div>
        `;

        // 如果有工具调用信息，添加到显示中
        if (data.action) {
            stepContent += `
                <div class="step-tool">
                    <strong>调用工具:</strong> <code>${data.action}</code>
                    <div style="margin-top: 8px; font-size: 12px; color: var(--text-tertiary);">
                        正在与工具服务通信...
                    </div>
                </div>
            `;
        }

        if (data.input) {
            const inputDisplay = typeof data.input === 'object' ?
                JSON.stringify(data.input, null, 2) : data.input;
            stepContent += `
                <div class="step-input">
                    <strong>输入参数:</strong>
                    <pre>${inputDisplay}</pre>
                </div>
            `;
        }

        if (data.observation) {
            // 截短过长的观察结果
            const obsDisplay = data.observation.length > 300 ?
                data.observation.substring(0, 300) + '...\n[结果已截断]' :
                data.observation;

            stepContent += `
                <div class="step-observation">
                    <strong>执行结果:</strong>
                    <pre>${obsDisplay}</pre>
                </div>
            `;
        }

        stepDiv.innerHTML = stepContent;
        thinkingContainer.appendChild(stepDiv);

        // 立即滚动到新步骤
        stepDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // 滚动到底部
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 完成思考过程
function completeThinking(thinkingProcess) {
    if (!thinkingProcess) return;

    // 移除可能残留的运行中步骤
    const runningSteps = thinkingProcess.querySelectorAll('.step-running');
    runningSteps.forEach(step => {
        if (step.textContent.includes('初始化')) {
            step.remove();
        }
    });

    // 更新标题
    const title = thinkingProcess.querySelector('.thinking-title span:last-child');
    const emoji = thinkingProcess.querySelector('.thinking-title .emoji');
    const loadingDots = thinkingProcess.querySelector('.loading-dots');

    title.textContent = '思考完成';
    emoji.textContent = '✅';
    emoji.style.animation = 'none';

    // 移除loading动画
    if (loadingDots) {
        loadingDots.style.display = 'none';
    }

    // 移除思考总结显示

    // 4秒后自动收起
    setTimeout(() => {
        const content = thinkingProcess.querySelector('.thinking-content');
        const toggle = thinkingProcess.querySelector('.thinking-toggle');
        if (content && toggle) {
            content.style.display = 'none';
            toggle.textContent = '▶';
        }
    }, 4000);
}

// 移除思考过程
function removeThinkingProcess(thinkingProcess) {
    if (thinkingProcess && thinkingProcess.parentNode) {
        thinkingProcess.parentNode.removeChild(thinkingProcess);
    }
}

// 切换思考过程显示
function toggleThinkingProcess(header) {
    const content = header.nextElementSibling;
    const toggle = header.querySelector('.thinking-toggle');

    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.textContent = '▼';
    } else {
        content.style.display = 'none';
        toggle.textContent = '▶';
    }
}

// 保存到历史记录
function saveToHistory(userMessage, aiResponse) {
    console.log('💾 saveToHistory 被调用');
    console.log('🔧 autoSave设置:', userSettings.autoSave);
    console.log('🆔 要保存到的对话ID:', currentChatId);

    if (!userSettings.autoSave) {
        console.log('❌ 自动保存已禁用，跳过保存');
        return;
    }

    const currentChat = chatHistory.find(c => c.id === currentChatId);
    console.log('🔍 查找对话结果:', currentChat ? '找到' : '未找到');

    if (currentChat) {
        console.log('📝 保存用户消息:', userMessage);
        currentChat.messages.push({
            sender: 'user',
            content: userMessage,
            timestamp: new Date()
        });

        console.log('🤖 保存AI回复:', aiResponse.substring(0, 50) + '...');
        currentChat.messages.push({
            sender: 'ai',
            content: aiResponse,
            timestamp: new Date()
        });

        // 更新标题为第一条用户消息
        if (currentChat.messages.filter(m => m.sender === 'user').length === 1) {
            const newTitle = userMessage.length > 30 ? userMessage.substring(0, 30) + '...' : userMessage;
            console.log('📋 更新对话标题:', newTitle);
            currentChat.title = newTitle;
        }

        console.log('📊 对话消息总数:', currentChat.messages.length);
        updateChatHistoryUI();
        saveChatHistory();
        console.log('✅ 消息已保存到历史记录');
    } else {
        console.error('❌ 无法找到当前对话记录，无法保存消息');
        console.error('📋 可用的对话ID列表:', chatHistory.map(c => c.id));
    }
}

// 更新对话历史UI
function updateChatHistoryUI() {
    const historyList = document.getElementById('historyList');

    if (chatHistory.length === 0) {
        historyList.innerHTML = `
            <div style="color: var(--text-tertiary); font-size: 12px; text-align: center; padding: 20px;">
                点击"新建对话"开始
            </div>
        `;
        return;
    }

    historyList.innerHTML = chatHistory.map(chat => `
        <div class="history-item ${chat.id === currentChatId ? 'active' : ''}" onclick="switchToChat('${chat.id}')">
            <div class="history-time">${formatTime(chat.startTime)}</div>
            <div class="history-preview">${chat.title}</div>
        </div>
    `).join('');
}

// 切换到指定对话
function switchToChat(chatId) {
    const chat = chatHistory.find(c => c.id === chatId);
    if (!chat) return;

    currentChatId = chatId;

    // 清空当前对话
    document.getElementById('chatMessages').innerHTML = '';

    // 隐藏欢迎界面，显示聊天界面
    document.getElementById('welcomePrompts').classList.add('hidden');
    document.getElementById('chatMessages').classList.add('show');

    // 重新显示历史消息
    setTimeout(() => {
        chat.messages.forEach(msg => {
            addMessage(msg.sender, msg.content);
        });
    }, 50);

    updateChatHistoryUI();

    if (!chatStarted) {
        chatStarted = true;
    }
}

// 格式化时间
function formatTime(date) {
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}天前`;
    if (hours > 0) return `${hours}小时前`;
    if (minutes > 0) return `${minutes}分钟前`;
    return '刚刚';
}

// 清空所有历史
function clearAllHistory() {
    if (!confirm('确定要清空当前项目的所有对话历史吗？此操作不可恢复。')) {
        return;
    }

    console.log(`🗑️ 清空项目${currentProject ? currentProject.name : '通用'}的所有对话历史`);

    chatHistory = [];
    currentChatId = null;
    chatStarted = false;

    // 清空聊天界面
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '';
    chatMessages.classList.remove('show');

    // 显示欢迎界面
    document.getElementById('welcomePrompts').classList.remove('hidden');

    // 🆕 保存清空后的历史（按项目分别保存）
    saveChatHistory();
    updateChatHistoryUI();

    const projectName = currentProject ? currentProject.name : '通用项目';
    showNotification(`${projectName}的对话历史已清空`, 'success');
    console.log(`✅ ${projectName}的对话历史清空完成`);
}

// 保存聊天历史
function saveChatHistory() {
    if (!currentProject || !currentProject.id) {
        // 如果没有项目信息，保存到通用历史
        localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
        return;
    }

    // 🆕 按项目ID分别保存对话历史
    const projectHistoryKey = `chatHistory_${currentProject.id}`;
    localStorage.setItem(projectHistoryKey, JSON.stringify(chatHistory));
    console.log(`💾 保存项目${currentProject.name}的对话历史，共${chatHistory.length}条对话`);
}

// 加载聊天历史
function loadChatHistory() {
    if (!currentProject || !currentProject.id) {
        // 如果没有项目信息，加载通用历史
        const saved = localStorage.getItem('chatHistory');
        if (saved) {
            chatHistory = JSON.parse(saved);
        } else {
            chatHistory = [];
        }
    } else {
        // 🆕 按项目ID加载对应的对话历史
        const projectHistoryKey = `chatHistory_${currentProject.id}`;
        const saved = localStorage.getItem(projectHistoryKey);
        if (saved) {
            chatHistory = JSON.parse(saved);
            console.log(`📚 加载项目${currentProject.name}的对话历史，共${chatHistory.length}条对话`);
        } else {
            chatHistory = [];
            console.log(`📝 项目${currentProject.name}暂无对话历史，初始化为空`);
        }
    }

    updateChatHistoryUI();

    // 重要：加载历史记录后，确保没有设置当前对话ID
    // 这样用户必须明确选择一个对话或新建对话
    currentChatId = null;
    chatStarted = false;
}

// 打开设置面板
function openSettings() {
    updateProjectDisplayInSettings();
    document.getElementById('settingsOverlay').classList.add('show');
}

// 关闭设置面板
function closeSettings() {
    document.getElementById('settingsOverlay').classList.remove('show');
}

// 设置主题
function setTheme(theme) {
    userSettings.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);

    // 更新主题按钮状态
    document.querySelectorAll('.theme-option').forEach(btn => {
        btn.classList.remove('active');
    });

    const activeBtn = document.querySelector(`[onclick*="${theme}"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    saveSettings();
}

// 切换思考过程显示
function toggleThinking(show) {
    userSettings.showThinking = show;
    updateSettingsUI();
}

// 切换自动保存
function toggleAutoSave(enable) {
    userSettings.autoSave = enable;
    updateSettingsUI();
}

// 更新设置UI
function updateSettingsUI() {
    // 更新思考过程按钮
    document.querySelectorAll('[onclick*="toggleThinking"]').forEach(btn => {
        btn.classList.remove('active');
    });
    const thinkingBtn = document.querySelector(`[onclick*="toggleThinking(${userSettings.showThinking})"]`);
    if (thinkingBtn) thinkingBtn.classList.add('active');

    // 更新自动保存按钮
    document.querySelectorAll('[onclick*="toggleAutoSave"]').forEach(btn => {
        btn.classList.remove('active');
    });
    const autoSaveBtn = document.querySelector(`[onclick*="toggleAutoSave(${userSettings.autoSave})"]`);
    if (autoSaveBtn) autoSaveBtn.classList.add('active');
}

// 重置设置
function resetSettings() {
    if (confirm('确定要重置所有设置吗？')) {
        userSettings = {
            theme: 'light',
            showThinking: true,
            autoSave: true
        };

        setTheme('light');
        updateSettingsUI();
        saveSettings();

        showNotification('设置已重置', 'success');
    }
}

// 保存设置
function saveSettings() {
    localStorage.setItem('userSettings', JSON.stringify(userSettings));
    showNotification('设置已保存', 'success');
}

// 显示通知
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#4caf50' : type === 'error' ? '#f44336' : 'var(--primary-color)'};
        color: white;
        border-radius: 8px;
        z-index: 10001;
        font-size: 14px;
        box-shadow: var(--shadow-md);
        animation: slideInRight 0.3s ease;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// CSS动画
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// 返回项目选择页面
function goBackToProjectSelection() {
    if (confirm('确定要返回项目选择页面吗？当前对话将被保存。')) {
        // 保存当前状态
        if (userSettings.autoSave) {
            saveChatHistory();
        }

        // 跳转回项目选择页面
        window.location.href = '/project_selector.html';
    }
}

// 更新设置面板中的项目显示
function updateProjectDisplayInSettings() {
    const projectDisplay = document.getElementById('currentProjectDisplay');
    if (projectDisplay) {
        projectDisplay.textContent = getProjectSummary();
    }
}

// 导出函数到全局作用域，供HTML中的onclick使用
window.openSettings = openSettings;
window.closeSettings = closeSettings;
window.setTheme = setTheme;
window.toggleThinking = toggleThinking;
window.toggleAutoSave = toggleAutoSave;
window.resetSettings = resetSettings;
window.saveSettings = saveSettings;
window.startNewChat = startNewChat;
window.startChat = startChat;
window.switchTab = switchTab;
window.switchToChat = switchToChat;
window.clearAllHistory = clearAllHistory;
window.addToKnowledgeFromTemp = addToKnowledgeFromTemp;
window.removeCurrentFile = removeCurrentFile;
window.toggleThinkingProcess = toggleThinkingProcess;
window.clearProjectLock = clearProjectLock;
window.goBackToProjectSelection = goBackToProjectSelection;

// 更新项目统计数据
function updateProjectStats(type) {
    if (!currentProject) return;

    // 获取或初始化项目统计数据
    let projectStats = JSON.parse(localStorage.getItem('projectData') || '{}');

    // 使用项目ID作为key
    const projectKey = currentProject.id;

    if (!projectStats[projectKey]) {
        projectStats[projectKey] = { files: 0, chats: 0 };
    }

    // 更新对应类型的统计
    if (type === 'files') {
        projectStats[projectKey].files++;
        console.log(`📊 项目 ${currentProject.name} 文件数量更新为: ${projectStats[projectKey].files}`);
    } else if (type === 'chats') {
        projectStats[projectKey].chats++;
        console.log(`📊 项目 ${currentProject.name} 对话数量更新为: ${projectStats[projectKey].chats}`);
    }

    // 保存到localStorage
    localStorage.setItem('projectData', JSON.stringify(projectStats));

    // 如果父页面有项目管理器，通知更新
    if (window.opener && window.opener.projectManager) {
        window.opener.projectManager.updateCounts();
    }
}

// 清除项目锁定
function clearProjectLock() {
    localStorage.removeItem('currentProject');
    currentProject = null;
    console.log('🔓 项目锁定已清除');

    // 重置页面标题
    document.title = '工程AI助手';

    // 隐藏项目信息
    const projectInfo = document.getElementById('projectInfo');
    if (projectInfo) {
        projectInfo.style.display = 'none';
    }

    // 重置欢迎消息
    const welcomeTitle = document.querySelector('.welcome-title');
    const welcomeSubtitle = document.querySelector('.welcome-subtitle');
    if (welcomeTitle && welcomeSubtitle) {
        welcomeTitle.textContent = '欢迎使用AI生成文档助手';
        welcomeSubtitle.textContent = '点击左侧"新建对话"开始，或选择下方场景快速开始';
    }
}

// 验证项目ID格式
function validateProjectId(projectId) {
    if (!projectId || typeof projectId !== 'string') {
        return false;
    }

    // 项目ID应该是合法的字符串，不包含特殊字符
    const validPattern = /^[a-zA-Z0-9_\-\u4e00-\u9fff]+$/;
    return validPattern.test(projectId);
}

// 检查项目权限（预留功能）
async function checkProjectPermission(projectId) {
    try {
        const response = await apiRequest(`${API_BASE}/project/check`, {
            method: 'POST',
            body: JSON.stringify({ projectId })
        });

        const data = await response.json();
        return data.success && data.hasPermission;
    } catch (error) {
        console.warn('无法验证项目权限:', error);
        return true; // 默认允许访问
    }
}

// 获取项目信息摘要
function getProjectSummary() {
    if (!currentProject) {
        return '未选择项目';
    }

    return `项目: ${currentProject.name} (${currentProject.type}) - ID: ${currentProject.id}`;
}

// 🆕 处理下载链接的函数 - 简化版本
function processDownloadLinks(content) {
    console.log('🔍 处理下载链接 - 输入内容长度:', content ? content.length : 'undefined');
    console.log('🔍 处理下载链接 - 输入前100字符:', content ? content.substring(0, 100) : 'undefined');

    if (!content) {
        console.warn('⚠️ processDownloadLinks: 输入内容为空');
        return '';
    }

    // 🔧 简化处理：只进行基本的文本格式化，确保不截断内容
    let processedContent = content
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');

    console.log('🔍 基本格式化后长度:', processedContent ? processedContent.length : 'undefined');

    // 🔍 简化的下载链接检测 - 只处理明确的下载链接格式
    try {
        // 模式1：[下载 文档名称](minio_url)
        processedContent = processedContent.replace(/\[下载\s+([^\]]+)\]\((http[^\)]+)\)/g, (match, filename, url) => {
            console.log('🔗 检测到下载链接:', filename, url);
            return createSimpleDownloadButton(filename, url);
        });

        // 模式2：**下载链接：** http://...
        processedContent = processedContent.replace(/\*\*下载链接[：:]\*\*\s*(http[^\s<]+)/g, (match, url) => {
            console.log('🔗 检测到下载链接2:', url);
            const filename = extractFilenameFromUrl(url);
            return `<strong>下载链接：</strong><br>${createSimpleDownloadButton(filename, url)}`;
        });
    } catch (error) {
        console.error('❌ 下载链接处理失败:', error);
        // 如果链接处理失败，至少返回基本格式化的内容
    }

    console.log('🔍 处理下载链接 - 输出内容长度:', processedContent ? processedContent.length : 'undefined');
    console.log('🔍 处理下载链接 - 输出前100字符:', processedContent ? processedContent.substring(0, 100) : 'undefined');
    console.log('🔍 处理下载链接 - 输出后100字符:', processedContent ? processedContent.substring(Math.max(0, processedContent.length - 100)) : 'undefined');

    return processedContent;
}

// 🔗 创建简单下载按钮
function createSimpleDownloadButton(filename, url) {
    return `
        <div style="margin: 10px 0;">
            <a href="${url}" 
               download="${filename}" 
               style="
                   background: #007bff;
                   color: white;
                   padding: 8px 16px;
                   text-decoration: none;
                   border-radius: 4px;
                   display: inline-block;
                   margin: 5px 0;
               "
               onclick="console.log('🔽 下载文件:', '${filename}')">
                📄 下载 ${filename}
            </a>
        </div>
    `;
}

// 📁 从URL提取文件名
function extractFilenameFromUrl(url) {
    try {
        const urlParts = url.split('/');
        const filename = urlParts[urlParts.length - 1];

        // 如果文件名包含查询参数，去除它们
        const cleanFilename = filename.split('?')[0];

        // 如果没有扩展名，添加默认扩展名
        if (!cleanFilename.includes('.')) {
            return cleanFilename + '.pdf';
        }

        return cleanFilename;
    } catch (error) {
        console.error('提取文件名失败:', error);
        return '生成的文档.pdf';
    }
}

// 🔽 处理文件下载
function handleDownload(url, filename) {
    console.log('🔽 开始下载文件:', filename, url);

    try {
        // 显示下载提示
        showNotification(`正在下载 ${filename}...`, 'info');

        // 创建隐藏的下载链接
        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = filename;
        downloadLink.style.display = 'none';

        // 添加到页面并点击
        document.body.appendChild(downloadLink);
        downloadLink.click();

        // 清理
        setTimeout(() => {
            document.body.removeChild(downloadLink);
            showNotification(`${filename} 下载开始！`, 'success');
        }, 100);

    } catch (error) {
        console.error('下载失败:', error);
        showNotification(`下载失败: ${error.message}`, 'error');

        // fallback: 在新窗口打开
        window.open(url, '_blank');
    }
}

// 🔄 任务状态轮询功能
let pollingIntervals = new Map(); // 存储所有活动的轮询任务

async function startTaskPolling(taskId, originalMessage) {
    console.log(`🔄 开始轮询任务 ${taskId}`);

    let pollCount = 0;
    const maxPolls = 180; // 最多轮询30分钟 (180 * 10s)

    // 如果已经在轮询这个任务，先清除
    if (pollingIntervals.has(taskId)) {
        clearInterval(pollingIntervals.get(taskId));
    }

    // 创建轮询任务
    const pollInterval = setInterval(async () => {
        pollCount++;
        console.log(`📋 第${pollCount}次查询任务${taskId}状态...`);

        try {
            const response = await apiRequest(`${API_BASE}/tasks/${taskId}`);

            if (!response.ok) {
                console.error(`❌ 查询任务状态失败: ${response.status}`);

                // 如果查询失败次数过多，停止轮询
                if (pollCount >= 5) {
                    console.log(`❌ 任务${taskId}查询失败次数过多，停止轮询`);
                    clearTaskPolling(taskId);
                    updateTaskMessage(taskId, '⚠️ 任务状态查询失败，请稍后手动检查');
                }
                return;
            }

            const taskData = await response.json();
            console.log(`📊 任务${taskId}状态:`, taskData);

            // 检查任务状态
            const status = taskData.status?.toLowerCase();

            if (status === 'completed' || status === 'done' || status === 'finished' || status === 'success') {
                console.log(`✅ 任务${taskId}已完成!`);
                clearTaskPolling(taskId);

                // 处理完成结果
                await handleTaskCompletion(taskId, taskData, originalMessage);

            } else if (status === 'failed' || status === 'error') {
                console.log(`❌ 任务${taskId}失败:`, taskData.error);
                clearTaskPolling(taskId);

                updateTaskMessage(taskId, `❌ 文档生成失败: ${taskData.error || '未知错误'}`);

            } else {
                // 任务仍在进行中，更新进度显示
                console.log(`⏳ 任务${taskId}进行中，状态: ${status}`);
                updateTaskProgress(taskId, taskData);
            }

        } catch (error) {
            console.error(`❌ 查询任务${taskId}状态异常:`, error);

            // 网络错误等，继续重试，但有次数限制
            if (pollCount >= maxPolls) {
                console.log(`❌ 任务${taskId}轮询超时，停止查询`);
                clearTaskPolling(taskId);
                updateTaskMessage(taskId, '⚠️ 任务查询超时，请稍后手动检查');
            }
        }

    }, 10000); // 每10秒查询一次

    // 保存轮询任务引用
    pollingIntervals.set(taskId, pollInterval);

    // 显示轮询开始提示
    updateTaskProgress(taskId, { status: 'polling_started' });
}

function clearTaskPolling(taskId) {
    if (pollingIntervals.has(taskId)) {
        clearInterval(pollingIntervals.get(taskId));
        pollingIntervals.delete(taskId);
        console.log(`🔄 已清除任务${taskId}的轮询`);
    }
}

async function handleTaskCompletion(taskId, taskData, originalMessage) {
    console.log(`🎉 处理任务${taskId}完成结果:`, taskData);
    console.log(`🔍 详细数据检查 - taskData结构:`, JSON.stringify(taskData, null, 2));

    // 🔧 根据API文档，files和minio_urls在result字段中
    let files = {};
    let minioUrls = {};
    let message = '';

    // 尝试从不同位置提取数据
    if (taskData.result) {
        // 主要路径：从result字段中提取
        files = taskData.result.files || {};
        minioUrls = taskData.result.minio_urls || {};
        message = taskData.result.message || '';
        console.log('📋 从result字段提取数据:');
        console.log('   - files:', files);
        console.log('   - minioUrls数量:', Object.keys(minioUrls).length);
        console.log('   - minioUrls keys:', Object.keys(minioUrls));
        console.log('   - message:', message);
    } else {
        // 备用路径：直接从根级别提取（适配不同的API响应格式）
        files = taskData.files || {};
        minioUrls = taskData.minio_urls || {};
        message = taskData.message || '';
        console.log('📋 从根级别提取数据:', { files, minioUrls, message });
    }

    // 构建完成消息
    let completionMessage = '✅ 文档生成完成！\n\n';

    if (message) {
        completionMessage += `📝 ${message}\n\n`;
    }

    if (Object.keys(minioUrls).length > 0) {
        completionMessage += '📥 **下载链接：**\n\n';

        // 🎯 优先显示final_document (最重要的文档)
        if (minioUrls.final_document) {
            const finalDocUrl = minioUrls.final_document;
            const finalDocName = extractDocumentName(finalDocUrl) || '完整版文档';
            completionMessage += `🎯 **主要文档：**\n`;
            completionMessage += `- [📄 ${finalDocName}](${finalDocUrl})\n`;
            completionMessage += `- [📖 预览文档](javascript:void(0)) [点击预览Markdown渲染效果](preview-${taskId})\n\n`;
            console.log('✅ 添加主要文档链接:', finalDocName, finalDocUrl);

            // 🆕 保存final_document URL以供预览使用
            window.taskDocuments = window.taskDocuments || {};
            window.taskDocuments[taskId] = {
                url: finalDocUrl,
                name: finalDocName
            };
        }

        // 🔧 显示其他辅助文件
        const otherFiles = Object.entries(minioUrls).filter(([key]) => key !== 'final_document');
        if (otherFiles.length > 0) {
            completionMessage += `📋 **辅助文件：**\n`;
            for (const [key, url] of otherFiles) {
                const filename = getDisplayName(key, files[key]) || `${key}文件`;
                completionMessage += `- [📄 ${filename}](${url})\n`;
                console.log('📎 添加辅助文件链接:', filename, url);
            }
            completionMessage += '\n';
        }

        completionMessage += '💡 点击链接即可下载文档';
    } else {
        console.warn('⚠️ 未找到minio_urls，显示调试信息');
        completionMessage += '⚠️ 文档已生成，但未找到下载链接。\n\n';
        completionMessage += '📋 **调试信息：**\n';
        completionMessage += `- 任务ID: ${taskId}\n`;
        completionMessage += `- 状态: ${taskData.status}\n`;
        completionMessage += `- result字段存在: ${!!taskData.result}\n`;
        if (taskData.result) {
            completionMessage += `- result.minio_urls存在: ${!!taskData.result.minio_urls}\n`;
            completionMessage += `- result.minio_urls类型: ${typeof taskData.result.minio_urls}\n`;
            completionMessage += `- result.minio_urls键数量: ${Object.keys(taskData.result.minio_urls || {}).length}\n`;
        }
    }

    console.log('📝 完整消息内容:', completionMessage);

    // 更新原始消息
    updateTaskMessage(taskId, completionMessage);

    // 显示通知
    if (Object.keys(minioUrls).length > 0) {
        showNotification('文档生成完成！点击消息中的链接下载', 'success');
    } else {
        showNotification('文档生成完成，但未找到下载链接', 'warning');
    }
}

// 🆕 从URL中提取文档名称的辅助函数
function extractDocumentName(url) {
    try {
        // 从URL中提取文件名，并解码中文字符
        const urlParts = url.split('/');
        const filename = urlParts[urlParts.length - 1];
        const nameWithoutQuery = filename.split('?')[0];

        // 解码URL编码的中文字符
        const decoded = decodeURIComponent(nameWithoutQuery);

        // 提取有意义的部分
        if (decoded.includes('完整版文档')) {
            return '完整版文档';
        } else if (decoded.includes('final_document')) {
            return '最终文档';
        } else if (decoded.includes('.md')) {
            return decoded.replace(/.*_/, '').replace('.md', '') || '文档';
        }

        return decoded;
    } catch (error) {
        console.warn('提取文档名称失败:', error);
        return null;
    }
}

// 🆕 获取友好显示名称的辅助函数
function getDisplayName(key, originalName) {
    const keyMap = {
        'document_guide': '文档指南',
        'enriched_guide': '详细指南',
        'generation_input': '生成依据',
        'final_document': '完整版文档'
    };

    return keyMap[key] || originalName || key;
}

function updateTaskProgress(taskId, taskData) {
    // 找到包含该task_id的消息
    const messages = document.querySelectorAll('.message.ai');
    let targetMessage = null;

    for (const message of messages) {
        const content = message.querySelector('.message-content');
        if (content && content.textContent.includes(taskId)) {
            targetMessage = message;
            break;
        }
    }

    if (!targetMessage) {
        console.warn(`⚠️ 未找到任务${taskId}对应的消息`);
        return;
    }

    // 添加或更新进度指示器
    let progressDiv = targetMessage.querySelector('.task-progress');
    if (!progressDiv) {
        progressDiv = document.createElement('div');
        progressDiv.className = 'task-progress';
        progressDiv.style.cssText = `
            margin-top: 10px;
            padding: 8px 12px;
            background: linear-gradient(90deg, #e3f2fd, #f3e5f5);
            border-left: 4px solid #2196f3;
            border-radius: 4px;
            font-size: 14px;
            color: #666;
        `;
        targetMessage.querySelector('.message-content').appendChild(progressDiv);
    }

    // 更新进度内容
    if (taskData.status === 'polling_started') {
        progressDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <div class="spinner" style="width: 16px; height: 16px; border: 2px solid #ccc; border-top: 2px solid #2196f3; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <span>🔄 系统正在跟踪任务进度...</span>
            </div>
        `;
    } else {
        const status = taskData.status || 'unknown';
        const progress = taskData.progress || '';
        progressDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <div class="spinner" style="width: 16px; height: 16px; border: 2px solid #ccc; border-top: 2px solid #2196f3; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <span>⏳ 状态: ${status} ${progress ? `(${progress})` : ''}</span>
            </div>
        `;
    }

    // 添加CSS动画
    if (!document.querySelector('#spinner-css')) {
        const style = document.createElement('style');
        style.id = 'spinner-css';
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
}

function updateTaskMessage(taskId, newContent) {
    console.log(`🔄 更新任务${taskId}的消息`, newContent);

    // 找到包含该task_id的消息
    const messages = document.querySelectorAll('.message.ai');
    let targetMessage = null;

    for (const message of messages) {
        const content = message.querySelector('.message-content');
        if (content && content.textContent.includes(taskId)) {
            targetMessage = message;
            break;
        }
    }

    if (!targetMessage) {
        console.warn(`⚠️ 未找到任务${taskId}对应的消息进行更新`);
        // 如果找不到原始消息，创建新消息
        addMessage('ai', newContent);
        return;
    }

    console.log(`✅ 找到目标消息，准备更新`);

    // 移除进度指示器
    const progressDiv = targetMessage.querySelector('.task-progress');
    if (progressDiv) {
        progressDiv.remove();
        console.log(`🗑️ 已移除进度指示器`);
    }

    // 更新消息内容
    const messageContent = targetMessage.querySelector('.message-content');
    if (messageContent) {
        // 保留原始消息的开头部分，添加完成信息
        const originalText = messageContent.textContent;
        const taskIdIndex = originalText.indexOf(`任务ID: ${taskId}`);

        if (taskIdIndex !== -1) {
            // 找到"📊 系统正在生成报告"这一行，替换后面的内容
            const lines = originalText.split('\n');
            const newLines = [];
            let foundProgress = false;

            for (const line of lines) {
                if (line.includes('📊 系统正在生成') || line.includes('🔄 文档正在生成')) {
                    foundProgress = true;
                    break;
                }
                newLines.push(line);
            }

            // 重新构建消息
            const baseMessage = newLines.join('\n');
            const finalMessage = baseMessage + '\n\n' + newContent;

            console.log(`📝 准备渲染的完整消息:`, finalMessage);

            // 检查是否有marked库
            if (typeof marked !== 'undefined') {
                messageContent.innerHTML = marked.parse(finalMessage);
                console.log(`✅ 使用marked.js渲染消息`);
            } else {
                // 备用：手动处理基本的Markdown链接
                console.warn(`⚠️ marked库未找到，使用备用渲染方法`);
                const htmlContent = finalMessage
                    .replace(/\n/g, '<br>')
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
                messageContent.innerHTML = htmlContent;
            }

            // 🆕 处理预览链接，将其转换为可点击的按钮
            setTimeout(() => {
                // 🔧 修复：使用更准确的方式匹配预览链接
                const previewLinks = messageContent.querySelectorAll('a[href*="preview-"]');
                previewLinks.forEach(link => {
                    // 从链接文本或href中提取taskId
                    const linkHref = link.getAttribute('href') || '';
                    const taskIdMatch = linkHref.match(/preview-([a-zA-Z0-9-]+)/);

                    if (taskIdMatch) {
                        const taskId = taskIdMatch[1];
                        console.log('🔗 找到预览链接，任务ID:', taskId);

                        link.href = 'javascript:void(0)';
                        link.onclick = (e) => {
                            e.preventDefault();
                            previewMarkdownDocument(taskId);
                        };
                        link.style.cssText = `
                            display: inline-flex;
                            align-items: center;
                            gap: 6px;
                            padding: 6px 12px;
                            background: #8b5cf6;
                            color: white;
                            text-decoration: none;
                            border-radius: 6px;
                            font-size: 14px;
                            margin: 4px 0;
                            transition: background 0.2s ease;
                            cursor: pointer;
                        `;
                        link.onmouseover = () => link.style.background = '#7c3aed';
                        link.onmouseout = () => link.style.background = '#8b5cf6';
                    }
                });
            }, 100);

            console.log(`✅ 消息内容已更新`);
        } else {
            // 如果没找到合适的分割点，直接替换
            console.log(`🔄 未找到分割点，直接替换消息内容`);

            if (typeof marked !== 'undefined') {
                messageContent.innerHTML = marked.parse(newContent);
            } else {
                const htmlContent = newContent
                    .replace(/\n/g, '<br>')
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
                messageContent.innerHTML = htmlContent;
            }
        }

        // 🔍 验证最终的HTML内容
        setTimeout(() => {
            const links = messageContent.querySelectorAll('a');
            console.log(`🔗 消息中的链接数量: ${links.length}`);
            links.forEach((link, index) => {
                console.log(`   链接${index + 1}: ${link.textContent} -> ${link.href}`);
            });
        }, 100);
    }
}

// 清理所有轮询任务（页面卸载时）
window.addEventListener('beforeunload', () => {
    for (const [taskId, interval] of pollingIntervals) {
        clearInterval(interval);
        console.log(`🧹 页面卸载，清理任务${taskId}的轮询`);
    }
    pollingIntervals.clear();
});

// 🆕 Markdown预览器功能
let currentPreviewTaskId = null;

async function previewMarkdownDocument(taskId) {
    console.log(`📖 预览文档，任务ID: ${taskId}`);

    // 检查是否有该任务的文档信息
    if (!window.taskDocuments || !window.taskDocuments[taskId]) {
        console.error(`❌ 未找到任务${taskId}的文档信息`);
        showNotification('无法找到文档信息', 'error');
        return;
    }

    const docInfo = window.taskDocuments[taskId];
    currentPreviewTaskId = taskId;

    // 显示预览窗口
    openMarkdownPreview(docInfo.name);

    // 开始获取和渲染文档
    await fetchAndRenderMarkdown(docInfo.url, docInfo.name);
}

function openMarkdownPreview(docTitle) {
    const modal = document.getElementById('markdownPreviewModal');
    const titleElement = document.getElementById('previewDocTitle');

    if (titleElement) {
        titleElement.textContent = docTitle || '文档预览';
    }

    // 显示模态窗口
    modal.classList.add('show');
    modal.style.display = 'flex';

    // 重置状态
    showPreviewLoading();

    // 禁用页面滚动
    document.body.style.overflow = 'hidden';

    console.log('📖 预览窗口已打开');
}

function closeMarkdownPreview() {
    const modal = document.getElementById('markdownPreviewModal');
    modal.classList.remove('show');
    modal.style.display = 'none';

    // 恢复页面滚动
    document.body.style.overflow = '';

    currentPreviewTaskId = null;
    console.log('📖 预览窗口已关闭');
}

function showPreviewLoading() {
    document.getElementById('previewLoading').style.display = 'flex';
    document.getElementById('previewError').style.display = 'none';
    document.getElementById('previewResult').style.display = 'none';
    document.getElementById('previewStatus').textContent = '正在获取文档...';
}

function showPreviewError(errorMsg) {
    document.getElementById('previewLoading').style.display = 'none';
    document.getElementById('previewError').style.display = 'flex';
    document.getElementById('previewResult').style.display = 'none';
    document.getElementById('previewErrorMsg').textContent = errorMsg;
    document.getElementById('previewStatus').textContent = '获取失败';
}

function showPreviewResult(htmlContent) {
    document.getElementById('previewLoading').style.display = 'none';
    document.getElementById('previewError').style.display = 'none';
    document.getElementById('previewResult').style.display = 'block';
    document.getElementById('previewResult').innerHTML = htmlContent;
    document.getElementById('previewStatus').textContent = '渲染完成';
}

async function fetchAndRenderMarkdown(url, docName) {
    try {
        console.log(`🌐 获取Markdown文档: ${url}`);
        document.getElementById('previewStatus').textContent = '正在下载文档...';

        // 🔧 添加CORS和错误处理
        const response = await fetch(url, {
            method: 'GET',
            mode: 'cors', // 明确指定CORS模式
            headers: {
                'Accept': 'text/plain, text/markdown, */*'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const markdownContent = await response.text();
        console.log(`📄 获取到Markdown内容，长度: ${markdownContent.length} 字符`);

        // 检查内容是否为空或无效
        if (!markdownContent || markdownContent.trim().length === 0) {
            throw new Error('文档内容为空');
        }

        // 渲染Markdown
        document.getElementById('previewStatus').textContent = '正在渲染文档...';

        let htmlContent;
        if (typeof marked !== 'undefined' && marked.parse) {
            // 🔧 配置marked选项 - 检查marked版本兼容性
            try {
                if (marked.setOptions) {
                    marked.setOptions({
                        breaks: true,
                        gfm: true,
                        headerIds: false,
                        mangle: false
                    });
                }
                htmlContent = marked.parse(markdownContent);
                console.log('✅ 使用marked.js渲染Markdown');
            } catch (markedError) {
                console.warn('⚠️ marked.js渲染失败，使用备用方法:', markedError);
                htmlContent = renderMarkdownFallback(markdownContent);
            }
        } else {
            console.warn('⚠️ marked.js不可用，使用备用渲染');
            htmlContent = renderMarkdownFallback(markdownContent);
        }

        // 优化图片显示
        htmlContent = enhanceImages(htmlContent);

        // 显示渲染结果
        showPreviewResult(htmlContent);

        // 添加图片懒加载和错误处理
        setTimeout(() => {
            setupImageHandling();
        }, 100);

        console.log('✅ Markdown文档渲染完成');

    } catch (error) {
        console.error('❌ 获取或渲染Markdown失败:', error);
        let errorMsg = `获取文档失败: ${error.message}`;

        // 🔧 针对常见错误提供更友好的提示
        if (error.message.includes('CORS')) {
            errorMsg = '跨域访问被阻止，请检查文档链接设置';
        } else if (error.message.includes('404')) {
            errorMsg = '文档不存在或已被删除';
        } else if (error.message.includes('403')) {
            errorMsg = '文档访问权限不足';
        }

        showPreviewError(errorMsg);
    }
}

// 🆕 备用Markdown渲染函数
function renderMarkdownFallback(markdownContent) {
    return markdownContent
        .replace(/\n/g, '<br>')
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 100%; height: auto; margin: 12px 0; border-radius: 8px;">')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
}

function enhanceImages(htmlContent) {
    // 改进图片显示，添加加载状态和错误处理
    return htmlContent.replace(
        /<img([^>]+)>/g,
        '<div class="image-container"><img$1 loading="lazy" onerror="this.parentElement.innerHTML=\'<div class=&quot;image-error&quot;>🖼️ 图片加载失败</div>\'"></div>'
    );
}

function setupImageHandling() {
    const previewResult = document.getElementById('previewResult');
    const images = previewResult.querySelectorAll('img');

    images.forEach(img => {
        // 添加加载完成样式
        img.onload = () => {
            img.style.opacity = '1';
            img.style.transition = 'opacity 0.3s ease';
        };

        // 初始透明度
        img.style.opacity = '0.7';

        // 添加点击放大功能（可选）
        img.onclick = () => {
            window.open(img.src, '_blank');
        };
        img.style.cursor = 'pointer';
        img.title = '点击查看大图';
    });
}

async function downloadOriginalDoc() {
    if (!currentPreviewTaskId || !window.taskDocuments || !window.taskDocuments[currentPreviewTaskId]) {
        showNotification('无法找到原文档信息', 'error');
        return;
    }

    const docInfo = window.taskDocuments[currentPreviewTaskId];
    window.open(docInfo.url, '_blank');
    console.log('📄 开始下载原文档:', docInfo.url);
}

async function refreshPreview() {
    if (!currentPreviewTaskId || !window.taskDocuments || !window.taskDocuments[currentPreviewTaskId]) {
        showNotification('无法刷新预览', 'error');
        return;
    }

    const docInfo = window.taskDocuments[currentPreviewTaskId];
    showPreviewLoading();
    await fetchAndRenderMarkdown(docInfo.url, docInfo.name);
    console.log('🔄 预览已刷新');
}

// 导出预览相关函数到全局作用域
window.previewMarkdownDocument = previewMarkdownDocument;
window.openMarkdownPreview = openMarkdownPreview;
window.closeMarkdownPreview = closeMarkdownPreview;
window.downloadOriginalDoc = downloadOriginalDoc;
window.refreshPreview = refreshPreview;

// 🔧 防止重复添加事件监听器
if (!window.previewEventListenersAdded) {
    // ESC键关闭预览窗口
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('markdownPreviewModal');
            if (modal && modal.classList.contains('show')) {
                closeMarkdownPreview();
            }
        }
    });

    // 点击背景关闭预览窗口
    document.addEventListener('click', (e) => {
        const modal = document.getElementById('markdownPreviewModal');
        if (e.target === modal) {
            closeMarkdownPreview();
        }
    });

    window.previewEventListenersAdded = true;
    console.log('✅ 预览器事件监听器已添加');
}

// 🆕 保存项目文件列表
function saveProjectFiles() {
    if (!currentProject || !currentProject.id) {
        // 如果没有项目信息，保存到通用文件列表
        localStorage.setItem('currentFiles', JSON.stringify(currentFiles));
        return;
    }

    // 按项目ID分别保存文件列表
    const projectFilesKey = `projectFiles_${currentProject.id}`;
    localStorage.setItem(projectFilesKey, JSON.stringify(currentFiles));
    console.log(`💾 保存项目${currentProject.name}的文件列表，共${currentFiles.length}个文件`);
}

// 🆕 加载项目文件列表
function loadProjectFiles() {
    if (!currentProject || !currentProject.id) {
        // 如果没有项目信息，加载通用文件列表
        const saved = localStorage.getItem('currentFiles');
        if (saved) {
            currentFiles = JSON.parse(saved);
        } else {
            currentFiles = [];
        }
    } else {
        // 按项目ID加载对应的文件列表
        const projectFilesKey = `projectFiles_${currentProject.id}`;
        const saved = localStorage.getItem(projectFilesKey);
        if (saved) {
            currentFiles = JSON.parse(saved);
            console.log(`📚 加载项目${currentProject.name}的文件列表，共${currentFiles.length}个文件`);
        } else {
            currentFiles = [];
            console.log(`📁 项目${currentProject.name}暂无文件，初始化为空`);
        }
    }

    updateFileTreeUI();
}

// 🆕 更新文件树UI
function updateFileTreeUI() {
    const fileTree = document.getElementById('fileTree');

    if (currentFiles.length === 0) {
        fileTree.innerHTML = `
            <div style="color: var(--text-tertiary); font-size: 12px; text-align: center; padding: 20px;">
                通过对话框📎按钮上传文件后，文件将在此显示
            </div>
        `;
        return;
    }

    // 清空并重新构建文件树
    fileTree.innerHTML = '';

    currentFiles.forEach(fileInfo => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span>${getFileIcon(fileInfo.type)}</span>
            <span>${fileInfo.name}</span>
        `;

        fileItem.onclick = () => {
            showNotification(`文件: ${fileInfo.name}\n大小: ${formatFileSize(fileInfo.size)}\n类型: ${fileInfo.type}`, 'info');
        };

        fileTree.appendChild(fileItem);
    });
}

// 🆕 清理当前项目数据
function clearProjectData() {
    console.log('🧹 清理当前项目数据');

    // 清空对话相关数据
    chatHistory = [];
    currentChatId = null;
    chatStarted = false;

    // 清空文件相关数据
    currentFiles = [];

    // 清空界面
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = '';
        chatMessages.classList.remove('show');
    }

    const welcomePrompts = document.getElementById('welcomePrompts');
    if (welcomePrompts) {
        welcomePrompts.classList.remove('hidden');
    }

    // 更新UI
    updateChatHistoryUI();
    updateFileTreeUI();

    console.log('✅ 项目数据清理完成');
}

// 🆕 切换到新项目
function switchToProject(projectId, projectName, projectType) {
    console.log(`🔄 切换到项目: ${projectName} (${projectId})`);

    // 保存当前项目的数据
    if (currentProject) {
        saveChatHistory();
        saveProjectFiles();
    }

    // 清理当前数据
    clearProjectData();

    // 设置新项目
    currentProject = {
        id: projectId,
        name: projectName,
        type: projectType || '项目'
    };

    // 保存项目信息
    localStorage.setItem('currentProject', JSON.stringify(currentProject));

    // 加载新项目数据
    loadChatHistory();
    loadProjectFiles();

    // 更新UI
    displayProjectInfo();
    updateWelcomeMessage();
    document.title = `${currentProject.name} - 工程AI助手`;

    showNotification(`已切换到项目: ${projectName}`, 'success');
    console.log(`✅ 项目切换完成: ${projectName}`);
}

// 导出项目切换函数到全局作用域
window.switchToProject = switchToProject;