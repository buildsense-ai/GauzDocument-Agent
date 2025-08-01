// 全局变量
let chatStarted = false;
let currentChatId = null;
let chatHistory = [];
let currentFiles = [];
let currentProject = null; // 当前选中的项目信息

// 🆕 数据库相关状态
let isHistoryLoaded = false;
let totalMessagesInDb = 0;
let currentPage = 1;
let isUploading = false; // 是否正在上传文件到MinIO
let uploadStartTime = null; // 记录上传开始时间
let uploadPhase = null; // 记录上传阶段: 'request', 'waiting', 'processing'

// 🔄 任务轮询相关状态
let pollingIntervals = new Map(); // 存储所有活动的轮询任务

let userSettings = {
    theme: 'light',
    showThinking: true,
    autoSave: true  // 默认开启自动保存
};

// API基础URL - 指向当前前端服务器（会代理到后端）
const API_BASE = '/api';

// 🆕 通用API请求函数，自动添加项目ID和项目名称到请求头
async function apiRequest(url, options = {}) {
    const headers = {
        ...options.headers
    };

    // 如果body不是FormData，添加Content-Type
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    // 🆕 如果有当前项目，添加项目ID和名称到请求头
    if (currentProject && (currentProject.id || currentProject.name)) {
        if (currentProject.id) {
            headers['X-Project-ID'] = currentProject.id;
        }
        if (currentProject.name) {
            headers['X-Project-Name'] = encodeURIComponent(currentProject.name); // 编码中文字符
        }
        console.log('📤 API请求添加项目信息:', {
            id: currentProject.id,
            name: currentProject.name
        }, 'URL:', url);
    }

    return fetch(url, {
        ...options,
        headers
    });
}

// 初始化应用
document.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 页面加载完成，开始初始化...');

    // 初始化项目环境
    initializeProject();

    // 初始化用户设置
    initializeSettings();

    // 初始化事件监听器（重要：绑定按钮点击事件）
    initializeEventListeners();

    // 检查连接状态
    checkConnectionStatus();

    // 检查marked.js状态（延迟检查以确保加载完成）
    setTimeout(() => {
        checkMarkedJSStatus();

        // 如果marked.js仍未加载，显示友好提示
        if (typeof marked === 'undefined' && !window.markedLoadFailed) {
            console.warn('🕐 marked.js仍在加载中，将在加载完成后自动启用');
        }
    }, 1000);

    // 🔧 添加全局测试函数
    window.testImageRendering = function (markdownText) {
        console.log('🧪 测试图片渲染功能');
        console.log('📝 输入内容:', markdownText);

        let htmlContent;
        if (typeof marked !== 'undefined' && !window.markedLoadFailed) {
            try {
                // 适配不同版本的API
                if (typeof marked.parse === 'function') {
                    htmlContent = marked.parse(markdownText);
                } else if (typeof marked === 'function') {
                    htmlContent = marked(markdownText);
                } else {
                    throw new Error('无法识别的marked.js API');
                }
                console.log('✅ marked.js渲染结果:', htmlContent);
            } catch (e) {
                console.warn('⚠️ marked.js失败，使用备用方法:', e);
                htmlContent = renderMarkdownFallback(markdownText);
            }
        } else {
            console.log('💼 使用备用渲染器');
            htmlContent = renderMarkdownFallback(markdownText);
        }

        htmlContent = enhanceImages(htmlContent);
        console.log('🎨 最终渲染结果:', htmlContent);

        // 创建临时div显示结果
        const testDiv = document.createElement('div');
        testDiv.innerHTML = htmlContent;
        testDiv.style.cssText = 'border: 2px solid #007bff; padding: 15px; margin: 10px; background: #f8f9fa; border-radius: 8px;';
        document.body.appendChild(testDiv);
        console.log('📺 测试结果已添加到页面底部');

        setTimeout(() => {
            if (confirm('移除测试元素？')) {
                testDiv.remove();
            }
        }, 5000);
    };
    console.log('🔧 图片渲染测试函数已添加到 window.testImageRendering()');

    // 🔧 添加marked.js诊断函数
    window.diagnoseMarkedJS = function () {
        console.log('🩺 开始诊断marked.js状态');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

        // 基础检查
        console.log('1️⃣ 基础检查:');
        console.log('   typeof marked:', typeof marked);
        console.log('   window.markedLoadFailed:', window.markedLoadFailed);

        if (typeof marked !== 'undefined') {
            console.log('2️⃣ API兼容性检查:');
            console.log('   marked()函数:', typeof marked === 'function');
            console.log('   marked.parse():', typeof marked.parse === 'function');
            console.log('   marked.setOptions():', typeof marked.setOptions === 'function');
            console.log('   marked.use():', typeof marked.use === 'function');

            console.log('3️⃣ 测试渲染:');
            try {
                const testMd = '**测试** *图片* ![test](https://via.placeholder.com/100x50.png?text=TEST)';
                let result;

                if (typeof marked.parse === 'function') {
                    result = marked.parse(testMd);
                    console.log('   ✅ marked.parse() 成功');
                } else if (typeof marked === 'function') {
                    result = marked(testMd);
                    console.log('   ✅ marked() 成功');
                } else {
                    console.log('   ❌ 无可用的渲染方法');
                    return;
                }

                console.log('   渲染结果:', result);
                console.log('   包含图片标签:', result.includes('<img'));
            } catch (e) {
                console.log('   ❌ 渲染测试失败:', e);
            }
        } else {
            console.log('❌ marked.js 未加载或加载失败');
        }

        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log('💡 如果marked.js有问题，可以运行 resetMarkedJS() 重新加载');
    };

    // 🔧 添加重置函数
    window.resetMarkedJS = function () {
        console.log('🔄 尝试重新加载marked.js');
        window.markedLoadFailed = false;
        delete window.marked;
        loadMarkedFromBackup();
    };

    console.log('🔧 诊断函数已添加: window.diagnoseMarkedJS() 和 window.resetMarkedJS()');

    // 🆕 添加持久化诊断函数
    window.diagnosePersistence = function () {
        console.log('🔍 开始诊断持久化状态');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

        console.log('1️⃣ 项目信息:');
        console.log('   currentProject:', currentProject);
        console.log('   localStorage项目:', localStorage.getItem('currentProject'));

        console.log('2️⃣ 聊天历史:');
        console.log('   内存中历史数量:', chatHistory.length);
        console.log('   数据库加载状态:', isHistoryLoaded);

        console.log('3️⃣ 文件列表:');
        console.log('   内存中文件数量:', currentFiles.length);
        if (currentProject) {
            const key = `projectFiles_${currentProject.id}`;
            const saved = localStorage.getItem(key);
            console.log('   localStorage文件数量:', saved ? JSON.parse(saved).length : 0);
        }

        console.log('4️⃣ 数据源状态:');
        console.log('   - 项目信息来源: URL参数 + localStorage + 数据库验证');
        console.log('   - 聊天历史来源: 数据库 (API) -> localStorage备用');
        console.log('   - 文件列表来源: 数据库 (API) -> localStorage备用');

        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    };

    // 🆕 添加数据重新加载函数
    window.reloadProjectData = function () {
        console.log('🔄 重新加载项目数据...');
        if (currentProject) {
            Promise.all([
                loadChatHistory(),
                loadProjectFiles()
            ]).then(() => {
                console.log('✅ 项目数据重新加载完成');
                showNotification('项目数据已重新加载', 'success');
            }).catch(error => {
                console.error('❌ 重新加载失败:', error);
                showNotification('重新加载失败', 'error');
            });
        } else {
            console.warn('⚠️ 没有当前项目，无法重新加载');
        }
    };

    console.log('🔧 持久化诊断函数已添加: window.diagnosePersistence() 和 window.reloadProjectData()');

    // 启动上传状态监控（每5秒检查一次）
    setInterval(checkUploadTimeout, 5000);
    console.log('🔍 上传状态监控已启动');

    // 添加快捷键重置上传状态 (Ctrl+Shift+R)
    document.addEventListener('keydown', function (e) {
        if (e.ctrlKey && e.shiftKey && e.key === 'R') {
            e.preventDefault();
            resetUploadStatus();
        }
    });

    console.log('✅ 初始化完成');
});

// 初始化项目信息
function initializeProject() {
    // 首先从localStorage中读取项目信息
    const savedProject = localStorage.getItem('currentProject');

    // 🆕 从URL参数中读取项目信息 - 支持项目名称优先
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project');
    const projectName = urlParams.get('projectName');
    const projectType = urlParams.get('projectType');

    // 🆕 优先使用项目名称作为主要标识
    if (projectName) {
        currentProject = {
            id: projectId,
            name: projectName,
            type: projectType || '项目'
        };

        // 将项目信息保存到localStorage
        localStorage.setItem('currentProject', JSON.stringify(currentProject));

        console.log('🏗️ 从URL初始化项目（优先使用项目名称）:', currentProject);
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

        // 🆕 加载项目专属的对话历史和文件列表 (异步加载)
        Promise.all([
            loadChatHistory(),
            loadProjectFiles()
        ]).then(() => {
            console.log(`🎯 项目${currentProject.name}的所有数据加载完成`);
        }).catch(error => {
            console.error('❌ 项目数据加载出现问题:', error);
        });

        console.log(`🔄 项目${currentProject.name}数据加载完成`);
    } else {
        console.log('📋 未指定项目，使用通用模式');
        // 在通用模式下仍然加载数据 (异步加载)
        Promise.all([
            loadChatHistory(),
            loadProjectFiles()
        ]).then(() => {
            console.log('🎯 通用模式数据加载完成');
        }).catch(error => {
            console.error('❌ 通用模式数据加载出现问题:', error);
        });
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

    // 检查元素是否存在
    if (!uploadZone) {
        console.log('⚠️ uploadZone元素不存在，跳过拖拽上传设置');
        return;
    }

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
    uploadStartTime = Date.now();
    uploadPhase = 'request';
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
            console.log('📤 开始网络请求（临时文件）:', file.name);
            uploadPhase = 'waiting';
            const response = await apiRequest(`/api/upload`, {
                method: 'POST',
                body: formData,
                headers: {} // 清空Content-Type，让浏览器自动设置multipart/form-data
            });

            console.log('📥 收到响应，开始解析JSON');
            uploadPhase = 'processing';
            const data = await response.json();

            if (data.success) {
                const fileInfo = {
                    name: data.originalName || data.original_filename,  // 兼容两种字段名
                    path: data.minio_path,  // 🌐 使用MinIO路径
                    reactAgentPath: data.minio_path,  // 🌐 AI agent使用MinIO路径
                    type: data.mimetype,
                    size: data.size,
                    isTemporary: true,
                    verified: data.verified || false,  // 验证状态
                    verificationDetails: data.verification_details  // 验证详情
                };

                currentFiles.push(fileInfo);
                console.log('📎 临时文件已添加到currentFiles:', fileInfo.name, '当前文件数量:', currentFiles.length);
                console.log('🔍 文件验证状态:', fileInfo.verified, fileInfo.verificationDetails);
                updateCurrentFilesUI();

                // 更新项目统计 - 文件数量
                updateProjectStats('files');

                // 添加到左侧文件树
                addFileToTree(fileInfo);

                // 🆕 保存更新后的文件列表
                saveProjectFiles();

                // 🆕 显示验证状态的通知
                const verifyStatus = data.verified ? '✅ 已验证' : '⚠️ 未验证';
                showNotification(`文件 "${fileInfo.name}" 上传成功 ${verifyStatus}`, 'success');
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
        uploadStartTime = null;
        uploadPhase = null;
        updateSendButton(); // 更新发送按钮状态
        console.log('🔄 临时文件上传完成，isUploading 重置为 false');
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
    uploadStartTime = Date.now();
    uploadPhase = 'request';
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
            console.log('📤 开始网络请求（持久化文件）:', file.name);
            uploadPhase = 'waiting';
            const response = await apiRequest(`/api/upload`, {
                method: 'POST',
                body: formData,
                headers: {} // 清空Content-Type，让浏览器自动设置multipart/form-data
            });

            console.log('📥 收到响应，开始解析JSON');
            uploadPhase = 'processing';
            const data = await response.json();

            if (data.success) {
                // 🆕 既添加到知识库，又添加到当前对话的文件列表
                const fileInfo = {
                    name: data.originalName || data.original_filename,
                    path: data.minio_path,  // 🌐 使用MinIO路径
                    reactAgentPath: data.minio_path,  // 🌐 AI agent使用MinIO路径
                    type: data.mimetype,
                    size: data.size,
                    isTemporary: false,  // 标记为持久化文件
                    verified: data.verified || false,  // 验证状态
                    verificationDetails: data.verification_details  // 验证详情
                };

                // 添加到当前对话文件列表
                currentFiles.push(fileInfo);
                console.log('📎 文件已添加到currentFiles:', fileInfo.name, '当前文件数量:', currentFiles.length);
                console.log('🔍 文件验证状态:', fileInfo.verified, fileInfo.verificationDetails);
                updateCurrentFilesUI();

                // 更新项目统计 - 文件数量
                updateProjectStats('files');

                // 添加到左侧文件树
                addFileToTree(fileInfo);

                // 🆕 显示验证状态的通知
                const verifyStatus = data.verified ? '✅ 已验证' : '⚠️ 未验证';
                showNotification(`文件 "${fileInfo.name}" 已上传并添加到对话中 ${verifyStatus}`, 'success');

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
        uploadStartTime = null;
        uploadPhase = null;
        updateSendButton(); // 更新发送按钮状态
        console.log('🔄 持久化文件上传完成，isUploading 重置为 false');
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

// 重置上传状态（保险措施）
function resetUploadStatus() {
    if (isUploading) {
        console.warn('⚠️ 强制重置上传状态');
        console.warn('重置前状态：isUploading =', isUploading, '阶段：', uploadPhase);
        isUploading = false;
        uploadStartTime = null;
        uploadPhase = null;
        updateSendButton();
        showNotification('上传状态已重置', 'info');
    }
}

// 检查上传超时（增强版）
function checkUploadTimeout() {
    if (isUploading && uploadStartTime) {
        const elapsed = Date.now() - uploadStartTime;

        // 30秒警告，60秒强制重置
        if (elapsed > 60000) { // 60秒超时
            console.error('❌ 上传严重超时（60秒），强制重置状态');
            console.error('可能原因：网络请求卡住、后端API无响应、或前端异常');
            resetUploadStatus();
            showNotification('上传严重超时，已强制重置', 'error');
        } else if (elapsed > 30000) { // 30秒警告
            console.warn('⚠️ 上传时间较长（30秒+），请检查网络连接');
            console.warn('当前状态：isUploading =', isUploading, '阶段：', uploadPhase, '已用时：', Math.round(elapsed / 1000), '秒');
        }
    }
}

// 更新发送按钮状态
function updateSendButton() {
    const inputField = document.getElementById('inputField');
    const sendButton = document.getElementById('sendButton');

    const hasText = inputField.value.trim().length > 0;
    const hasFiles = currentFiles.length > 0;

    // 检查上传超时
    checkUploadTimeout();

    // 🚀 关键修改：在上传期间禁用发送按钮并显示漏斗
    if (isUploading) {
        sendButton.disabled = true;
        sendButton.innerHTML = '⏳'; // 漏斗状态
        sendButton.title = '正在上传文件到MinIO...';
        console.log('🔒 发送按钮锁定中，isUploading =', isUploading);
    } else {
        sendButton.disabled = !hasText && !hasFiles;
        sendButton.innerHTML = '发送'; // 正常状态
        sendButton.title = '发送消息';
        console.log('🔓 发送按钮已解锁，isUploading =', isUploading);
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
                            // 🔧 修复：正确处理final_answer，显示AI的最终回答
                            console.log('📋 流式中收到final_answer，准备显示完整结果');
                            console.log('📥 Final Answer详细信息:');
                            console.log('   - 接收长度:', data.content.length, '字符');
                            console.log('   - 接收行数:', data.content.split('\n').length, '行');
                            console.log('   - 开头100字符:', data.content.substring(0, 100));

                            // 完成思考过程显示
                            completeThinking(thinkingProcess);

                            // 🆕 检测是否包含task_id，如果是文档生成任务，启动轮询 - 使用简化的检测方式
                            const finalAnswer = data.content;
                            console.log('🔍 检查Final Answer是否包含任务ID...');
                            console.log('📝 Final Answer完整内容:', finalAnswer);

                            const taskIdMatch = finalAnswer.match(/任务ID[：:]\s*([a-zA-Z0-9_-]+)/);
                            if (taskIdMatch) {
                                const taskId = taskIdMatch[1];
                                console.log('🎯 检测到文档生成任务ID:', taskId);

                                // 显示初始响应
                                addMessage('ai', finalAnswer);

                                // 开始轮询任务状态
                                startTaskPolling(taskId, finalAnswer);
                            } else {
                                console.log('❌ 未检测到任务ID，将作为普通响应处理');
                                // 普通响应，直接显示
                                addMessage('ai', finalAnswer);
                            }

                            // 关闭事件源
                            eventSource.close();
                            resolve(finalAnswer);
                            return;

                        case 'stream_end':
                            // 🔧 处理流结束信号
                            console.log('🎉 流式对话结束:', data.message);
                            completeThinking(thinkingProcess);
                            eventSource.close();

                            // 如果没有收到final_answer，显示默认消息
                            if (!eventSource.finalAnswerReceived) {
                                console.warn('⚠️ 没有收到final_answer，显示默认消息');
                                addMessage('ai', '✅ 处理完成，但未获得最终结果');
                                resolve('处理完成');
                            }
                            return;

                        case 'complete':
                        case 'timeout':
                        case 'error':
                        case 'session_ended':
                            console.log(`🎉 思考流程结束: ${data.type}`);
                            if (data.type === 'session_ended') {
                                console.log('ℹ️ 会话已结束或过期，这是正常现象');
                            }
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

                                // 🆕 检测是否包含task_id，如果是文档生成任务，启动轮询 - 使用简化的检测方式
                                console.log('🔍 检查Final Answer是否包含任务ID...');
                                console.log('📝 Final Answer完整内容:', finalAnswer);

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
                                    console.log('❌ 未检测到任务ID，将作为普通响应处理');
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

    // 🆕 检测内容是否已经是HTML格式
    const isAlreadyHtml = content.includes('<p>') || content.includes('<strong>') || content.includes('<a href=');

    if (isAlreadyHtml) {
        console.log('✅ 检测到已渲染的HTML，直接使用');
        // 直接使用预渲染的HTML内容
        messageContent.innerHTML = content;
    } else {
        // 🆕 优先使用marked.js，备用完整Markdown渲染
        if (typeof marked !== 'undefined' && !window.markedLoadFailed) {
            console.log('✅ 使用marked.js渲染消息');
            try {
                let htmlContent;

                // 检查API类型并适配
                if (typeof marked.parse === 'function') {
                    // 新版API (v4+)
                    if (marked.setOptions) {
                        marked.setOptions({
                            breaks: true,
                            gfm: true,
                            headerIds: false,
                            mangle: false
                        });
                    }
                    htmlContent = marked.parse(content);
                } else if (typeof marked === 'function') {
                    // 旧版API兼容
                    marked.setOptions && marked.setOptions({
                        breaks: true,
                        gfm: true,
                        headerIds: false,
                        mangle: false
                    });
                    htmlContent = marked(content);
                } else {
                    throw new Error('无法识别的marked.js API');
                }

                // 应用图片增强处理
                htmlContent = enhanceImages(htmlContent);
                messageContent.innerHTML = htmlContent;
                console.log('🎨 marked.js渲染完成');
            } catch (markedError) {
                console.warn('⚠️ marked.js渲染失败，使用备用方法:', markedError);
                // 如果marked.js出错，使用备用方法
                let htmlContent = renderMarkdownFallback(content);
                htmlContent = enhanceImages(htmlContent);
                messageContent.innerHTML = htmlContent;
            }
        } else {
            console.log('⚠️ marked.js不可用，使用备用渲染方法');
            // 🔧 使用完整的备用渲染方法，包含图片处理
            let htmlContent = renderMarkdownFallback(content);
            htmlContent = enhanceImages(htmlContent);
            messageContent.innerHTML = htmlContent;
        }
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

// 保存聊天历史 (本地备用)
function saveChatHistory() {
    if (!currentProject || !currentProject.id) {
        // 如果没有项目信息，保存到通用历史
        localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
        return;
    }

    // 🆕 按项目ID分别保存对话历史
    const projectHistoryKey = `chatHistory_${currentProject.id}`;
    localStorage.setItem(projectHistoryKey, JSON.stringify(chatHistory));
    console.log(`💾 保存项目${currentProject.name}的对话历史到localStorage，共${chatHistory.length}条对话`);
}

// 🆕 从数据库加载聊天历史 (真正的数据库实现)
async function loadChatHistory() {
    try {
        console.log(`📚 从数据库加载对话历史...`);

        let apiUrl;
        if (currentProject && currentProject.name) {
            // 有项目时，获取项目特定的历史
            const projectIdentifier = encodeURIComponent(currentProject.name);
            apiUrl = `/api/projects/${projectIdentifier}/current-session?by_name=true&limit=20`;
        } else {
            // 没有项目时，尝试加载通用历史（如果有API支持）
            console.log('📝 没有项目信息，初始化为空历史');
            chatHistory = [];
            updateChatHistoryUI();
            return;
        }

        const response = await apiRequest(apiUrl);
        const result = await response.json();

        if (result.success && result.messages) {
            // 清空现有聊天历史
            chatHistory = [];
            const chatMessages = document.getElementById('chatMessages');

            // 处理消息数据
            if (result.messages.length > 0) {
                console.log(`📨 处理${result.messages.length}条数据库消息...`);

                // 显示聊天界面，隐藏欢迎界面
                if (chatMessages) {
                    chatMessages.innerHTML = '';
                    chatMessages.classList.add('show');
                }

                const welcomePrompts = document.getElementById('welcomePrompts');
                if (welcomePrompts) {
                    welcomePrompts.style.display = 'none';
                }

                // 创建单一对话对象来包含所有消息
                const sessionInfo = result.messages[0].session_info;
                const chatTitle = sessionInfo?.title ||
                    (result.messages.find(m => m.role === 'user')?.content?.substring(0, 30) + '...' || '新对话');

                const chatObject = {
                    id: sessionInfo?.id || 'current-session',
                    title: chatTitle,
                    startTime: new Date(sessionInfo?.created_at || result.messages[0].created_at),
                    messages: []
                };

                // 按时间顺序处理消息
                result.messages.reverse().forEach(msg => {
                    const messageData = {
                        id: msg.id,
                        sender: msg.role, // 映射为switchToChat期望的字段
                        content: msg.content,
                        timestamp: new Date(msg.created_at),
                        thinking_process: msg.thinking_data,
                        rendered_html: msg.rendered_html,
                        extra_data: msg.extra_data
                    };

                    // 添加到对话对象的消息列表
                    chatObject.messages.push(messageData);

                    // 直接渲染到聊天界面
                    if (msg.role === 'user') {
                        addMessage('user', msg.content);
                    } else if (msg.role === 'assistant') {
                        let content;

                        // 🆕 检查是否是任务完成消息，如果是，实时渲染
                        if (msg.extra_data && msg.extra_data.task_result && msg.extra_data.task_id) {
                            console.log('🎨 发现任务完成消息，实时渲染:', msg.extra_data.task_id);

                            // 从原始数据实时渲染
                            content = renderTaskCompletionFromResult(msg.extra_data.task_result, msg.extra_data.task_id);

                            console.log('✅ 任务完成消息已重新渲染，包含实时链接');
                        }
                        // 🔄 兼容旧版本：检查旧的minio_urls格式
                        else if (msg.extra_data && msg.extra_data.task_id && msg.extra_data.minio_urls) {
                            console.log('🔄 重建旧版本文档信息:', msg.extra_data.task_id);

                            // 重建window.taskDocuments，使预览功能可用
                            window.taskDocuments = window.taskDocuments || {};

                            const taskId = msg.extra_data.task_id;
                            const finalDocUrl = msg.extra_data.minio_urls.final_document;

                            if (finalDocUrl) {
                                // 从URL提取文件名
                                const urlParts = finalDocUrl.split('/');
                                const fileName = urlParts[urlParts.length - 1] || '完整版文档';

                                window.taskDocuments[taskId] = {
                                    url: finalDocUrl,
                                    name: fileName
                                };

                                console.log('✅ 旧版本文档信息已重建:', taskId, fileName);
                            }

                            // 使用预渲染的HTML或原始内容
                            content = msg.rendered_html || msg.content;
                        }
                        else {
                            // 普通消息，使用预渲染的HTML或原始内容
                            content = msg.rendered_html || msg.content;
                        }

                        addMessage('assistant', content);
                    }
                });

                // 将对话对象添加到历史记录
                chatHistory.push(chatObject);
                currentChatId = chatObject.id;

                chatStarted = true;
                console.log(`✅ 成功从数据库加载${result.messages.length}条历史消息`);

                // 获取当前会话的文件列表
                if (result.messages[0] && result.messages[0].files) {
                    const dbFiles = result.messages[0].files;
                    if (dbFiles.length > 0) {
                        console.log(`📁 从数据库加载${dbFiles.length}个文件记录`);
                        // 转换数据库文件记录为前端格式
                        currentFiles = dbFiles.map(file => ({
                            name: file.display_name || file.original_name,
                            path: file.minio_path,
                            reactAgentPath: file.minio_path,
                            type: file.mime_type,
                            size: file.file_size,
                            isTemporary: false,
                            verified: file.status === 'ready',
                            dbId: file.id // 保存数据库ID
                        }));
                        updateCurrentFilesUI();
                        updateFileTreeUI();
                    }
                }
            } else {
                console.log(`📝 项目${currentProject ? currentProject.name : '当前'}暂无对话历史`);
                // 显示欢迎界面
                const welcomePrompts = document.getElementById('welcomePrompts');
                if (welcomePrompts) {
                    welcomePrompts.style.display = 'block';
                }
            }

            isHistoryLoaded = true;
            totalMessagesInDb = result.total || 0;
        } else {
            throw new Error(result.error || '加载历史消息失败');
        }

    } catch (error) {
        console.error('❌ 从数据库加载对话历史失败:', error);
        console.error('错误详情:', error.message);

        // 降级到localStorage备用方案
        console.log('🔄 尝试从localStorage加载备用历史...');
        try {
            const fallbackKey = currentProject ? `chatHistory_${currentProject.id}` : 'chatHistory';
            const savedHistory = localStorage.getItem(fallbackKey);
            if (savedHistory) {
                chatHistory = JSON.parse(savedHistory);
                console.log(`📚 从localStorage恢复${chatHistory.length}条历史记录`);
                // 重新渲染历史消息
                if (chatHistory.length > 0) {
                    const chatMessages = document.getElementById('chatMessages');
                    if (chatMessages) {
                        chatMessages.innerHTML = '';
                        chatMessages.classList.add('show');
                    }
                    chatHistory.forEach(msg => {
                        addMessage(msg.role || msg.sender, msg.content);
                    });
                    chatStarted = true;
                }
            } else {
                chatHistory = [];
            }
        } catch (fallbackError) {
            console.error('❌ localStorage备用方案也失败:', fallbackError);
            chatHistory = [];
        }

        showNotification('从数据库加载历史失败，已切换到本地备用数据', 'warning');
    }

    updateChatHistoryUI();
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
async function startTaskPolling(taskId, originalMessage) {
    console.log(`🔄 开始轮询任务 ${taskId}`);
    console.log(`📊 当前活跃轮询任务数量: ${pollingIntervals.size}`);
    console.log(`📋 轮询配置: 每10秒查询一次，最多30分钟`);

    let pollCount = 0;
    const maxPolls = 180; // 最多轮询30分钟 (180 * 10s)

    // 如果已经在轮询这个任务，先清除
    if (pollingIntervals.has(taskId)) {
        console.log(`⚠️ 任务${taskId}已在轮询中，先清除旧轮询`);
        clearInterval(pollingIntervals.get(taskId));
    }

    // 创建轮询任务
    const pollInterval = setInterval(async () => {
        pollCount++;
        console.log(`📋 第${pollCount}次查询任务${taskId}状态...`);
        console.log(`🌐 请求URL: ${API_BASE}/tasks/${taskId}`);

        try {
            const response = await apiRequest(`${API_BASE}/tasks/${taskId}`);
            console.log(`📡 API响应状态: ${response.status}`);

            if (!response.ok) {
                console.error(`❌ 查询任务状态失败: ${response.status}`);

                try {
                    const errorData = await response.json();
                    console.error(`❌ 错误详情:`, errorData);

                    // 根据不同的错误类型处理
                    if (response.status === 404) {
                        // 任务不存在，立即停止轮询
                        console.log(`📋 任务${taskId}不存在，停止轮询`);
                        clearTaskPolling(taskId);
                        updateTaskMessage(taskId, `⚠️ 任务不存在或已过期: ${errorData.error || '任务未找到'}`);
                        return;
                    } else if (response.status === 500) {
                        // 服务器内部错误，可以重试但有限制
                        console.log(`🔄 服务器内部错误，继续重试...`);
                        if (pollCount >= 10) {
                            console.log(`❌ 服务器错误重试次数过多，停止轮询`);
                            clearTaskPolling(taskId);
                            updateTaskMessage(taskId, `❌ 文档生成服务异常: ${errorData.error || '服务暂时不可用'}`);
                            return;
                        }
                    } else {
                        // 其他错误，有限重试
                        console.log(`⚠️ 其他错误 (${response.status})，继续重试...`);
                        if (pollCount >= 5) {
                            console.log(`❌ 任务${taskId}查询失败次数过多，停止轮询`);
                            clearTaskPolling(taskId);
                            updateTaskMessage(taskId, `⚠️ 任务状态查询失败: ${errorData.error || '请稍后手动检查'}`);
                            return;
                        }
                    }
                } catch (parseError) {
                    // 无法解析错误响应，使用原始文本
                    const errorText = await response.text();
                    console.error(`❌ 错误详情: ${errorText}`);

                    if (pollCount >= 5) {
                        console.log(`❌ 任务${taskId}查询失败次数过多，停止轮询`);
                        clearTaskPolling(taskId);
                        updateTaskMessage(taskId, '⚠️ 任务状态查询失败，请稍后手动检查');
                        return;
                    }
                }
                return;
            }

            const taskData = await response.json();
            console.log(`📊 任务${taskId}状态:`, taskData);

            // 检查响应格式和任务状态
            if (!taskData.success && taskData.error) {
                console.error(`❌ 任务${taskId}查询失败:`, taskData.error);
                clearTaskPolling(taskId);
                updateTaskMessage(taskId, `❌ 任务查询失败: ${taskData.error}`);
                return;
            }

            // 检查任务状态 - 根据API文档格式
            const status = taskData.status?.toLowerCase();
            const progress = taskData.progress || '';

            console.log(`📊 任务${taskId}详细状态:`);
            console.log(`   - status: ${status}`);
            console.log(`   - progress: ${progress}`);
            console.log(`   - result存在: ${!!taskData.result}`);
            console.log(`   - error: ${taskData.error || 'none'}`);

            // 如果有错误信息，处理错误
            if (taskData.error && status !== 'completed') {
                console.error(`❌ 任务${taskId}执行出错:`, taskData.error);
                clearTaskPolling(taskId);
                updateTaskMessage(taskId, `❌ 任务执行失败: ${taskData.error}`);
                return;
            }

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

                // 根据不同状态提供更详细的进度信息
                let progressInfo = { status: status };
                if (progress) {
                    progressInfo.progress = progress;
                }
                if (taskData.updated_at) {
                    progressInfo.updated_at = taskData.updated_at;
                }

                updateTaskProgress(taskId, progressInfo);

                // 对于长时间运行的任务，定期输出状态
                if (pollCount % 6 === 0) { // 每60秒输出一次详细状态
                    console.log(`📈 任务${taskId}运行状态汇总 (第${pollCount}次查询):`);
                    console.log(`   - 当前状态: ${status}`);
                    console.log(`   - 进度信息: ${progress || '无'}`);
                    console.log(`   - 已轮询: ${Math.floor(pollCount * 10 / 60)}分钟`);
                }
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

    // 🆕 直接保存原始result数据到数据库，不保存渲染后的HTML
    await saveTaskResultToDatabase(taskId, taskData, completionMessage);

    // 更新前端显示（不保存到数据库）
    updateTaskMessage(taskId, completionMessage, false);

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
        const updatedAt = taskData.updated_at;

        // 根据状态选择合适的图标和颜色
        let statusIcon = '⏳';
        let statusColor = '#2196f3';
        let statusText = status;

        switch (status.toLowerCase()) {
            case 'pending':
                statusIcon = '📋';
                statusText = '排队中';
                break;
            case 'running':
            case 'processing':
                statusIcon = '⚙️';
                statusText = '处理中';
                break;
            case 'generating':
                statusIcon = '📝';
                statusText = '生成中';
                break;
            case 'finalizing':
                statusIcon = '🔄';
                statusText = '完善中';
                break;
            default:
                statusText = status;
        }

        // 格式化更新时间
        let timeInfo = '';
        if (updatedAt) {
            try {
                const updateTime = new Date(updatedAt);
                const now = new Date();
                const diffSeconds = Math.floor((now - updateTime) / 1000);

                if (diffSeconds < 60) {
                    timeInfo = `(${diffSeconds}秒前更新)`;
                } else if (diffSeconds < 3600) {
                    timeInfo = `(${Math.floor(diffSeconds / 60)}分钟前更新)`;
                } else {
                    timeInfo = `(${updateTime.toLocaleTimeString()}更新)`;
                }
            } catch (e) {
                console.warn('时间格式化失败:', e);
            }
        }

        progressDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <div class="spinner" style="width: 16px; height: 16px; border: 2px solid #ccc; border-top: 2px solid ${statusColor}; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <span>${statusIcon} 状态: ${statusText} ${progress ? `- ${progress}` : ''} ${timeInfo}</span>
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

function updateTaskMessage(taskId, newContent, shouldPersist = false) {
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
            if (typeof marked !== 'undefined' && !window.markedLoadFailed) {
                try {
                    let htmlContent;

                    // 检查API类型并适配
                    if (typeof marked.parse === 'function') {
                        // 新版API
                        if (marked.setOptions) {
                            marked.setOptions({
                                breaks: true,
                                gfm: true,
                                headerIds: false,
                                mangle: false
                            });
                        }
                        htmlContent = marked.parse(finalMessage);
                    } else if (typeof marked === 'function') {
                        // 旧版API兼容
                        marked.setOptions && marked.setOptions({
                            breaks: true,
                            gfm: true,
                            headerIds: false,
                            mangle: false
                        });
                        htmlContent = marked(finalMessage);
                    } else {
                        throw new Error('无法识别的marked.js API');
                    }

                    htmlContent = enhanceImages(htmlContent);
                    messageContent.innerHTML = htmlContent;
                    console.log(`✅ 使用marked.js渲染任务消息`);
                } catch (markedError) {
                    console.warn(`⚠️ marked.js渲染失败，使用备用方法:`, markedError);
                    let htmlContent = renderMarkdownFallback(finalMessage);
                    htmlContent = enhanceImages(htmlContent);
                    messageContent.innerHTML = htmlContent;
                }
            } else {
                // 🔧 使用完整的备用渲染方法，包含图片处理
                console.warn(`⚠️ marked库未找到，使用备用渲染方法`);
                let htmlContent = renderMarkdownFallback(finalMessage);
                htmlContent = enhanceImages(htmlContent);
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

        // 🆕 持久化更新后的消息到历史记录
        if (shouldPersist && userSettings.autoSave && currentChatId) {
            console.log(`💾 开始持久化任务${taskId}的完成消息`);
            updateMessageInHistory(taskId, taskIdIndex !== -1 ? finalMessage : newContent).catch(error => {
                console.error(`❌ 持久化消息失败:`, error);
            });
        }
    }
}

// 🆕 更新历史记录中的消息内容并持久化
async function updateMessageInHistory(taskId, updatedContent) {
    console.log(`💾 更新历史记录中任务${taskId}的消息`);

    // 找到当前对话记录
    const currentChat = chatHistory.find(c => c.id === currentChatId);
    if (!currentChat) {
        console.warn(`⚠️ 未找到当前对话记录，无法更新历史记录`);
        return;
    }

    // 查找包含该taskId的AI消息
    let messageFound = false;
    let updatedMessage = null;
    for (let i = currentChat.messages.length - 1; i >= 0; i--) {
        const message = currentChat.messages[i];
        if (message.sender === 'ai' && message.content.includes(taskId)) {
            console.log(`✅ 找到包含任务ID的AI消息，索引: ${i}`);
            console.log(`📝 原消息长度: ${message.content.length} 字符`);
            console.log(`📝 新消息长度: ${updatedContent.length} 字符`);

            // 更新消息内容，保持其他属性不变
            message.content = updatedContent;
            message.updatedAt = new Date(); // 添加更新时间标记

            updatedMessage = message;
            messageFound = true;
            console.log(`✅ 已更新历史记录中的消息内容`);
            break;
        }
    }

    if (!messageFound) {
        console.warn(`⚠️ 未在历史记录中找到包含任务ID ${taskId} 的AI消息`);
        return;
    }

    // 更新对话历史UI
    updateChatHistoryUI();

    // 🆕 保存到数据库
    if (currentProject && currentProject.name) {
        try {
            console.log(`💾 保存更新后的消息到数据库...`);

            const response = await apiRequest(`${API_BASE}/projects/${encodeURIComponent(currentProject.name)}/messages`, {
                method: 'POST',
                body: JSON.stringify({
                    role: 'assistant',
                    content: updatedContent,
                    extra_data: {
                        task_id: taskId,
                        message_type: 'task_completion',
                        updated_at: new Date().toISOString()
                    },
                    by_name: true
                })
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`✅ 消息已保存到数据库: 消息ID=${data.message_id}`);
                showNotification('任务完成信息已保存', 'success');
            } else {
                throw new Error(`保存失败: ${response.status}`);
            }
        } catch (error) {
            console.error(`❌ 保存消息到数据库失败:`, error);
            showNotification('保存消息失败，但本地已更新', 'warning');

            // 备用：保存到localStorage
            saveChatHistory();
        }
    } else {
        console.warn(`⚠️ 没有项目信息，使用localStorage备用保存`);
        // 备用：保存到localStorage
        saveChatHistory();
    }

    console.log(`💾 任务${taskId}的完成消息已持久化`);
}

// 🆕 保存原始任务结果到数据库
async function saveTaskResultToDatabase(taskId, taskData, renderedContent) {
    console.log(`💾 保存任务${taskId}的原始结果到数据库...`);

    if (!currentProject || !currentProject.name) {
        console.warn(`⚠️ 没有项目信息，无法保存到数据库`);
        return;
    }

    try {
        // 构建简洁的消息内容（不包含具体链接，因为链接会实时渲染）
        const simpleContent = '✅ 文档生成完成！\n\n📊 系统已完成文档生成，点击下方链接查看和下载。';

        // 构建包含完整原始数据的extra_data
        const extraData = {
            task_id: taskId,
            message_type: 'task_completion',
            task_result: taskData.result || {}, // 保存完整的result对象
            task_status: taskData.status,
            task_progress: taskData.progress,
            created_at: taskData.created_at,
            updated_at: taskData.updated_at,
            rendered_content: renderedContent, // 保存当前渲染的内容作为备用
            saved_at: new Date().toISOString()
        };

        console.log('💾 保存的extra_data:', extraData);

        const response = await apiRequest(`${API_BASE}/projects/${encodeURIComponent(currentProject.name)}/messages`, {
            method: 'POST',
            body: JSON.stringify({
                role: 'assistant',
                content: simpleContent,
                extra_data: extraData,
                by_name: true
            })
        });

        if (response.ok) {
            const data = await response.json();
            const messageId = data.data?.message_id || data.message_id || 'unknown';
            console.log(`✅ 任务结果已保存到数据库: 消息ID=${messageId}`);
            showNotification('文档生成结果已保存', 'success');
        } else {
            throw new Error(`保存失败: ${response.status}`);
        }
    } catch (error) {
        console.error(`❌ 保存任务结果到数据库失败:`, error);
        showNotification('保存失败，但前端已更新', 'warning');

        // 备用：保存到localStorage
        saveChatHistory();
    }
}

// 🆕 从原始任务结果渲染文档完成消息
function renderTaskCompletionFromResult(taskResult, taskId) {
    console.log('🎨 从原始结果渲染任务完成消息:', taskResult);

    const files = taskResult.files || {};
    const minioUrls = taskResult.minio_urls || {};
    const message = taskResult.message || '';

    // 构建完成消息（与handleTaskCompletion相同的逻辑）
    let completionMessage = '✅ 文档生成完成！\n\n';

    if (message) {
        completionMessage += `📝 ${message}\n\n`;
    }

    // 处理下载链接
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
            }
            completionMessage += '\n';
        }

        completionMessage += '💡 点击链接即可下载文档';
    } else {
        completionMessage += '⚠️ 文档已生成，但未找到下载链接。\n\n';
        completionMessage += '📋 **调试信息：**\n';
        completionMessage += `- 任务ID: ${taskId}\n`;
        completionMessage += `- files存在: ${!!taskResult.files}\n`;
        completionMessage += `- minio_urls存在: ${!!taskResult.minio_urls}\n`;
        if (taskResult.minio_urls) {
            completionMessage += `- minio_urls键数量: ${Object.keys(taskResult.minio_urls).length}\n`;
        }
    }

    return completionMessage;
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
        if (typeof marked !== 'undefined' && !window.markedLoadFailed) {
            // 🔧 配置marked选项 - 检查marked版本兼容性
            try {
                // 适配不同版本的API
                if (typeof marked.parse === 'function') {
                    // 新版API
                    if (marked.setOptions) {
                        marked.setOptions({
                            breaks: true,
                            gfm: true,
                            headerIds: false,
                            mangle: false
                        });
                    }
                    htmlContent = marked.parse(markdownContent);
                } else if (typeof marked === 'function') {
                    // 旧版API兼容
                    marked.setOptions && marked.setOptions({
                        breaks: true,
                        gfm: true,
                        headerIds: false,
                        mangle: false
                    });
                    htmlContent = marked(markdownContent);
                } else {
                    throw new Error('无法识别的marked.js API');
                }

                console.log('✅ 使用marked.js渲染Markdown预览');
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

// 🆕 备用Markdown渲染函数 (增强版)
function renderMarkdownFallback(markdownContent) {
    console.log('🔧 使用备用Markdown渲染器');
    return markdownContent
        .replace(/\n/g, '<br>')
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code style="background-color: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-family: monospace;">$1</code>')
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 400px; width: auto; height: auto; margin: 12px 0; border-radius: 8px; display: block; cursor: pointer;" onclick="window.open(\'$2\', \'_blank\')" title="点击查看大图">')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color: #007bff; text-decoration: none;">$1</a>');
}

// 检查marked.js状态
function checkMarkedJSStatus() {
    if (typeof marked !== 'undefined') {
        console.log('✅ marked.js已成功加载');

        // 检查API兼容性
        const apiInfo = {
            marked_function: typeof marked === 'function',
            parse_method: typeof marked.parse === 'function',
            setOptions_method: typeof marked.setOptions === 'function',
            use_method: typeof marked.use === 'function'
        };

        console.log('📋 marked.js API信息:', apiInfo);

        // 尝试获取版本信息
        try {
            if (marked.getDefaults) {
                const defaults = marked.getDefaults();
                console.log('⚙️ marked.js配置:', defaults);
            }
        } catch (e) {
            console.log('ℹ️ 无法获取默认配置');
        }

        return true;
    } else if (window.markedLoadFailed) {
        console.warn('❌ marked.js加载完全失败，将使用备用渲染器');
        return false;
    } else {
        console.warn('⚠️ marked.js尚未加载完成');
        return false;
    }
}

function enhanceImages(htmlContent) {
    // 辅助函数：检测是否为图片URL或图片相关链接
    function isImageLink(url, linkText) {
        // 检查URL是否指向图片格式
        const imageExtensions = /\.(jpg|jpeg|png|gif|bmp|webp|svg)(\?.*)?$/i;
        if (imageExtensions.test(url)) {
            return true;
        }

        // 检查链接文本是否包含图片关键词
        const imageKeywords = /(?:图|示意图|截图|图片|图像|示例|样例|效果图|设计图|布局图|结构图|流程图|架构图|原理图|配置图)/i;
        if (imageKeywords.test(linkText)) {
            return true;
        }

        // 检查URL是否来自已知的图片服务器或包含图片路径
        const imageServerPatterns = [
            /43\.139\.19\.144:900/,  // 用户提到的图片服务器
            /\/images?\//i,
            /\/img\//i,
            /\/static\//i,
            /\/uploads?\//i,
            /\/assets?\//i,
            /_image/i,
            /image_/i
        ];

        return imageServerPatterns.some(pattern => pattern.test(url));
    }

    // 首先处理指向图片的普通链接，将其转换为图片显示
    let enhanced = htmlContent.replace(
        /<a\s+href="([^"]+)"\s+target="_blank"[^>]*>([^<]+)<\/a>/gi,
        function (match, url, linkText) {
            if (isImageLink(url, linkText)) {
                console.log('🖼️ 检测到图片链接:', linkText, '->', url);
                // 生成唯一ID避免冲突
                const containerId = `img-container-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                // 将错误和加载处理移到data属性中，避免模板字符串在HTML属性中的问题
                return `<div class="image-container" id="${containerId}">
                    <img src="${url}" 
                         alt="${linkText}"
                         loading="lazy" 
                         style="max-width: 400px; width: auto; height: auto; margin: 12px 0; border-radius: 8px; display: block; opacity: 0; cursor: pointer;"
                         data-link-text="${linkText.replace(/"/g, '&quot;')}" 
                         data-url="${url.replace(/"/g, '&quot;')}"
                         onload="this.style.opacity='1'; this.previousElementSibling?.remove(); console.log('✅ 图片加载成功:', this.dataset.linkText);"
                         onerror="handleImageError(this)"
                         onclick="window.open('${url}', '_blank')"
                         title="点击查看大图">
                    <div class="image-loading" style="padding: 20px; text-align: center; color: #666; font-size: 14px;">⏳ 加载图片中: ${linkText}...</div>
                </div>`;
            }
            // 如果不是图片链接，保持原样
            return match;
        }
    );

    // 然后处理标准的img标签，添加加载状态和错误处理
    enhanced = enhanced.replace(
        /<img([^>]+)>/g,
        function (match, attributes) {
            // 检查是否已经被上面的逻辑处理过
            if (match.includes('class="image-container"') || attributes.includes('data-link-text')) {
                return match;
            }

            // 生成唯一ID
            const containerId = `img-container-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            // 添加默认样式和错误处理
            const enhancedImg = `<div class="image-container" id="${containerId}">
                <img${attributes} 
                     loading="lazy" 
                     style="max-width: 400px; width: auto; height: auto; margin: 12px 0; border-radius: 8px; display: block; cursor: pointer;"
                     onload="this.style.opacity='1'; this.previousElementSibling?.remove(); console.log('✅ 图片加载成功');"
                     onerror="handleImageError(this)"
                     onclick="this.src && window.open(this.src, '_blank')"
                     title="点击查看大图">
                <div class="image-loading" style="padding: 20px; text-align: center; color: #666; font-size: 14px;">⏳ 图片加载中...</div>
            </div>`;
            return enhancedImg;
        }
    );

    // 最后处理纯文本中的图片名称，将其转换为可点击的图片或下载链接
    enhanced = enhanceTextImageNames(enhanced);

    return enhanced;
}

// 🔧 图片错误处理函数
function handleImageError(imgElement) {
    console.log('❌ 图片加载失败:', imgElement.src);

    const container = imgElement.parentElement;
    const linkText = imgElement.dataset?.linkText || '未知图片';
    const url = imgElement.dataset?.url || imgElement.src;

    // 创建错误显示元素
    const errorHtml = `
        <div class="image-error" style="padding: 20px; text-align: center; color: #888; border: 1px dashed #ccc; border-radius: 8px; margin: 12px 0;">
            🖼️ 图片加载失败
            ${linkText !== '未知图片' ? `<br><strong>${linkText}</strong>` : ''}
            <br><small>请检查图片链接是否有效</small>
            <br><a href="${url}" target="_blank" style="color: #007bff; text-decoration: none;">点击查看原链接</a>
        </div>
    `;

    container.innerHTML = errorHtml;
}

// 🆕 处理纯文本中的图片名称
function enhanceTextImageNames(htmlContent) {
    console.log('🔍 开始处理纯文本图片名称');

    let enhanced = htmlContent;

    // 更精确的匹配策略：寻找独立的图片名称行
    const lines = enhanced.split('<br>');
    const processedLines = lines.map(line => {
        // 跳过已经包含HTML标签的行
        if (line.includes('<') && line.includes('>')) {
            return line;
        }

        // 移除可能的列表符号和空格
        const cleanLine = line.replace(/^[-*•]\s*/, '').trim();

        // 图片名称的识别模式 - 更精确的匹配
        const imageNamePatterns = [
            /^(.*?(?:示意图|效果图|设计图|布局图|结构图|流程图|架构图|原理图|配置图|平面图|立面图|剖面图|详图|节点图)\d*)$/i,
            /^(.*?关系图.*)$/i,
            /^(防护措施示意图\d*)$/i,
            /^(.*?图\s*\d+)$/i
        ];

        for (const pattern of imageNamePatterns) {
            const match = cleanLine.match(pattern);
            if (match && match[1]) {
                const imageName = match[1].trim();

                // 过滤掉太短或太长的匹配
                if (imageName.length < 3 || imageName.length > 50) {
                    continue;
                }

                // 构造可能的图片URL
                const possibleUrls = [
                    `http://43.139.19.144:9000/images/${encodeURIComponent(imageName)}.png`,
                    `http://43.139.19.144:9000/images/${encodeURIComponent(imageName)}.jpg`,
                    `http://43.139.19.144:9000/images/${encodeURIComponent(imageName)}.jpeg`,
                    `http://43.139.19.144:9000/images/${encodeURIComponent(imageName)}.pdf`,
                    `http://43.139.19.144:9000/documents/${encodeURIComponent(imageName)}.png`,
                    `http://43.139.19.144:9000/documents/${encodeURIComponent(imageName)}.jpg`,
                    `http://43.139.19.144:9000/documents/${encodeURIComponent(imageName)}.jpeg`,
                    `http://43.139.19.144:9000/documents/${encodeURIComponent(imageName)}.pdf`
                ];

                console.log('🖼️ 检测到纯文本图片名称:', imageName);

                // 创建一个可点击的图片预览组件
                return `<div class="text-image-reference" style="margin: 8px 0; padding: 12px; background: #f8f9fa; border-left: 4px solid #007bff; border-radius: 4px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 20px;">🖼️</span>
                        <span style="font-weight: 500; color: #333;">${imageName}</span>
                        <button onclick="tryLoadTextImage('${imageName.replace(/'/g, "\\'")}', ${JSON.stringify(possibleUrls)})" 
                                style="background: #007bff; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-left: auto;">
                            查看图片
                        </button>
                    </div>
                </div>`;
            }
        }

        return line;
    });

    return processedLines.join('<br>');
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

// 🆕 尝试加载纯文本中提到的图片
async function tryLoadTextImage(imageName, possibleUrls) {
    console.log('🔍 尝试加载图片:', imageName, possibleUrls);

    // 创建模态框显示加载状态
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        background: rgba(0,0,0,0.8); z-index: 10000; display: flex; 
        align-items: center; justify-content: center;
    `;
    modal.id = 'imageLoadModal';

    const content = document.createElement('div');
    content.style.cssText = `
        background: white; padding: 20px; border-radius: 8px; 
        max-width: 90vw; max-height: 90vh; overflow: auto;
        position: relative;
    `;

    // 关闭按钮
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✕';
    closeBtn.style.cssText = `
        position: absolute; top: 10px; right: 10px; 
        background: none; border: none; font-size: 20px; 
        cursor: pointer; color: #666;
    `;
    closeBtn.onclick = () => document.body.removeChild(modal);

    content.appendChild(closeBtn);

    // 加载状态
    const loadingDiv = document.createElement('div');
    loadingDiv.innerHTML = `<div style="text-align: center; padding: 40px;">
        <div style="font-size: 24px; margin-bottom: 16px;">🔍</div>
        <div>正在查找图片: ${imageName}</div>
        <div style="margin-top: 8px; font-size: 14px; color: #666;">尝试多个可能的位置...</div>
    </div>`;
    content.appendChild(loadingDiv);

    modal.appendChild(content);
    document.body.appendChild(modal);

    // 逐个尝试URL
    for (let i = 0; i < possibleUrls.length; i++) {
        const url = possibleUrls[i];
        console.log(`🔍 尝试URL ${i + 1}/${possibleUrls.length}:`, url);

        try {
            // 更新加载状态
            loadingDiv.innerHTML = `<div style="text-align: center; padding: 40px;">
                <div style="font-size: 24px; margin-bottom: 16px;">🔍</div>
                <div>正在查找图片: ${imageName}</div>
                <div style="margin-top: 8px; font-size: 14px; color: #666;">尝试位置 ${i + 1}/${possibleUrls.length}</div>
                <div style="margin-top: 4px; font-size: 12px; color: #888; word-break: break-all;">${url}</div>
            </div>`;

            const response = await fetch(url, { method: 'HEAD' });
            if (response.ok) {
                console.log('✅ 找到图片:', url);

                // 根据文件类型显示内容
                const contentType = response.headers.get('content-type') || '';

                if (contentType.startsWith('image/')) {
                    // 显示图片
                    content.innerHTML = `
                        <button onclick="document.body.removeChild(document.getElementById('imageLoadModal'))" 
                                style="position: absolute; top: 10px; right: 10px; background: none; border: none; font-size: 20px; cursor: pointer; color: #666;">✕</button>
                        <div style="text-align: center; padding: 20px;">
                            <h3 style="margin-bottom: 16px;">${imageName}</h3>
                            <img src="${url}" style="max-width: 100%; height: auto; border-radius: 8px;" alt="${imageName}">
                            <div style="margin-top: 16px;">
                                <a href="${url}" target="_blank" style="color: #007bff; text-decoration: none;">🔗 在新窗口中打开</a>
                            </div>
                        </div>
                    `;
                } else {
                    // 非图片文件，提供下载链接
                    content.innerHTML = `
                        <button onclick="document.body.removeChild(document.getElementById('imageLoadModal'))" 
                                style="position: absolute; top: 10px; right: 10px; background: none; border: none; font-size: 20px; cursor: pointer; color: #666;">✕</button>
                        <div style="text-align: center; padding: 40px;">
                            <div style="font-size: 48px; margin-bottom: 16px;">📄</div>
                            <h3>${imageName}</h3>
                            <p style="color: #666; margin: 16px 0;">检测到文档文件</p>
                            <a href="${url}" target="_blank" 
                               style="display: inline-block; background: #007bff; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none;">
                               📥 下载/查看文件
                            </a>
                        </div>
                    `;
                }
                return;
            }
        } catch (error) {
            console.log(`❌ URL ${i + 1} 失败:`, error.message);
        }
    }

    // 所有URL都失败了
    console.log('❌ 所有图片URL都失败了');
    content.innerHTML = `
        <button onclick="document.body.removeChild(document.getElementById('imageLoadModal'))" 
                style="position: absolute; top: 10px; right: 10px; background: none; border: none; font-size: 20px; cursor: pointer; color: #666;">✕</button>
        <div style="text-align: center; padding: 40px;">
            <div style="font-size: 48px; margin-bottom: 16px;">❌</div>
            <h3>未找到图片: ${imageName}</h3>
            <p style="color: #666; margin: 16px 0;">在以下位置都未找到相应的图片文件：</p>
            <div style="text-align: left; background: #f8f9fa; padding: 16px; border-radius: 4px; margin: 16px 0; max-height: 200px; overflow-y: auto;">
                ${possibleUrls.map(url => `<div style="font-family: monospace; font-size: 12px; margin: 4px 0; word-break: break-all;">${url}</div>`).join('')}
            </div>
            <p style="color: #888; font-size: 14px;">请联系管理员确认图片是否已上传到服务器</p>
        </div>
    `;
}

// 导出函数到全局作用域
window.tryLoadTextImage = tryLoadTextImage;

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

// 🆕 保存项目文件列表 (本地备用)
function saveProjectFiles() {
    if (!currentProject || !currentProject.id) {
        // 如果没有项目信息，保存到通用文件列表
        localStorage.setItem('currentFiles', JSON.stringify(currentFiles));
        return;
    }

    // 按项目ID分别保存文件列表
    const projectFilesKey = `projectFiles_${currentProject.id}`;
    localStorage.setItem(projectFilesKey, JSON.stringify(currentFiles));
    console.log(`💾 保存项目${currentProject.name}的文件列表到localStorage，共${currentFiles.length}个文件`);
}

// 🆕 从数据库加载项目文件列表 (真正的数据库实现)
async function loadProjectFiles() {
    try {
        if (!currentProject || !currentProject.name) {
            console.log('📁 没有项目信息，初始化为空文件列表');
            currentFiles = [];
            updateFileTreeUI();
            return;
        }

        console.log(`📚 从数据库加载项目${currentProject.name}的文件列表...`);

        // 调用后端API获取项目文件
        const projectIdentifier = encodeURIComponent(currentProject.name);
        const response = await apiRequest(`/api/projects/${projectIdentifier}/files?by_name=true`);
        const result = await response.json();

        if (result.success && result.files) {
            // 转换数据库文件记录为前端格式
            currentFiles = result.files.map(file => ({
                name: file.display_name || file.original_name,
                path: file.minio_path,
                reactAgentPath: file.minio_path,
                type: file.mime_type,
                size: file.file_size,
                isTemporary: false,
                verified: file.status === 'ready',
                dbId: file.id,
                uploadedAt: file.uploaded_at
            }));

            console.log(`✅ 成功从数据库加载${currentFiles.length}个文件记录`);

            // 同时更新localStorage作为备用
            const projectFilesKey = `projectFiles_${currentProject.id}`;
            localStorage.setItem(projectFilesKey, JSON.stringify(currentFiles));
        } else {
            console.log(`📁 项目${currentProject.name}暂无文件记录`);
            currentFiles = [];
        }

    } catch (error) {
        console.error('❌ 从数据库加载文件列表失败:', error);

        // 降级到localStorage备用方案
        console.log('🔄 尝试从localStorage加载备用文件列表...');
        try {
            const projectFilesKey = currentProject?.id ? `projectFiles_${currentProject.id}` : 'currentFiles';
            const saved = localStorage.getItem(projectFilesKey);
            if (saved) {
                currentFiles = JSON.parse(saved);
                console.log(`📚 从localStorage恢复${currentFiles.length}个文件记录`);
            } else {
                currentFiles = [];
            }
        } catch (fallbackError) {
            console.error('❌ localStorage备用方案也失败:', fallbackError);
            currentFiles = [];
        }

        showNotification('从数据库加载文件列表失败，已切换到本地备用数据', 'warning');
    }

    updateFileTreeUI();
    updateCurrentFilesUI();
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

// 🧪 调试用：测试任务轮询功能
window.debugTaskPolling = function (testTaskId = 'test_' + Date.now()) {
    console.log(`🧪 开始测试任务轮询功能，任务ID: ${testTaskId}`);

    // 模拟一个任务ID返回的消息
    const testMessage = `✅ 文档生成任务已提交！

**任务信息：**
- 任务ID: ${testTaskId}
- 状态: 处理中
- 说明: 测试任务已创建

文档正在生成中，完成后将提供下载链接。`;

    // 添加测试消息到界面
    addMessage('ai', testMessage);

    // 开始轮询测试
    startTaskPolling(testTaskId, testMessage);

    console.log(`🧪 测试说明:`);
    console.log(`   1. 这会启动一个对不存在任务的轮询测试`);
    console.log(`   2. 应该很快看到"任务不存在"的错误`);
    console.log(`   3. 检查控制台输出以验证错误处理逻辑`);
    console.log(`   4. 使用 clearTaskPolling('${testTaskId}') 来手动停止轮询`);

    return testTaskId;
};

// 🧪 调试用：手动清除任务轮询
window.debugClearPolling = function (taskId) {
    if (!taskId) {
        console.log('🧹 清除所有轮询任务');
        for (const [tid] of pollingIntervals) {
            clearTaskPolling(tid);
        }
        console.log(`✅ 已清除 ${pollingIntervals.size} 个轮询任务`);
    } else {
        console.log(`🧹 清除任务 ${taskId} 的轮询`);
        clearTaskPolling(taskId);
    }
};

// 🧪 调试用：查看当前轮询状态
window.debugPollingStatus = function () {
    console.log(`📊 当前轮询状态:`);
    console.log(`   - 活跃轮询任务数: ${pollingIntervals.size}`);
    if (pollingIntervals.size > 0) {
        console.log(`   - 任务列表:`, Array.from(pollingIntervals.keys()));
    }
    return {
        activeCount: pollingIntervals.size,
        taskIds: Array.from(pollingIntervals.keys())
    };
};

console.log('🧪 调试功能已加载！');
console.log('   - debugTaskPolling() - 测试任务轮询');
console.log('   - debugClearPolling(taskId) - 清除轮询');
console.log('   - debugPollingStatus() - 查看轮询状态');

// 🆕 文档编辑器功能
let currentEditingContent = '';
let currentEditingUrl = '';
let currentEditingName = '';

// 打开文档编辑器
function openDocumentEditor() {
    console.log('📝 打开文档编辑器');
    
    // 检查是否有当前预览的文档
    if (!currentPreviewTaskId || !window.taskDocuments || !window.taskDocuments[currentPreviewTaskId]) {
        showNotification('请先预览一个文档再进行编辑', 'warning');
        return;
    }
    
    const docInfo = window.taskDocuments[currentPreviewTaskId];
    currentEditingUrl = docInfo.url;
    currentEditingName = docInfo.name;
    
    // 设置编辑器标题
    document.getElementById('editorDocTitle').textContent = `编辑: ${currentEditingName}`;
    document.getElementById('editorStatus').textContent = '正在加载文档内容...';
    
    // 显示编辑器模态窗口
    const modal = document.getElementById('documentEditorModal');
    modal.classList.add('show');
    modal.style.display = 'flex';
    
    // 禁用页面滚动
    document.body.style.overflow = 'hidden';
    
    // 加载文档内容到编辑器
    loadDocumentForEditing();
    
    console.log('✅ 文档编辑器已打开');
}

// 加载文档内容到编辑器
async function loadDocumentForEditing() {
    try {
        console.log(`📥 加载文档内容: ${currentEditingUrl}`);
        
        const response = await fetch(currentEditingUrl, {
            method: 'GET',
            mode: 'cors',
            headers: {
                'Accept': 'text/plain, text/markdown, */*'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const markdownContent = await response.text();
        currentEditingContent = markdownContent;
        
        // 设置编辑器内容
        const editor = document.getElementById('markdownEditor');
        editor.value = markdownContent;
        
        // 更新状态和统计
        document.getElementById('editorStatus').textContent = '文档加载完成，可以开始编辑';
        updateEditorStats();
        
        // 初始预览
        updateEditorPreview();
        
        // 设置编辑器事件监听
        setupEditorEventListeners();
        
        console.log('✅ 文档内容加载完成');
        
    } catch (error) {
        console.error('❌ 加载文档内容失败:', error);
        document.getElementById('editorStatus').textContent = `加载失败: ${error.message}`;
        showNotification('文档内容加载失败', 'error');
    }
}

// 设置编辑器事件监听
function setupEditorEventListeners() {
    const editor = document.getElementById('markdownEditor');
    
    // 移除之前的监听器（如果存在）
    editor.removeEventListener('input', handleEditorInput);
    editor.removeEventListener('scroll', handleEditorScroll);
    
    // 添加新的监听器
    editor.addEventListener('input', handleEditorInput);
    editor.addEventListener('scroll', handleEditorScroll);
    
    console.log('✅ 编辑器事件监听器已设置');
}

// 处理编辑器输入
function handleEditorInput() {
    updateEditorStats();
    updateEditorPreview();
    
    // 标记内容已修改
    const status = document.getElementById('editorStatus');
    if (!status.textContent.includes('已修改')) {
        status.textContent = '文档已修改，记得保存';
    }
}

// 处理编辑器滚动（同步预览滚动）
function handleEditorScroll() {
    const editor = document.getElementById('markdownEditor');
    const preview = document.getElementById('editorPreview');
    
    // 计算滚动比例
    const scrollRatio = editor.scrollTop / (editor.scrollHeight - editor.clientHeight);
    
    // 同步预览滚动
    if (isFinite(scrollRatio)) {
        preview.scrollTop = scrollRatio * (preview.scrollHeight - preview.clientHeight);
    }
}

// 更新编辑器统计信息
function updateEditorStats() {
    const editor = document.getElementById('markdownEditor');
    const content = editor.value;
    
    const charCount = content.length;
    const lineCount = content.split('\n').length;
    
    document.getElementById('editorWordCount').textContent = `字符数: ${charCount}`;
    document.getElementById('editorLineCount').textContent = `行数: ${lineCount}`;
}

// 更新编辑器预览
function updateEditorPreview() {
    const editor = document.getElementById('markdownEditor');
    const preview = document.getElementById('editorPreview');
    const content = editor.value;
    
    if (!content.trim()) {
        preview.innerHTML = '<p style="color: var(--text-secondary); text-align: center; margin-top: 50px;">开始输入以查看预览...</p>';
        return;
    }
    
    let htmlContent;
    
    // 使用marked.js渲染（如果可用）
    if (typeof marked !== 'undefined' && !window.markedLoadFailed) {
        try {
            if (typeof marked.parse === 'function') {
                htmlContent = marked.parse(content);
            } else if (typeof marked === 'function') {
                htmlContent = marked(content);
            } else {
                throw new Error('无法识别的marked.js API');
            }
        } catch (markedError) {
            console.warn('⚠️ marked.js渲染失败，使用备用方法:', markedError);
            htmlContent = renderMarkdownFallback(content);
        }
    } else {
        htmlContent = renderMarkdownFallback(content);
    }
    
    // 应用图片增强
    htmlContent = enhanceImages(htmlContent);
    
    // 更新预览内容
    preview.innerHTML = htmlContent;
    
    // 设置图片处理
    setTimeout(() => {
        setupImageHandling();
    }, 100);
}

// 关闭文档编辑器
function closeDocumentEditor() {
    const modal = document.getElementById('documentEditorModal');
    modal.classList.remove('show');
    modal.style.display = 'none';
    
    // 恢复页面滚动
    document.body.style.overflow = '';
    
    // 清理状态
    currentEditingContent = '';
    currentEditingUrl = '';
    currentEditingName = '';
    
    console.log('📝 文档编辑器已关闭');
}

// 插入Markdown模板
function insertMarkdownTemplate() {
    const editor = document.getElementById('markdownEditor');
    const template = `# 文档标题

## 概述

这里是文档的概述内容。

## 主要内容

### 子标题1

- 列表项1
- 列表项2
- 列表项3

### 子标题2

**粗体文本** 和 *斜体文本*

\`\`\`
代码块示例
\`\`\`

## 结论

这里是结论部分。
`;
    
    // 在当前光标位置插入模板
    const cursorPos = editor.selectionStart;
    const currentValue = editor.value;
    const newValue = currentValue.slice(0, cursorPos) + template + currentValue.slice(cursorPos);
    
    editor.value = newValue;
    editor.focus();
    
    // 更新预览和统计
    updateEditorStats();
    updateEditorPreview();
    
    showNotification('Markdown模板已插入', 'success');
}

// 下载编辑后的内容
function downloadEditedContent() {
    const editor = document.getElementById('markdownEditor');
    const content = editor.value;
    
    if (!content.trim()) {
        showNotification('没有内容可下载', 'warning');
        return;
    }
    
    // 生成文件名：项目名_时间戳.md
    const now = new Date();
    const timestamp = now.toISOString().slice(0, 19).replace(/[T:]/g, '-').replace(/-/g, '');
    const projectName = (currentProject && currentProject.name) ? currentProject.name.replace(/[^\w\u4e00-\u9fa5-]/g, '_') : 'GauzDocument';
    let fileName = `${projectName}_${timestamp}.md`;
    
    // 如果有原始文件名，尝试提取有意义的部分
    if (currentEditingName && currentEditingName !== '完整文档') {
        const cleanName = currentEditingName.replace(/\.(md|markdown)$/i, '').replace(/[^\w\u4e00-\u9fa5-]/g, '_');
        if (cleanName && cleanName.length > 0) {
            fileName = `${projectName}_${cleanName}_${timestamp}.md`;
        }
    }
    
    // 创建下载链接
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    URL.revokeObjectURL(url);
    
    showNotification(`文档已下载: ${fileName}`, 'success');
    console.log(`💾 编辑后的文档已下载: ${fileName}`);
}

// 保存编辑后的文档
async function saveEditedDocument() {
    const editor = document.getElementById('markdownEditor');
    const content = editor.value;
    
    if (!content.trim()) {
        showNotification('没有内容可保存', 'warning');
        return;
    }
    
    try {
        document.getElementById('editorStatus').textContent = '正在保存文档...';
        
        // 这里可以实现保存逻辑，比如：
        // 1. 保存到本地存储
        // 2. 发送到后端API保存
        // 3. 更新原始文档（如果有权限）
        
        // 生成保存的文件名
        const now = new Date();
        const timestamp = now.toISOString().slice(0, 19).replace(/[T:]/g, '-').replace(/-/g, '');
        const projectName = (currentProject && currentProject.name) ? currentProject.name.replace(/[^\w\u4e00-\u9fa5-]/g, '_') : 'GauzDocument';
        let savedFileName = `${projectName}_${timestamp}.md`;
        
        // 如果有原始文件名，尝试提取有意义的部分
        if (currentEditingName && currentEditingName !== '完整文档') {
            const cleanName = currentEditingName.replace(/\.(md|markdown)$/i, '').replace(/[^\w\u4e00-\u9fa5-]/g, '_');
            if (cleanName && cleanName.length > 0) {
                savedFileName = `${projectName}_${cleanName}_${timestamp}.md`;
            }
        }
        
        // 保存到本地存储
        const saveKey = `edited_doc_${currentPreviewTaskId}_${Date.now()}`;
        localStorage.setItem(saveKey, JSON.stringify({
            name: savedFileName,
            originalName: currentEditingName,
            content: content,
            originalUrl: currentEditingUrl,
            editTime: new Date().toISOString(),
            taskId: currentPreviewTaskId
        }));
        
        document.getElementById('editorStatus').textContent = '文档保存成功';
        showNotification('文档已保存到本地', 'success');
        
        console.log('💾 文档已保存到本地存储');
        
        // 可选：自动下载备份
        setTimeout(() => {
            if (confirm('是否同时下载文档备份？')) {
                downloadEditedContent();
            }
        }, 1000);
        
    } catch (error) {
        console.error('❌ 保存文档失败:', error);
        document.getElementById('editorStatus').textContent = `保存失败: ${error.message}`;
        showNotification('文档保存失败', 'error');
    }
}

// 导出编辑器函数到全局
window.openDocumentEditor = openDocumentEditor;
window.closeDocumentEditor = closeDocumentEditor;
window.insertMarkdownTemplate = insertMarkdownTemplate;
window.downloadEditedContent = downloadEditedContent;
window.saveEditedDocument = saveEditedDocument;

// AI编辑器相关变量
let aiEditorModal = null;
let dmp = null; // diff_match_patch实例
let currentAIEditText = '';
let currentAIRequest = '';
let currentDiffResult = null;

// 初始化diff_match_patch库
function initializeDiffMatchPatch() {
    if (typeof diff_match_patch !== 'undefined') {
        dmp = new diff_match_patch();
        console.log('✅ diff_match_patch库已初始化');
    } else {
        console.warn('⚠️ diff_match_patch库未找到，请确保已加载');
    }
}

// 打开AI编辑器
function openAIEditor() {
    const editorTextarea = document.getElementById('markdownEditor');
    if (!editorTextarea) {
        showNotification('请先打开文档编辑器', 'error');
        return;
    }

    const selectedText = getSelectedText(editorTextarea);
    const textToEdit = selectedText || editorTextarea.value;
    
    if (!textToEdit.trim()) {
        showNotification('请选择要编辑的文本或确保编辑器中有内容', 'warning');
        return;
    }

    currentAIEditText = textToEdit;
    showAIEditorModal();
}

// 获取选中的文本
function getSelectedText(textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    return textarea.value.substring(start, end);
}

// 显示AI编辑器模态框
function showAIEditorModal() {
    aiEditorModal = document.getElementById('aiEditorModal');
    if (!aiEditorModal) {
        console.error('AI编辑器模态框未找到');
        return;
    }

    // 重置界面
    document.getElementById('aiOriginalText').value = currentAIEditText;
    document.getElementById('aiRequest').value = '';
    document.getElementById('aiDiffContainer').innerHTML = '';
    document.getElementById('aiAcceptBtn').style.display = 'none';
    document.getElementById('aiRejectBtn').style.display = 'none';
    
    aiEditorModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// 关闭AI编辑器
function closeAIEditor() {
    if (aiEditorModal) {
        aiEditorModal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
    currentDiffResult = null;
}

// 处理AI编辑请求
async function processAIEdit() {
    const requestText = document.getElementById('aiRequest').value.trim();
    if (!requestText) {
        showNotification('请输入修改要求', 'warning');
        return;
    }

    currentAIRequest = requestText;
    
    // 显示加载状态
    const diffContainer = document.getElementById('aiDiffContainer');
    diffContainer.innerHTML = `
        <div class="ai-loading">
            <div class="ai-loading-spinner"></div>
            <span>AI正在处理您的请求...</span>
        </div>
    `;

    try {
        // 调用AI编辑API
        const response = await fetch('/api/ai-editor/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plain_text: [currentAIEditText],
                request: currentAIRequest,
                project_name: currentProject?.name || '默认项目',
                search_type: 'hybrid',
                top_k: 5
            })
        });

        if (!response.ok) {
            throw new Error(`API请求失败: ${response.status}`);
        }

        const result = await response.json();
        const optimizedText = result.result || currentAIEditText;
        
        // 生成并显示diff
        generateAndDisplayDiff(currentAIEditText, optimizedText);
        
    } catch (error) {
        console.error('AI编辑请求失败:', error);
        diffContainer.innerHTML = `
            <div class="ai-loading" style="color: var(--error-color);">
                <span>❌ 处理失败: ${error.message}</span>
            </div>
        `;
    }
}

// 生成并显示diff
function generateAndDisplayDiff(originalText, modifiedText) {
    if (!dmp) {
        initializeDiffMatchPatch();
        if (!dmp) {
            showNotification('diff_match_patch库未加载，无法显示差异', 'error');
            return;
        }
    }

    // 生成diff
    const diffs = dmp.diff_main(originalText, modifiedText);
    dmp.diff_cleanupSemantic(diffs);
    
    currentDiffResult = {
        original: originalText,
        modified: modifiedText,
        diffs: diffs
    };

    // 显示diff结果
    displayDiffResult(diffs);
    
    // 显示操作按钮
    document.getElementById('aiAcceptBtn').style.display = 'inline-flex';
    document.getElementById('aiRejectBtn').style.display = 'inline-flex';
}

// 显示diff结果
function displayDiffResult(diffs) {
    const diffContainer = document.getElementById('aiDiffContainer');
    let html = '';
    
    for (let i = 0; i < diffs.length; i++) {
        const [operation, text] = diffs[i];
        const escapedText = escapeHtml(text);
        
        switch (operation) {
            case 1: // 插入 (新增的内容)
                html += `<div class="diff-line modified">${escapedText}</div>`;
                break;
            case -1: // 删除 (原有的内容)
                html += `<div class="diff-line original">${escapedText}</div>`;
                break;
            case 0: // 不变
                html += `<div class="diff-line unchanged">${escapedText}</div>`;
                break;
        }
    }
    
    diffContainer.innerHTML = html;
}

// HTML转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 接受AI修改
function acceptAIEdit() {
    if (!currentDiffResult) {
        showNotification('没有可接受的修改', 'warning');
        return;
    }

    const editorTextarea = document.getElementById('markdownEditor');
    if (!editorTextarea) {
        showNotification('编辑器未找到', 'error');
        return;
    }

    // 替换文本
    const originalText = currentAIEditText;
    const modifiedText = currentDiffResult.modified;
    const currentContent = editorTextarea.value;
    
    // 如果是选中的文本，只替换选中部分
    const selectedText = getSelectedText(editorTextarea);
    if (selectedText && selectedText === originalText) {
        const start = editorTextarea.selectionStart;
        const end = editorTextarea.selectionEnd;
        const newContent = currentContent.substring(0, start) + modifiedText + currentContent.substring(end);
        editorTextarea.value = newContent;
        
        // 设置新的选中范围
        editorTextarea.setSelectionRange(start, start + modifiedText.length);
    } else {
        // 替换整个内容
        editorTextarea.value = modifiedText;
    }

    // 触发输入事件以更新预览
    editorTextarea.dispatchEvent(new Event('input'));
    
    showNotification('已接受AI修改', 'success');
    closeAIEditor();
}

// 拒绝AI修改
function rejectAIEdit() {
    showNotification('已拒绝AI修改', 'info');
    closeAIEditor();
}

// 导出AI编辑器函数到全局
window.openAIEditor = openAIEditor;
window.closeAIEditor = closeAIEditor;
window.processAIEdit = processAIEdit;
window.acceptAIEdit = acceptAIEdit;
window.rejectAIEdit = rejectAIEdit;

// 初始化diff_match_patch
document.addEventListener('DOMContentLoaded', function() {
    initializeDiffMatchPatch();
});

console.log('✏️ 文档编辑器功能已加载！');
console.log('🤖 AI编辑器功能已加载！');