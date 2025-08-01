// AI编辑器相关变量
let aiEditorModal = null;
let dmp = null; // diff_match_patch实例
let currentAIEditText = '';
let currentAIRequest = '';
let currentDiffResult = null;

// 全局变量，用于存储当前编辑会话的状态
let currentEditorSelection = {
    text: '',
    start: 0,
    end: 0,
    originalContent: '',
    modifiedText: ''
};

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

    // 存储当前选择的文本和位置信息
    currentEditorSelection = {
        text: selectedText,
        start: selectionStart,
        end: selectionEnd,
        originalContent: markdownEditor.value
    };

    // 获取并填充AI面板
    const aiCommandPanel = document.getElementById('aiCommandPanel');
    const aiSelectedTextPreview = document.getElementById('aiSelectedTextPreview');
    
    aiSelectedTextPreview.textContent = selectedText;
    
    // 重置面板状态并显示
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
        // 调用真实的后端API
        const modifiedText = await callAIEditorAPI(currentEditorSelection.text, command);
        currentEditorSelection.modifiedText = modifiedText; // 保存AI返回的结果
        
        // 渲染差异对比视图
        renderDiff(currentEditorSelection.text, modifiedText);
        
        // 切换操作按钮的显示
        document.getElementById('aiPanelActions').style.display = 'none';
        document.getElementById('aiDiffActions').style.display = 'flex';

    } catch (error) {
        console.error("AI处理失败:", error);
        document.getElementById('aiDiffViewContainer').innerHTML = `<p style="color: var(--error-color); padding: 20px;">AI处理失败，请稍后重试。错误信息: ${error.message}</p>`;
        showNotification('AI处理失败，请稍后重试', 'error');
    } finally {
        // 恢复按钮状态
        aiProcessBtn.innerHTML = `<span>✨</span> 生成修改`;
        aiProcessBtn.disabled = false;
    }
}

// 调用真实的AI编辑器API
async function callAIEditorAPI(text, command) {
    const requestData = {
        plain_text: [text],
        request: command,
        project_name: currentProject?.name || 'default',
        search_type: 'hybrid',
        top_k: 5
    };

    console.log('📤 发送AI编辑请求:', requestData);

    const response = await apiRequest('http://localhost:8001/api/ai-editor/process', {
        method: 'POST',
        body: JSON.stringify(requestData)
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('📥 AI编辑响应:', result);

    if (!result.success) {
        throw new Error(result.error || '未知错误');
    }

    // 从结果中提取优化后的文本
    const resultText = result.result;
    const optimizedTextMatch = resultText.match(/=== 优化后的文本 ===\s*([\s\S]*?)\s*=== 参考资料摘要 ===/);    
    
    if (optimizedTextMatch && optimizedTextMatch[1]) {
        return optimizedTextMatch[1].trim();
    } else {
        // 如果没有找到特定格式，返回整个结果
        return resultText;
    }
}

// 渲染差异对比的函数
function renderDiff(original, modified) {
    const aiDiffViewContainer = document.getElementById('aiDiffViewContainer');
    
    // 确保diff_match_patch已加载
    if (typeof diff_match_patch === 'undefined') {
        aiDiffViewContainer.innerHTML = '<p style="color: var(--error-color); padding: 20px;">差异对比功能未加载，请刷新页面重试。</p>';
        return;
    }
    
    const dmp = new diff_match_patch();
    const diffs = dmp.diff_main(original, modified);
    dmp.diff_cleanupSemantic(diffs);

    const html = dmp.diff_prettyHtml(diffs)
                    .replace(/&para;/g, ' ')
                    .replace(/<ins style="background:#e6ffe6;">/g, '<span class="diff-line modified">')
                    .replace(/<del style="background:#ffe6e6;">/g, '<span class="diff-line original">')
                    .replace(/<\/ins>/g, '</span>')
                    .replace(/<\/del>/g, '</span>')
                    .replace(/<span>/g, '<span class="diff-line unchanged">');
    
    aiDiffViewContainer.innerHTML = html;
    aiDiffViewContainer.style.display = 'block';
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

// 接受AI的修改
function acceptAIEdit() {
    const markdownEditor = document.getElementById('markdownEditor');
    const { start, end, originalContent, modifiedText } = currentEditorSelection;

    // 用AI修改后的文本替换编辑器中的原文
    markdownEditor.value = originalContent.substring(0, start) + modifiedText + originalContent.substring(end);
    
    // 触发编辑器的更新事件，以刷新预览和状态
    markdownEditor.dispatchEvent(new Event('input', { bubbles: true }));
    
    closeAICommandPanel();
    showNotification('AI修改已应用', 'success');
}

// 拒绝AI的修改，并返回到输入指令的界面
function rejectAIEdit() {
    resetAIPanel();
    showNotification('已拒绝AI修改', 'info');
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
window.openAIEditor = openAIEditor;
window.closeAIEditor = closeAIEditor;
window.initiateAIEdit = initiateAIEdit;
window.closeAICommandPanel = closeAICommandPanel;
window.processAIEdit = processAIEdit;
window.acceptAIEdit = acceptAIEdit;
window.rejectAIEdit = rejectAIEdit;

// 初始化diff_match_patch
document.addEventListener('DOMContentLoaded', function() {
    initializeDiffMatchPatch();
});

console.log('🤖 AI编辑器功能已加载！');

// 兼容性函数：如果showNotification不存在，使用alert作为后备
if (typeof showNotification === 'undefined') {
    window.showNotification = function(message, type) {
        alert(message);
    };
}

// 兼容性函数：如果apiRequest不存在，使用fetch作为后备
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