/**
 * =================================================================
 * 工程AI助手 - 核心交互脚本 (ai_chat_script.js)
 * =================================================================
 * * 修复日志 (v2.3.0):
 * - 增加了对AI面板关闭按钮("×")的事件监听。
 * - 修复了点击 "拒绝" 或 "接受" 按钮后，AI面板不会自动关闭的bug。
 * - 使用setTimeout延迟提示框，防止与关闭动画冲突。
 * - 移除旧版AI编辑器中不再使用的函数。
 */

document.addEventListener('DOMContentLoaded', function() {
    // --- 初始化所有功能 ---
    initializeDiffMatchPatch();
    initializeAIEditorEventListeners(); // ⭐️ 关键修复：初始化AI面板的事件监听
});

// --- 全局变量 ---
let dmp = null; // diff_match_patch实例
let currentEditorSelection = {
    text: '',
    start: 0,
    end: 0,
    originalContent: '',
    modifiedText: ''
};

// --- 初始化函数 ---

function initializeDiffMatchPatch() {
    if (typeof diff_match_patch !== 'undefined') {
        dmp = new diff_match_patch();
        console.log('✅ diff_match_patch库已初始化');
    } else {
        console.warn('⚠️ diff_match_patch库未找到，请确保已加载');
    }
}

// ⭐️ 关键修复：为AI面板的按钮绑定事件
function initializeAIEditorEventListeners() {
    const aiPanelCloseBtn = document.getElementById('aiPanelCloseBtn');
    if (aiPanelCloseBtn) {
        aiPanelCloseBtn.addEventListener('click', closeAICommandPanel);
    } else {
        console.warn('AI面板关闭按钮未找到');
    }
}


// --- AI集成编辑核心功能 ---

// 触发AI编辑模式
function initiateAIEdit() {
    const markdownEditor = document.getElementById('markdownEditor');
    const selectionStart = markdownEditor.selectionStart;
    const selectionEnd = markdownEditor.selectionEnd;
    const selectedText = markdownEditor.value.substring(selectionStart, selectionEnd);

    if (!selectedText.trim()) {
        showNotification("请先在左侧编辑器中选择需要修改的文本。", 'warning');
        return;
    }

    currentEditorSelection = {
        text: selectedText,
        start: selectionStart,
        end: selectionEnd,
        originalContent: markdownEditor.value
    };

    const aiCommandPanel = document.getElementById('aiCommandPanel');
    const aiSelectedTextPreview = document.getElementById('aiSelectedTextPreview');
    
    aiSelectedTextPreview.textContent = selectedText;
    
    resetAIPanel();
    aiCommandPanel.classList.add('show');
    document.getElementById('aiCommandInput').focus();
}

// 关闭AI编辑面板
function closeAICommandPanel() {
    document.getElementById('aiCommandPanel').classList.remove('show');
}

// 处理AI编辑请求
async function processAIEdit() {
    const aiCommandInput = document.getElementById('aiCommandInput');
    const command = aiCommandInput.value.trim();
    if (!command) {
        showNotification("请输入您的修改要求。", 'warning');
        return;
    }

    const aiProcessBtn = document.getElementById('aiProcessBtn');
    aiProcessBtn.innerHTML = `<span><div class="ai-loading-spinner"></div></span> 正在处理...`;
    aiProcessBtn.disabled = true;

    try {
        const modifiedText = await callAIEditorAPI(currentEditorSelection.text, command);
        displayDiffResultWithEditor(currentEditorSelection.text, modifiedText);
        
        document.getElementById('aiPanelActions').style.display = 'none';
        document.getElementById('aiDiffActions').style.display = 'flex';

    } catch (error) {
        console.error("AI处理失败:", error);
        document.getElementById('aiDiffViewContainer').innerHTML = `<p style="color: var(--error-color); padding: 20px;">AI处理失败，请稍后重试。错误信息: ${error.message}</p>`;
        showNotification('AI处理失败，请稍后重试', 'error');
    } finally {
        aiProcessBtn.innerHTML = `<span>✨</span> 生成修改`;
        aiProcessBtn.disabled = false;
    }
}

// 调用真实的AI编辑器API
async function callAIEditorAPI(text, command) {
    // 模拟API调用
    console.log('📤 发送AI编辑请求:', { text, command });
    await new Promise(resolve => setTimeout(resolve, 1000));
    const resultText = `这是AI根据“${command}”指令修改后的文本。\n` + text.split('\n').map(line => `> ${line}`).join('\n');
    console.log('📥 AI编辑响应:', resultText);
    return resultText;
}

// 渲染Diff和手动编辑区的函数
function displayDiffResultWithEditor(originalText, modifiedText) {
    const aiDiffViewContainer = document.getElementById('aiDiffViewContainer');
    
    if (!dmp) {
        aiDiffViewContainer.innerHTML = '<p style="color: var(--error-color); padding: 20px;">差异对比功能未加载。</p>';
        return;
    }
    
    const diffs = dmp.diff_main(originalText, modifiedText);
    dmp.diff_cleanupSemantic(diffs);

    const diffHtml = dmp.diff_prettyHtml(diffs)
                    .replace(/&para;/g, ' ')
                    .replace(/<ins style="background:#e6ffe6;">/g, '<span class="diff-line modified">')
                    .replace(/<del style="background:#ffe6e6;">/g, '<span class="diff-line original">')
                    .replace(/<\/ins>/g, '</span>')
                    .replace(/<\/del>/g, '</span>')
                    .replace(/<span>/g, '<span class="diff-line unchanged">');

    const finalHtml = `
        <div class="ai-diff-section">
            <h4>📊 修改对比</h4>
            <div class="ai-diff-container">${diffHtml}</div>
        </div>
        <div class="ai-edit-section">
            <h4>✏️ 手动编辑</h4>
            <div class="ai-edit-description">您可以在下方继续编辑AI生成的文本：</div>
            <textarea id="aiEditableText" class="ai-editable-text">${escapeHtml(modifiedText)}</textarea>
        </div>
    `;
    
    aiDiffViewContainer.innerHTML = finalHtml;
    aiDiffViewContainer.style.display = 'flex';
    
    currentEditorSelection.modifiedText = modifiedText;
}

// HTML转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 接受修改的函数
function acceptAIEdit() {
    const markdownEditor = document.getElementById('markdownEditor');
    const aiEditableText = document.getElementById('aiEditableText');
    const { start, end, originalContent } = currentEditorSelection;

    let finalText;
    if (aiEditableText) {
        finalText = aiEditableText.value;
    } else {
        finalText = currentEditorSelection.modifiedText;
    }

    markdownEditor.value = originalContent.substring(0, start) + finalText + originalContent.substring(end);
    
    markdownEditor.dispatchEvent(new Event('input', { bubbles: true }));
    
    // ⭐️ 关键修复：先重置面板状态，再关闭面板
    resetAIPanel();
    closeAICommandPanel();
    
    // ⭐️ 关键修复：延迟提示框，防止与动画冲突
    setTimeout(() => {
        showNotification('修改已应用', 'success');
    }, 400); // 延迟时间与CSS动画时间一致
}

// 拒绝修改的函数
function rejectAIEdit() {
    // ⭐️ 关键修复：先重置面板状态，再关闭面板
    resetAIPanel();
    closeAICommandPanel();
    
    // ⭐️ 关键修复：延迟提示框
    setTimeout(() => {
        showNotification('已取消AI修改', 'info');
    }, 400);
}

// 辅助函数：重置AI面板状态
function resetAIPanel() {
    const aiDiffViewContainer = document.getElementById('aiDiffViewContainer');
    const aiPanelActions = document.getElementById('aiPanelActions');
    const aiDiffActions = document.getElementById('aiDiffActions');
    
    aiDiffViewContainer.innerHTML = '';
    aiDiffViewContainer.style.display = 'none';
    aiDiffActions.style.display = 'none';
    aiPanelActions.style.display = 'flex';
    document.getElementById('aiCommandInput').focus();
}

// 导出AI编辑器函数到全局
window.initiateAIEdit = initiateAIEdit;
window.closeAICommandPanel = closeAICommandPanel;
window.processAIEdit = processAIEdit;
window.acceptAIEdit = acceptAIEdit;
window.rejectAIEdit = rejectAIEdit;

console.log('🤖 AI编辑器功能已加载！');

// 兼容性与占位函数
if (typeof showNotification === 'undefined') {
    window.showNotification = function(message, type) {
        console.log(`Notification (${type}): ${message}`);
        alert(message);
    };
}

if (typeof apiRequest === 'undefined') {
    window.apiRequest = function(url, options) {
        return fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
    };
}

// 其他页面功能的占位函数
window.startNewChat = () => alert('功能待实现: 新建对话');
window.clearAllHistory = () => alert('功能待实现: 清空历史');
window.clearProjectLock = () => alert('功能待实现: 解锁项目');
window.goBackToProjectSelection = () => alert('功能待实现: 返回项目选择');
window.toggleThinking = (show) => console.log(`显示思考过程: ${show}`);
window.toggleAutoSave = (save) => console.log(`自动保存: ${save}`);
window.resetSettings = () => alert('功能待实现: 重置设置');
window.saveSettings = () => alert('功能待实现: 保存设置');
window.closeMarkdownPreview = () => document.getElementById('markdownPreviewModal').classList.remove('show');
window.downloadOriginalDoc = () => alert('功能待实现: 下载原文件');
window.refreshPreview = () => alert('功能待实现: 刷新预览');
window.insertMarkdownTemplate = () => alert('功能待实现: 插入模板');
window.downloadEditedContent = () => alert('功能待实现: 下载编辑后内容');
window.saveEditedDocument = () => alert('功能待实现: 保存修改到服务器');
window.clearAllCurrentFiles = () => alert('功能待实现: 清空当前文件');
