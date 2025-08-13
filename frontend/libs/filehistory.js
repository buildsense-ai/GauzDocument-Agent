// 文件历史管理和工具栏功能

// 保存原始按钮状态
let originalButtonsHTML = null;
let isToolbarReplaced = false;

// 替换工具栏按钮的函数
function replaceToolbarButtons() {
    const toolbarDiv = document.querySelector('.preview-sidebar .toolbar-buttons') || document.querySelector('.toolbar-buttons');
    if (!toolbarDiv) {
        console.error('找不到工具栏容器');
        return;
    }
    
    // 如果还没有保存原始状态，先保存
    if (!originalButtonsHTML) {
        originalButtonsHTML = toolbarDiv.innerHTML;
    }
    
    // 应用简洁样式类
    try { toolbarDiv.classList.add('toolbar-minimal'); } catch(e) {}

    // 添加淡出效果
    toolbarDiv.style.transition = 'opacity 0.3s ease-in-out';
    toolbarDiv.style.opacity = '0';
    
    // 等待淡出完成后替换内容
    setTimeout(() => {
        // 创建新的按钮HTML
        const newButtonsHTML = `
            <button class="preview-btn" name="上一版本" onclick="goBack()" title="上一版本">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
            </button>
            <button class="preview-btn" name="下一版本" onclick="goForward()" title="下一版本">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12H19"/><path d="M12 5l7 7-7 7"/></svg>
            </button>
            <button class="preview-btn" onclick="uploadFile()" title="上传当前编辑文档">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>
            </button>
            <button class="preview-btn" onclick="downloadFile()" title="下载当前浏览版本">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12l7 7 7-7"/></svg>
            </button>
            <button class="preview-btn" onclick="restoreOriginalButtons()" title="恢复原工具栏">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9"/><path d="M3 3v6h6"/></svg>
            </button>
            <div class="version-history-container" style="display: none;">
                <div class="version-timeline">
                    <div class="timeline-header">
                        <span class="timeline-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                        </span>
                        <span class="timeline-title">版本历史</span>
                        <button class="timeline-close" onclick="toggleVersionHistory()">✕</button>
                    </div>
                    <div class="timeline-content">
                        <div class="timeline-slider-container">
                            <div class="timeline-markers" id="timelineMarkers"></div>
                            <input type="range" id="versionSlider" class="timeline-slider" min="0" max="0" value="0" step="1">
                            <div class="timeline-labels">
                                <span class="timeline-label-end">new</span>
                                <span class="timeline-label-start">old</span>
                            </div>
                        </div>
                        <div class="version-info">
                            <div class="version-details">
                                <span class="version-date">选择版本查看详情</span>
                                <span class="version-id"></span>
                            </div>
                            <div class="version-actions">
                                <button class="version-btn" onclick="previewVersion()" disabled>预览</button>
                                <button class="version-btn" onclick="restoreVersion()" disabled>恢复</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <button class="preview-btn" onclick="toggleVersionHistory()" title="版本历史">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            </button>
        `;
        
        // 添加版本历史组件的CSS样式
        const versionHistoryStyles = `
            <style>
            .toolbar-buttons {
                position: relative;
            }
            
            .version-history-container {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                max-width: 400px;
                max-height: 300px;
                overflow-y: auto;
                background: rgba(0, 0, 0, 0.9);
                border-radius: 8px;
                margin-top: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                z-index: 1000;
                animation: slideDown 0.3s ease-out;
            }
            
            @keyframes slideDown {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .version-timeline {
                padding: 16px;
                color: white;
            }
            
            .timeline-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                padding-bottom: 12px;
            }
            
            .timeline-icon {
                font-size: 18px;
                margin-right: 8px;
            }
            
            .timeline-title {
                font-size: 14px;
                font-weight: 600;
                flex: 1;
            }
            
            .timeline-close {
                background: none;
                border: none;
                color: rgba(255, 255, 255, 0.7);
                font-size: 16px;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: all 0.2s;
            }
            
            .timeline-close:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
            
            .timeline-content {
                display: flex;
                flex-direction: column;
                gap: 16px;
            }
            
            .timeline-slider-container {
                position: relative;
                margin: 16px 0;
            }
            
            .timeline-slider {
                width: 100%;
                height: 6px;
                border-radius: 3px;
                background: rgba(255, 255, 255, 0.2);
                outline: none;
                -webkit-appearance: none;
                appearance: none;
                position: relative;
                z-index: 2;
            }
            
            .timeline-markers {
                position: absolute;
                top: 50%;
                left: 0;
                right: 0;
                height: 2px;
                transform: translateY(-50%);
                pointer-events: none;
                z-index: 1;
            }
            
            .timeline-marker {
                position: absolute;
                width: 8px;
                height: 8px;
                background: #4CAF50;
                border: 2px solid rgba(0, 0, 0, 0.9);
                border-radius: 50%;
                transform: translate(-50%, -50%);
                top: 50%;
            }
            
            .timeline-marker.current {
                background: #FF9800;
                box-shadow: 0 0 8px rgba(255, 152, 0, 0.6);
            }
            
            .timeline-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: #4CAF50;
                cursor: pointer;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
                transition: all 0.2s;
            }
            
            .timeline-slider::-webkit-slider-thumb:hover {
                background: #66BB6A;
                transform: scale(1.1);
            }
            
            .timeline-slider::-moz-range-thumb {
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: #4CAF50;
                cursor: pointer;
                border: none;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
            }
            
            .timeline-labels {
                display: flex;
                justify-content: space-between;
                margin-top: 8px;
                font-size: 12px;
                color: rgba(255, 255, 255, 0.7);
            }
            
            .version-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 12px;
            }
            
            .version-details {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }
            
            .version-date {
                font-size: 13px;
                font-weight: 500;
            }
            
            .version-id {
                font-size: 11px;
                color: rgba(255, 255, 255, 0.7);
            }
            
            .version-actions {
                display: flex;
                gap: 8px;
            }
            
            .version-btn {
                padding: 6px 12px;
                font-size: 12px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .version-btn:hover:not(:disabled) {
                background: rgba(255, 255, 255, 0.2);
                border-color: rgba(255, 255, 255, 0.5);
            }
            
            .version-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            
            .preview-btn[onclick="toggleVersionHistory()"] {
                position: relative;
            }
            
            .preview-btn[onclick="toggleVersionHistory()"].active::after {
                content: '';
                position: absolute;
                bottom: -2px;
                left: 50%;
                transform: translateX(-50%);
                width: 6px;
                height: 6px;
                background: #4CAF50;
                border-radius: 50%;
            }
            </style>
        `;
        
        // 将样式添加到页面
        if (!document.querySelector('#version-history-styles')) {
            const styleElement = document.createElement('style');
            styleElement.id = 'version-history-styles';
            styleElement.textContent = versionHistoryStyles.replace(/<\/?style>/g, '');
            document.head.appendChild(styleElement);
        }
        
        // 替换工具栏内容
        toolbarDiv.innerHTML = newButtonsHTML;
        isToolbarReplaced = true;
        
        // 添加淡入效果
        setTimeout(() => {
            toolbarDiv.style.opacity = '1';
        }, 50); // 短暂延迟确保DOM更新完成
        
        console.log('工具栏按钮已替换');
    }, 300); // 等待淡出动画完成
}

// 恢复原始按钮的函数
function restoreOriginalButtons() {
    const toolbarDiv = document.querySelector('.toolbar-buttons');
    if (!toolbarDiv || !originalButtonsHTML) {
        console.error('无法恢复原始按钮');
        return;
    }
    
    // 添加淡出效果
    toolbarDiv.style.transition = 'opacity 0.3s ease-in-out';
    toolbarDiv.style.opacity = '0';
    
    // 等待淡出完成后恢复内容
    setTimeout(() => {
        // 恢复原始按钮
        toolbarDiv.innerHTML = originalButtonsHTML;
        isToolbarReplaced = false;
        try { toolbarDiv.classList.remove('toolbar-minimal'); } catch(e) {}
        
        // 添加淡入效果
        setTimeout(() => {
            toolbarDiv.style.opacity = '1';
        }, 50); // 短暂延迟确保DOM更新完成
        
        console.log('工具栏按钮已恢复');
    }, 300); // 等待淡出动画完成
}

// 上一版本
async function goBack() {
    if (currentVersionIndex < 0 || versionHistory.length === 0) {
        showNotification('正在加载版本历史...', 'info');
        await loadVersionHistory();
        if (versionHistory.length === 0) {
            return;
        }
    }
    
    if (currentVersionIndex < versionHistory.length - 1) {
        currentVersionIndex++;
        updateVersionInfo();
        updateMarkerHighlight();
        const slider = document.getElementById('versionSlider');
        if (slider) {
            slider.value = currentVersionIndex;
        }
        
        // 加载并显示该版本的内容到编辑器
        await loadVersionContentToEditor();
        
        // 保存当前浏览的版本到浏览器存储
        saveCurrentBrowsingVersion();
        
        showNotification('已切换到上一版本', 'info');
    } else {
        showNotification('已经是最早版本', 'warning');
    }
}

// 下一版本
async function goForward() {
    if (currentVersionIndex < 0 || versionHistory.length === 0) {
        showNotification('正在加载版本历史...', 'info');
        await loadVersionHistory();
        if (versionHistory.length === 0) {
            return;
        }
    }
    
    if (currentVersionIndex > 0) {
        currentVersionIndex--;
        updateVersionInfo();
        updateMarkerHighlight();
        const slider = document.getElementById('versionSlider');
        if (slider) {
            slider.value = currentVersionIndex;
        }
        
        // 加载并显示该版本的内容到编辑器
        await loadVersionContentToEditor();
        
        // 保存当前浏览的版本到浏览器存储
        saveCurrentBrowsingVersion();
        
        showNotification('已切换到下一版本', 'info');
    } else {
        showNotification('已经是最新版本', 'warning');
    }
}

// 下载当前浏览版本的文件到桌面
function downloadFile() {
    // 获取当前浏览的版本ID（从浏览器存储中获取）
    const currentBrowsingVersionId = getCurrentBrowsingVersion();
    
    if (!currentBrowsingVersionId) {
        showNotification('请先选择一个版本进行浏览', 'warning');
        return;
    }
    
    const fileName = getCurrentFileName();
    const versionIdShort = currentBrowsingVersionId.substring(0, 8);
    
    try {
        showNotification(`正在下载当前浏览版本 ${versionIdShort}...`, 'info');
        
        // 构建下载URL
        const downloadUrl = `http://43.139.19.144:8000/api/get_fileBinby_version?filename=${encodeURIComponent(fileName)}&version_id=${encodeURIComponent(currentBrowsingVersionId)}`;
        
        // 创建隐藏的下载链接
        const downloadLink = document.createElement('a');
        downloadLink.href = downloadUrl;
        downloadLink.style.display = 'none';
        
        // 添加到页面并触发下载
        document.body.appendChild(downloadLink);
        downloadLink.click();
        
        // 清理
        setTimeout(() => {
            document.body.removeChild(downloadLink);
        }, 100);
        
        showNotification(`版本 ${versionIdShort}... 下载已开始`, 'success');
        
    } catch (error) {
        console.error('Error downloading file:', error);
        showNotification('下载文件失败: ' + error.message, 'error');
    }
}

// 加载版本内容到编辑器
async function loadVersionContentToEditor() {
    if (currentVersionIndex < 0 || currentVersionIndex >= versionHistory.length) {
        return;
    }
    
    const version = versionHistory[currentVersionIndex];
    const fileName = getCurrentFileName();
    const versionId = version.versionId || version.version_id || version.id;
    
    if (!versionId) {
        showNotification('无法获取版本ID', 'error');
        return;
    }
    
    try {
        // 使用后端API获取文件内容
        const response = await fetch(`http://43.139.19.144:8000/api/get_fileBinby_version?filename=${encodeURIComponent(fileName)}&version_id=${encodeURIComponent(versionId)}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // 获取文件内容
        const content = await response.text();
        
        // 渲染内容到预览区域
        const previewResult = document.getElementById('previewResult');
        const previewLoading = document.getElementById('previewLoading');
        const previewError = document.getElementById('previewError');
        
        if (previewResult) {
            // 隐藏加载和错误状态
            if (previewLoading) previewLoading.style.display = 'none';
            if (previewError) previewError.style.display = 'none';
            
            // 渲染Markdown内容
            let htmlContent;
            if (typeof marked !== 'undefined' && !window.markedLoadFailed) {
                try {
                    // 配置marked选项
                    if (marked.setOptions) {
                        marked.setOptions({
                            breaks: true,
                            gfm: true,
                            headerIds: false,
                            mangle: false
                        });
                    }
                    
                    // 根据marked版本使用不同的API
                    if (typeof marked.parse === 'function') {
                        htmlContent = marked.parse(content);
                    } else if (typeof marked === 'function') {
                        htmlContent = marked(content);
                    } else {
                        throw new Error('无法识别的marked.js API');
                    }
                } catch (markedError) {
                    console.warn('⚠️ marked.js渲染失败，使用备用方法:', markedError);
                    htmlContent = content.replace(/\n/g, '<br>');
                }
            } else {
                // 备用渲染：简单的换行处理
                htmlContent = content.replace(/\n/g, '<br>');
            }
            
            // 显示渲染结果
            previewResult.innerHTML = htmlContent;
            previewResult.style.display = 'block';

            // 记录最近一次渲染所用的Markdown，供切换编辑和下载使用
            try { window.lastRenderedMarkdown = content; } catch(e) {}
            
            // 更新预览状态
            const previewStatus = document.getElementById('previewStatus');
            if (previewStatus) {
                previewStatus.textContent = '版本内容已加载';
            }
        }
        
    } catch (error) {
        console.error('Error loading version content:', error);
        showNotification('加载版本内容失败: ' + error.message, 'error');
    }
}

// 保存当前浏览的版本到浏览器存储
function saveCurrentBrowsingVersion() {
    if (currentVersionIndex >= 0 && currentVersionIndex < versionHistory.length) {
        const version = versionHistory[currentVersionIndex];
        const versionId = version.versionId || version.version_id || version.id;
        const fileName = getCurrentFileName();
        
        if (versionId && fileName) {
            const storageKey = `browsing_version_${fileName}`;
            localStorage.setItem(storageKey, versionId);
            console.log(`已保存当前浏览版本: ${versionId.substring(0, 8)}...`);
        }
    }
}

// 获取当前浏览的版本ID
function getCurrentBrowsingVersion() {
    const fileName = getCurrentFileName();
    if (!fileName) return null;
    
    const storageKey = `browsing_version_${fileName}`;
    return localStorage.getItem(storageKey);
}

// 上传文件到版本控制系统
function uploadFile() {
    // 获取当前编辑的文档名称
    let fileName = window.currentEditingName || '未命名文档';
    
    // 确保文件名有.md后缀
    const fileNameWithExtension = fileName.endsWith('.md') ? fileName : fileName + '.md';
    
    // 获取当前编辑器内容
    const markdownEditor = document.getElementById('markdownEditor');
    const editorContent = markdownEditor ? markdownEditor.value : '';
    
    if (!editorContent.trim()) {
        showNotification('当前文档内容为空，无法上传', 'error');
        return;
    }
    
    // 创建文件对象
    const blob = new Blob([editorContent], { type: 'text/markdown' });
    const formData = new FormData();
    formData.append('file', blob, fileNameWithExtension);
    
    // 显示上传进度
    showNotification(`正在上传当前编辑的文档 "${fileNameWithExtension}" 到版本控制系统...`, 'info');
    
    // 发送上传请求
    fetch('http://43.139.19.144:8000/api/uploadwithversion', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ 文件上传成功:', data);
        showNotification(`当前文档 "${data.filename}" 已成功上传到版本控制系统\n版本ID: ${data.versionId}`, 'success');
    })
    .catch(error => {
        console.error('❌ 文件上传失败:', error);
        showNotification(`当前文档上传失败: ${error.message}`, 'error');
    });
}

// 版本历史相关变量
let versionHistory = [];
let currentVersionIndex = -1;
let isVersionHistoryVisible = false;

// 切换版本历史显示
function toggleVersionHistory() {
    console.log('🔍 toggleVersionHistory 函数被调用');
    const container = document.querySelector('.version-history-container');
    const toggleBtn = document.querySelector('.preview-btn[onclick="toggleVersionHistory()"]');
    
    console.log('📦 版本历史容器:', container);
    console.log('🔘 切换按钮:', toggleBtn);
    
    if (!container) {
        console.error('❌ 找不到版本历史容器');
        showNotification('版本历史组件未找到，请先点击工具栏切换按钮', 'error');
        return;
    }
    
    isVersionHistoryVisible = !isVersionHistoryVisible;
    console.log('👁️ 版本历史可见状态:', isVersionHistoryVisible);
    
    if (isVersionHistoryVisible) {
        container.style.display = 'block';
        if (toggleBtn) toggleBtn.classList.add('active');
        console.log('📖 开始加载版本历史');
        loadVersionHistory();
    } else {
        container.style.display = 'none';
        if (toggleBtn) toggleBtn.classList.remove('active');
        console.log('🙈 隐藏版本历史');
    }
}

// 加载版本历史
async function loadVersionHistory() {
    console.log('📂 开始加载版本历史');
    const fileName = window.currentEditingName;
    console.log('📄 当前文档名称:', fileName);
    
    if (!fileName) {
        console.error('❌ 无法获取当前文档名称');
        showNotification('无法获取当前文档名称', 'error');
        return;
    }
    
    const fileNameWithExtension = fileName.endsWith('.md') ? fileName : fileName + '.md';
    console.log('📝 带扩展名的文件名:', fileNameWithExtension);
    
    try {
        showNotification('正在加载版本历史...', 'info');
        console.log('🌐 发送API请求获取版本历史');
        
        const response = await fetch(`http://43.139.19.144:8000/api/getfile_versions?filename=${encodeURIComponent(fileNameWithExtension)}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        // 处理API返回的数据格式
        versionHistory = data.versions ? data.versions.map((version, index) => ({
            id: version.versionId,
            timestamp: new Date(version.lastModified).getTime(),
            date: new Date(version.lastModified).toLocaleString('zh-CN'),
            size: version.size,
            etag: version.etag,
            isLatest: version.isLatest === 'true',
            storageClass: version.storageClass,
            versionId: version.versionId,
            created_at: version.lastModified,
            version_id: version.versionId
        })) : [];
        
        // 按时间排序，最新的在前
        versionHistory.sort((a, b) => b.timestamp - a.timestamp);
        
        if (versionHistory.length === 0) {
            showNotification('该文档暂无版本历史', 'warning');
            return;
        }
        
        // 更新时间轴滑块
        updateVersionSlider();
        showNotification(`已加载 ${versionHistory.length} 个版本`, 'success');
        
    } catch (error) {
        console.error('❌ 加载版本历史失败:', error);
        showNotification(`加载版本历史失败: ${error.message}`, 'error');
    }
}

// 更新版本滑块
function updateVersionSlider() {
    const slider = document.getElementById('versionSlider');
    const markersContainer = document.getElementById('timelineMarkers');
    
    if (!slider || versionHistory.length === 0) return;
    
    // 设置滑块范围
    slider.max = versionHistory.length - 1;
    slider.value = versionHistory.length - 1; // 默认选择最新版本
    currentVersionIndex = versionHistory.length - 1;
    
    // 创建时间轴标记
    if (markersContainer) {
        markersContainer.innerHTML = '';
        
        for (let i = 0; i < versionHistory.length; i++) {
            const marker = document.createElement('div');
            marker.className = 'timeline-marker';
            if (i === currentVersionIndex) {
                marker.classList.add('current');
            }
            
            // 计算标记位置（百分比）
            const position = versionHistory.length > 1 ? (i / (versionHistory.length - 1)) * 100 : 50;
            marker.style.left = position + '%';
            
            markersContainer.appendChild(marker);
        }
    }
    
    // 更新版本信息显示
    updateVersionInfo();
    
    // 添加滑块事件监听
    slider.oninput = function() {
        currentVersionIndex = parseInt(this.value);
        updateVersionInfo();
        updateMarkerHighlight();
    };
}

// 更新标记高亮
function updateMarkerHighlight() {
    const markers = document.querySelectorAll('.timeline-marker');
    markers.forEach((marker, index) => {
        if (index === currentVersionIndex) {
            marker.classList.add('current');
        } else {
            marker.classList.remove('current');
        }
    });
}

// 更新版本信息显示
function updateVersionInfo() {
    const versionDate = document.querySelector('.version-date');
    const versionId = document.querySelector('.version-id');
    const previewBtn = document.querySelector('.version-actions .version-btn:first-child');
    const restoreBtn = document.querySelector('.version-actions .version-btn:last-child');
    
    if (currentVersionIndex >= 0 && currentVersionIndex < versionHistory.length) {
        const version = versionHistory[currentVersionIndex];
        
        // 格式化日期
        const date = new Date(version.created_at || version.timestamp);
        const formattedDate = date.toLocaleString('zh-CN');
        
        const sizeInKB = version.size ? (version.size / 1024).toFixed(2) : '未知';
        const latestBadge = version.isLatest ? ' [最新]' : '';
        
        versionDate.textContent = formattedDate + latestBadge;
        versionId.textContent = `版本 ID: ${(version.version_id || version.id || version.versionId || '').substring(0, 8)}... | 大小: ${sizeInKB} KB`;
        
        // 启用按钮
        if (previewBtn) previewBtn.disabled = false;
        if (restoreBtn) restoreBtn.disabled = false;
    } else {
        versionDate.textContent = '选择版本查看详情';
        versionId.textContent = '';
        
        // 禁用按钮
        if (previewBtn) previewBtn.disabled = true;
        if (restoreBtn) restoreBtn.disabled = true;
    }
}

// 预览选中版本
async function previewVersion() {
    if (currentVersionIndex < 0 || currentVersionIndex >= versionHistory.length) {
        showNotification('请先选择一个版本', 'warning');
        return;
    }
    
    const version = versionHistory[currentVersionIndex];
    const versionIdShort = (version.version_id || version.id || version.versionId || '').substring(0, 8);
    
    try {
        showNotification(`正在预览版本 ${versionIdShort}...`, 'info');
        
        // 获取特定版本的内容
        const response = await fetch(`http://43.139.19.144:8000/api/get_fileBinby_version?filename=${encodeURIComponent(getCurrentFileName())}&version_id=${version.versionId || version.version_id || version.id}`);
        if (!response.ok) {
            throw new Error('Failed to load version content');
        }
        const content = await response.text();
        
        // 渲染Markdown内容到预览区域
        const previewResult = document.getElementById('previewResult');
        const previewLoading = document.getElementById('previewLoading');
        const previewError = document.getElementById('previewError');
        
        if (previewResult) {
            // 隐藏加载和错误状态
            if (previewLoading) previewLoading.style.display = 'none';
            if (previewError) previewError.style.display = 'none';
            
            // 渲染Markdown内容
            let htmlContent;
            if (typeof marked !== 'undefined' && !window.markedLoadFailed) {
                try {
                    // 配置marked选项
                    if (marked.setOptions) {
                        marked.setOptions({
                            breaks: true,
                            gfm: true,
                            headerIds: false,
                            mangle: false
                        });
                    }
                    
                    // 根据marked版本使用不同的API
                    if (typeof marked.parse === 'function') {
                        htmlContent = marked.parse(content);
                    } else if (typeof marked === 'function') {
                        htmlContent = marked(content);
                    } else {
                        throw new Error('无法识别的marked.js API');
                    }
                } catch (markedError) {
                    console.warn('⚠️ marked.js渲染失败，使用备用方法:', markedError);
                    htmlContent = content.replace(/\n/g, '<br>');
                }
            } else {
                // 备用渲染：简单的换行处理
                htmlContent = content.replace(/\n/g, '<br>');
            }
            
            // 显示渲染结果
            previewResult.innerHTML =  htmlContent;
            previewResult.style.display = 'block';

            // 记录最近一次渲染所用Markdown，供切换编辑和下载使用
            try { window.lastRenderedMarkdown = content; } catch(e) {}

            showNotification(`版本 ${versionIdShort} 预览完成`, 'success');
        }
        
    } catch (error) {
        console.error('Error previewing version:', error);
        showNotification('预览版本失败: ' + error.message, 'error');
        
        // 显示错误状态
        const previewError = document.getElementById('previewError');
        const previewErrorMsg = document.getElementById('previewErrorMsg');
        if (previewError && previewErrorMsg) {
            previewErrorMsg.textContent = error.message;
            previewError.style.display = 'flex';
        }
    }
}

// 恢复到选中版本
async function restoreVersion() {
    if (currentVersionIndex < 0 || currentVersionIndex >= versionHistory.length) {
        showNotification('请先选择一个版本', 'warning');
        return;
    }
    
    const version = versionHistory[currentVersionIndex];
    const versionIdShort = (version.version_id || version.id || version.versionId || '').substring(0, 8);
    
    if (!confirm(`确定要恢复到版本 ${versionIdShort}... 吗？\n\n创建时间: ${new Date(version.created_at || version.timestamp).toLocaleString('zh-CN')}\n\n当前编辑的内容将被替换！`)) {
        return;
    }
    
    try {
        showNotification(`正在恢复到版本 ${versionIdShort}...`, 'info');
        
        // 获取特定版本的内容
        const response = await fetch(`http://43.139.19.144:8000/api/get_fileBinby_version?filename=${encodeURIComponent(getCurrentFileName())}&version_id=${version.versionId || version.version_id || version.id}`);
        if (!response.ok) {
            throw new Error('Failed to load version content');
        }
        const content = await response.text();
        
        // 更新编辑器内容
        const editor = document.getElementById('markdownEditor');
        if (editor) {
            editor.value = content;
        }
        
        // 更新当前编辑内容
        if (window.currentEditingContent !== undefined) {
            window.currentEditingContent = content;
        }
        
        showNotification(`已恢复到版本 ${versionIdShort}...`, 'success');
        
        // 关闭版本历史面板
        toggleVersionHistory();
        
    } catch (error) {
        console.error('Error restoring version:', error);
        showNotification('恢复版本失败: ' + error.message, 'error');
    }
}

// 获取当前文件名的辅助函数
function getCurrentFileName() {
    let fileName = window.currentEditingName || '未命名文档';
    // 确保文件名有.md后缀
    if (!fileName.endsWith('.md')) {
        fileName += '.md';
    }
    return fileName;
}

// 显示通知消息的辅助函数
function showNotification(message, type = 'info') {
    // 如果全局的showNotification函数存在，使用它
    if (window.showNotification && typeof window.showNotification === 'function') {
        window.showNotification(message, type);
    } else {
        // 简单的控制台输出作为备用
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

