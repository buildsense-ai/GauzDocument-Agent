document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const fileInput = document.getElementById('fileInput');
    const fileUploadBtn = document.getElementById('fileUploadBtn');
    const uploadedFilesContainer = document.getElementById('uploadedFiles');
    const filesList = document.getElementById('filesList');
    const statusIndicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    const minioStatusText = document.getElementById('minioStatusText');
    const toolCountBadge = document.getElementById('toolCountBadge');
    const toolsList = document.getElementById('toolsList');
    const serverCount = document.getElementById('serverCount');
    const serversList = document.getElementById('serversList');
    const refreshToolsBtn = document.getElementById('refreshTools');
    const typingIndicator = document.getElementById('typingIndicator');
    const togglePanelBtn = document.getElementById('togglePanelBtn');
    const toolsPanel = document.getElementById('toolsPanel');

    let uploadedFiles = []; // To store file objects for the API call

    // --- API Helper ---
    async function apiFetch(endpoint, options = {}) {
        try {
            const response = await fetch(`/api${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: '发生了未知错误' }));
                throw new Error(errorData.error || `HTTP错误! 状态码: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API请求错误 ${endpoint}:`, error);
            showInlineError(error.message);
            throw error;
        }
    }

    // --- Core Functions ---
    async function initializeApp() {
        console.log("正在初始化应用程序...");
        setStatus('connecting', '连接中...');
        try {
            const data = await apiFetch('/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            if (data.success) {
                setStatus('connected', '已连接');
                updateServersUI(data.servers);
                await refreshTools(); // Fetch tools after connecting
            } else {
                setStatus('disconnected', '连接失败');
            }
            await checkMinIOStatus();
        } catch (error) {
            setStatus('disconnected', '连接错误');
        }
    }

    async function sendMessage() {
        const messageText = chatInput.value.trim();
        if (messageText === '') return;

        appendMessage(messageText, 'user-message');
        chatInput.value = '';
        chatInput.disabled = true;
        sendBtn.disabled = true;
        typingIndicator.style.display = 'inline-block';

        // 使用非流式模式
        try {
            await sendRegularMessage(messageText);
        } finally {
            chatInput.disabled = false;
            sendBtn.disabled = false;
            typingIndicator.style.display = 'none';
            chatInput.focus();
        }
    }

    async function sendRegularMessage(messageText) {
        const payload = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: messageText,
                files: uploadedFiles,
            }),
        };
        const data = await apiFetch('/chat', payload);

        if (data.success) {
            appendMessage(data.response, 'system-message', data);
            // Clear uploaded files after successful message send
            uploadedFiles = [];
            updateUploadedFilesUI();
        }
    }

    // 已删除流式处理代码 - 恢复到原始的非流式输出

    async function refreshTools() {
        try {
            const data = await apiFetch('/tools');
            if (data.success) {
                updateToolsUI(data.tools);
            }
        } catch (error) {
            console.error("刷新工具失败");
        }
    }

    async function checkMinIOStatus() {
        try {
            const data = await apiFetch('/minio/health');
            minioStatusText.textContent = data.health.status === 'ready' ? 'MinIO: 在线' : 'MinIO: 离线';
            minioStatusText.parentElement.style.color = data.health.status === 'ready' ? '#28a745' : '#dc3545';
        } catch (error) {
            minioStatusText.textContent = 'MinIO: 离线';
            minioStatusText.parentElement.style.color = '#dc3545';
        }
    }

    // --- Panel Toggle Function ---
    function togglePanel() {
        const isCollapsed = toolsPanel.classList.contains('collapsed');

        if (isCollapsed) {
            toolsPanel.classList.remove('collapsed');
            togglePanelBtn.classList.add('active');
            togglePanelBtn.innerHTML = '<i class="fas fa-cog"></i><span>工具面板</span>';
        } else {
            toolsPanel.classList.add('collapsed');
            togglePanelBtn.classList.remove('active');
            togglePanelBtn.innerHTML = '<i class="fas fa-cog"></i><span>工具面板</span>';
        }
    }

    // --- Error Handling ---
    function showInlineError(message) {
        // Create error message element
        const errorElement = document.createElement('div');
        errorElement.classList.add('message', 'system-message', 'error-message');
        errorElement.innerHTML = `
            <div class="message-icon">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div class="message-content">
                <strong>错误:</strong> ${message}
            </div>
        `;

        chatMessages.appendChild(errorElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.remove();
            }
        }, 5000);
    }

    async function handleFileUpload(event) {
        const files = event.target.files;
        if (files.length === 0) return;

        fileUploadBtn.classList.add('uploading');

        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            try {
                const data = await apiFetch('/upload', { method: 'POST', body: formData });
                if (data.success) {
                    uploadedFiles.push({
                        name: data.originalName,
                        path: data.filePath,
                        reactAgentPath: data.reactAgentPath,
                        type: data.mimetype,
                    });
                }
            } catch (error) {
                showInlineError(`上传文件 ${file.name} 失败: ${error.message}`);
            }
        }

        fileUploadBtn.classList.remove('uploading');
        updateUploadedFilesUI();
        fileInput.value = ''; // Reset file input
    }


    // --- UI Update Functions ---
    function setStatus(status, text) {
        statusIndicator.className = 'status-indicator ' + status;
        statusText.textContent = text;
    }

    function appendMessage(text, type, data = {}) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', type);

        const iconClass = type === 'user-message' ? 'fa-user' : 'fa-robot';

        // Use a library like 'marked' in a real app to safely parse markdown
        const processedText = text.replace(/\[Download(.*?)\]\((.*?)\)/g, `<a href="$2" target="_blank" class="download-link">Download$1</a>`);

        messageElement.innerHTML = `
            <div class="message-icon"><i class="fas ${iconClass}"></i></div>
            <div class="message-content">${processedText}</div>
        `;

        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function updateToolsUI(tools) {
        toolCountBadge.textContent = tools.length;
        toolsList.innerHTML = '';
        if (tools.length === 0) {
            toolsList.innerHTML = '<div class="list-item-placeholder">暂无可用工具</div>';
            return;
        }
        tools.forEach(tool => {
            const toolElement = document.createElement('div');
            toolElement.classList.add('tool-item');
            toolElement.innerHTML = `
                <span class="tool-name">${tool.name}</span>
                <span class="tool-server">${tool.serverName}</span>
            `;
            toolElement.title = tool.description;
            toolsList.appendChild(toolElement);
        });
    }

    function updateServersUI(servers) {
        serverCount.textContent = servers.length;
        serversList.innerHTML = '';
        if (servers.length === 0) {
            serversList.innerHTML = '<div class="list-item-placeholder">暂无配置的服务器</div>';
            return;
        }
        servers.forEach(server => {
            const serverElement = document.createElement('div');
            serverElement.classList.add('server-item');
            serverElement.innerHTML = `
                <div class="server-status-indicator ${server.connected ? 'connected' : ''}"></div>
                <span class="server-name">${server.name}</span>
            `;
            serversList.appendChild(serverElement);
        });
    }

    function updateUploadedFilesUI() {
        filesList.innerHTML = '';
        if (uploadedFiles.length > 0) {
            uploadedFiles.forEach((file, index) => {
                const fileElement = document.createElement('div');
                fileElement.className = 'file-item';
                fileElement.textContent = file.name;
                const removeBtn = document.createElement('button');
                removeBtn.innerHTML = '&times;';
                removeBtn.onclick = () => {
                    uploadedFiles.splice(index, 1);
                    updateUploadedFilesUI();
                };
                fileElement.appendChild(removeBtn);
                filesList.appendChild(fileElement);
            });
            uploadedFilesContainer.style.display = 'block';
        } else {
            uploadedFilesContainer.style.display = 'none';
        }
    }

    function showErrorModal(message) {
        document.getElementById('errorMessage').textContent = message;
        document.getElementById('errorModal').style.display = 'flex';
    }


    // --- Event Listeners ---
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    chatInput.addEventListener('input', () => {
        sendBtn.disabled = chatInput.value.trim() === '' && uploadedFiles.length === 0;
    });

    fileUploadBtn.addEventListener('click', () => fileInput.click());
    togglePanelBtn.addEventListener('click', togglePanel);
    fileInput.addEventListener('change', handleFileUpload);

    refreshToolsBtn.addEventListener('click', async () => {
        await initializeApp();
    });

    // --- Init ---
    initializeApp();
});

// For modals
function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
} 