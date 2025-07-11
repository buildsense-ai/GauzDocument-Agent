// 全局变量
let chatStarted = false;
let currentChatId = null;
let chatHistory = [];
let currentFiles = [];
let currentProject = null; // 当前选中的项目信息
let userSettings = {
    theme: 'light',
    showThinking: true,
    autoSave: true  // 默认开启自动保存
};

// API基础URL - 指向当前前端服务器（会代理到后端）
const API_BASE = '/api';

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

    // 加载历史记录
    loadChatHistory();
});

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
        const response = await fetch(`${API_BASE}/status`);
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

    try {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            // 如果有项目信息，添加到FormData中
            if (currentProject) {
                formData.append('project', JSON.stringify(currentProject));
            }

            const response = await fetch(`${API_BASE}/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                const fileInfo = {
                    name: data.originalName || data.original_filename,  // 兼容两种字段名
                    path: data.filePath || data.file_path,
                    reactAgentPath: data.reactAgentPath,
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

    try {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            // 如果有项目信息，添加到FormData中
            if (currentProject) {
                formData.append('project', JSON.stringify(currentProject));
            }

            const response = await fetch(`${API_BASE}/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                // 🆕 既添加到知识库，又添加到当前对话的文件列表
                const fileInfo = {
                    name: data.originalName || data.original_filename,
                    path: data.filePath || data.file_path,
                    reactAgentPath: data.reactAgentPath,
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
    const fileTree = document.getElementById('fileTree');

    // 如果是第一个文件，清空提示信息
    if (fileTree.children.length === 1 && fileTree.children[0].textContent.includes('通过对话框📎按钮上传文件后')) {
        fileTree.innerHTML = '';
    }

    // 创建文件项
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

    sendButton.disabled = !hasText && !hasFiles;
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

        // 使用非流式请求获取AI回复
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '请求失败');
        }

        console.log('🤖 收到AI回复:', result.response);
        console.log('🧠 收到思考过程数据:', result.thinking_process);

        // 🆕 构建包含思考过程的完整响应（只显示核心部分）
        let fullResponse = '';

        // 添加思考过程 - 只显示轮次和思考内容
        if (result.thinking_process && result.thinking_process.length > 0) {
            fullResponse += '🧠 **AI思考过程：**\n\n';

            result.thinking_process.forEach((step, index) => {
                switch (step.type) {
                    case 'iteration':
                        fullResponse += `\n🔄 **${step.content}**\n`;
                        break;
                    case 'thought':
                        fullResponse += `💭 **Thought:** ${step.content}\n`;
                        break;
                    // 🆕 不显示 action、observation、error 等冗长内容
                    case 'action':
                    case 'observation':
                    case 'error':
                        // 跳过这些步骤，不显示
                        break;
                }
            });

            fullResponse += '\n---\n\n';
        }

        // 添加最终答案
        fullResponse += `✅ **Final Answer:**\n${result.response}`;

        // 添加AI回复到对话
        addMessage('ai', fullResponse);

        // 标记思考过程完成
        completeThinking(thinkingProcess);

        // 保存到历史记录
        console.log('💾 保存消息到历史记录，对话ID:', currentChatId);
        saveToHistory(message, fullResponse);

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

// 生成对话ID
function generateChatId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// 添加消息
function addMessage(sender, content) {
    console.log(`💬 addMessage: ${sender} - ${content.substring(0, 50)}...`);
    console.log('🎯 当前对话ID:', currentChatId);

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

    // 🆕 支持Markdown格式的简单渲染
    let formattedContent = content
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // 加粗
        .replace(/\*(.*?)\*/g, '<em>$1</em>')             // 斜体
        .replace(/---/g, '<hr>')                          // 分隔线
        .replace(/`(.*?)`/g, '<code>$1</code>');          // 代码

    messageContent.innerHTML = formattedContent;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);

    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;

    console.log('✅ 消息已添加到界面，当前消息数量:', chatMessages.children.length);
}

// 创建思考过程
function createThinkingProcess() {
    if (!userSettings.showThinking) return null;

    const chatMessages = document.getElementById('chatMessages');
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'thinking-process';
    thinkingDiv.innerHTML = `
        <div class="thinking-header" onclick="toggleThinkingProcess(this)">
            <div class="thinking-title">
                <span>🤔</span>
                <span>AI正在思考...</span>
            </div>
            <button class="thinking-toggle">▼</button>
        </div>
        <div class="thinking-content" id="thinking-steps-container">
            <!-- 真实的思考步骤将在这里动态添加 -->
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
        const stepDiv = document.createElement('div');
        stepDiv.className = `thinking-step step-${data.status || 'completed'}`;
        stepDiv.setAttribute('data-step', data.step || 0);
        stepDiv.setAttribute('data-status', data.status || 'completed');

        // 根据状态设置不同的图标
        let statusIcon = '✅';
        if (data.status === 'running') statusIcon = '⏳';
        else if (data.status === 'error') statusIcon = '❌';

        let stepContent = `
            <div class="step-header">
                <span class="step-number">第${data.step || 0}步</span>
                <span class="step-title">${statusIcon} ${data.title || '思考'}</span>
                <span class="step-time">${new Date().toLocaleTimeString()}</span>
            </div>
            <div class="step-content">${data.content || ''}</div>
        `;

        // 如果有工具调用信息，添加到显示中
        if (data.action) {
            stepContent += `
                <div class="step-tool">
                    <strong>🔧 调用工具:</strong> <code>${data.action}</code>
                </div>
            `;
        }

        if (data.input) {
            const inputDisplay = typeof data.input === 'object' ?
                JSON.stringify(data.input, null, 2) : data.input;
            stepContent += `
                <div class="step-input">
                    <strong>📤 输入参数:</strong>
                    <pre>${inputDisplay}</pre>
                </div>
            `;
        }

        if (data.observation) {
            stepContent += `
                <div class="step-observation">
                    <strong>👁️ 执行结果:</strong>
                    <pre>${data.observation}</pre>
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

    const title = thinkingProcess.querySelector('.thinking-title span:last-child');
    title.textContent = '思考完成';

    // 3秒后自动收起
    setTimeout(() => {
        thinkingProcess.querySelector('.thinking-content').style.display = 'none';
        thinkingProcess.querySelector('.thinking-toggle').textContent = '▶';
    }, 3000);
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
    if (confirm('确定要清空所有对话历史吗？')) {
        chatHistory = [];
        currentChatId = null;
        chatStarted = false;

        // 清空对话区域
        document.getElementById('chatMessages').innerHTML = '';

        // 显示欢迎界面，隐藏聊天界面
        document.getElementById('chatMessages').classList.remove('show');
        document.getElementById('welcomePrompts').classList.remove('hidden');

        // 清空当前文件列表
        currentFiles = [];
        updateCurrentFilesUI();

        updateChatHistoryUI();
        saveChatHistory();

        showNotification('对话历史已清空', 'success');
    }
}

// 保存聊天历史
function saveChatHistory() {
    localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
}

// 加载聊天历史
function loadChatHistory() {
    const saved = localStorage.getItem('chatHistory');
    if (saved) {
        chatHistory = JSON.parse(saved);
        updateChatHistoryUI();

        // 重要：加载历史记录后，确保没有设置当前对话ID
        // 这样用户必须明确选择一个对话或新建对话
        currentChatId = null;
        chatStarted = false;
    }
}

// 打开设置面板
function openSettings() {
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

// 切换思考过程显示设置
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