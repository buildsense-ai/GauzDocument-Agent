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

// --- 工具函数 ---

// 获取当前选中的文本
function getSelectedText() {
    // 获取当前活跃的编辑器
    let activeEditor = document.getElementById('markdownEditor');
    const modalEditor = document.getElementById('modalMarkdownEditor');
    
    // 如果模态编辑器存在且可见，优先使用模态编辑器
    if (modalEditor && modalEditor.offsetParent !== null) {
        activeEditor = modalEditor;
    }
    
    if (!activeEditor) {
        return '';
    }
    
    const selectionStart = activeEditor.selectionStart;
    const selectionEnd = activeEditor.selectionEnd;
    const selectedText = activeEditor.value.substring(selectionStart, selectionEnd);
    
    return selectedText.trim();
}

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
    
    // ⭐️ 新增：监听编辑器文本选择事件，显示AI编辑提示气泡
    let selectionTimeout;
    
    const handleTextSelection = (event) => {
        console.log('🔍 文本选择事件触发:', event.type);
        // 清除之前的延时器
        clearTimeout(selectionTimeout);
        
        // 延迟检查选择，避免频繁触发
        selectionTimeout = setTimeout(() => {
            // 获取当前活跃的编辑器
            let activeEditor = null;
            const markdownEditor = document.getElementById('markdownEditor');
            const modalMarkdownEditor = document.getElementById('modalMarkdownEditor');
            
            // 确定当前活跃的编辑器
            if (event.target === modalMarkdownEditor) {
                activeEditor = modalMarkdownEditor;
            } else if (event.target === markdownEditor) {
                activeEditor = markdownEditor;
            } else {
                // 如果事件目标不明确，检查哪个编辑器可见且有焦点
                if (modalMarkdownEditor && modalMarkdownEditor.offsetParent !== null) {
                    activeEditor = modalMarkdownEditor;
                } else if (markdownEditor && markdownEditor.offsetParent !== null) {
                    activeEditor = markdownEditor;
                }
            }
            
            if (!activeEditor) return;
            
            const selectionStart = activeEditor.selectionStart;
            const selectionEnd = activeEditor.selectionEnd;
            const selectedText = activeEditor.value.substring(selectionStart, selectionEnd);
            
            console.log('📝 选中文本:', selectedText, '长度:', selectedText.length);
            
            // 如果选中了文本且长度合适，显示AI编辑提示气泡
            if (selectedText.trim() && selectedText.length > 5 && selectedText.length < 1000) {
                // 检查AI面板是否已经显示
                const aiCommandPanel = document.getElementById('aiCommandPanel');
                console.log('🎛️ AI面板状态:', aiCommandPanel ? aiCommandPanel.classList.contains('show') : 'not found');
                
                if (!aiCommandPanel.classList.contains('show')) {
                    // 获取鼠标位置或使用编辑器位置
                    let x = event.clientX || activeEditor.offsetLeft + 100;
                    let y = event.clientY || activeEditor.offsetTop + 100;
                    
                    // 如果没有鼠标事件，计算选中文本的大概位置
                    if (!event.clientX) {
                        const rect = activeEditor.getBoundingClientRect();
                        x = rect.left + 100;
                        y = rect.top + 100;
                    }
                    
                    console.log('🎯 创建气泡位置:', x, y);
                    createAIEditTooltip(x, y);
                }
            }
            // 移除了自动移除气泡的逻辑，让气泡自然超时消失
        }, 300); // 减少延迟到300ms，提高响应速度
    };
    
    // 为侧边栏编辑器添加事件监听
    const markdownEditor = document.getElementById('markdownEditor');
    if (markdownEditor) {
        markdownEditor.addEventListener('mouseup', handleTextSelection);
        markdownEditor.addEventListener('keyup', handleTextSelection);
        markdownEditor.addEventListener('select', handleTextSelection);
        console.log('✅ 侧边栏编辑器AI功能已初始化');
    }
    
    // 为模态窗口编辑器添加事件监听（延迟检查，因为模态窗口可能稍后创建）
    const initModalEditor = () => {
        const modalMarkdownEditor = document.getElementById('modalMarkdownEditor');
        if (modalMarkdownEditor && !modalMarkdownEditor.hasAIListener) {
            modalMarkdownEditor.addEventListener('mouseup', handleTextSelection);
            modalMarkdownEditor.addEventListener('keyup', handleTextSelection);
            modalMarkdownEditor.addEventListener('select', handleTextSelection);
            modalMarkdownEditor.hasAIListener = true; // 防止重复绑定
            console.log('✅ 模态窗口编辑器AI功能已初始化');
        }
    };
    
    // 立即尝试初始化模态编辑器
    initModalEditor();
    
    // 监听DOM变化，当模态窗口创建时自动初始化
    const observer = new MutationObserver(() => {
        initModalEditor();
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // 初始化复制/剪切操作检测
    detectCopyPasteOperations();
}


// --- AI集成编辑核心功能 ---

// 触发AI编辑模式
function initiateAIEdit() {
    // 尝试获取当前活跃的编辑器（侧边栏或模态窗口）
    let markdownEditor = document.getElementById('markdownEditor');
    let isModalEditor = false;
    
    // 如果侧边栏编辑器不可见或不存在，尝试模态窗口编辑器
    if (!markdownEditor || markdownEditor.offsetParent === null) {
        markdownEditor = document.getElementById('modalMarkdownEditor');
        isModalEditor = true;
    }
    
    if (!markdownEditor) {
        showNotification("未找到编辑器，请确保编辑模式已开启。", 'error');
        return;
    }
    
    const selectionStart = markdownEditor.selectionStart;
    const selectionEnd = markdownEditor.selectionEnd;
    const selectedText = markdownEditor.value.substring(selectionStart, selectionEnd);

    if (!selectedText.trim()) {
        showNotification("请先在编辑器中选择需要修改的文本。", 'warning');
        return;
    }

    currentEditorSelection = {
        text: selectedText,
        start: selectionStart,
        end: selectionEnd,
        originalContent: markdownEditor.value,
        editorId: isModalEditor ? 'modalMarkdownEditor' : 'markdownEditor'
    };

    const aiCommandPanel = document.getElementById('aiCommandPanel');
    const aiSelectedTextPreview = document.getElementById('aiSelectedTextPreview');
    
    aiSelectedTextPreview.textContent = selectedText;
    
    resetAIPanel();
    aiCommandPanel.classList.add('show');
    document.getElementById('aiCommandInput').focus();
    
    console.log('✅ AI编辑模式已启动，使用编辑器:', isModalEditor ? '模态窗口' : '侧边栏');
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
    try {
        console.log('📤 发送AI编辑请求:', { text, command });
        
        // 获取当前项目名称
        let projectName = "GauzDocument-Agent"; // 默认项目名称
        
        // 尝试从全局变量获取当前项目名称
        if (typeof currentProject !== 'undefined' && currentProject && currentProject.name) {
            projectName = currentProject.name;
            console.log('📋 使用当前项目名称:', projectName);
        } else {
            // 尝试从localStorage获取
            try {
                const savedProject = localStorage.getItem('currentProject');
                if (savedProject) {
                    const project = JSON.parse(savedProject);
                    if (project && project.name) {
                        projectName = project.name;
                        console.log('📋 从localStorage获取项目名称:', projectName);
                    }
                }
            } catch (error) {
                console.warn('⚠️ 无法从localStorage获取项目信息:', error);
            }
        }
        
        // 构建请求数据
        const requestData = {
            plain_text: [text], // 后端期望的是字符串数组
            request: command,
            project_name: projectName, // 动态获取的项目名称
            search_type: "hybrid",
            top_k: 5
        };
        
        console.log('📤 AI编辑请求数据:', requestData);
        
        // 发送POST请求到后端API
        const response = await fetch('http://localhost:8001/api/ai-editor/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('📥 AI编辑响应:', result);
        
        if (result.success) {
            return result.result;
        } else {
            throw new Error(result.error || '未知错误');
        }
        
    } catch (error) {
        console.error('❌ AI编辑API调用失败:', error);
        // 显示错误通知
        if (typeof showNotification === 'function') {
            showNotification(`AI编辑失败: ${error.message}`, 'error');
        }
        // 返回原文本作为fallback
        return text;
    }
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
    const markdownEditor = document.getElementById(currentEditorSelection.editorId || 'markdownEditor');
    if (!markdownEditor) {
        showNotification("编辑器不可用。", 'error');
        return;
    }
    
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

// ⭐️ AI编辑提示气泡功能 ⭐️
let aiEditTooltip = null;
let tooltipTimeout = null;
let globalClickHandler = null; // 跟踪全局点击监听器

// 创建AI编辑提示气泡
function createAIEditTooltip(x, y) {
    console.log('🎈 开始创建气泡，位置:', x, y);
    
    // 移除已存在的气泡
    removeAIEditTooltip();
    
    // 获取当前选中的文本
    const selectedText = getSelectedText();
    const displayText = selectedText ? selectedText.substring(0, 50) + (selectedText.length > 50 ? '...' : '') : '未选中文本';
    
    const tooltip = document.createElement('div');
    tooltip.id = 'aiEditTooltip';
    tooltip.className = 'ai-edit-tooltip';
    tooltip.innerHTML = `
        <div class="tooltip-content">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <span class="tooltip-icon">🤖</span>
                <span class="tooltip-text">AI编辑</span>
            </div>
            <div style="display: none; font-size: 12px; color: #666; background: #f5f5f5; padding: 6px 8px; border-radius: 4px; border-left: 3px solid #007acc;">
                <strong>选中文本:</strong> ${displayText}
            </div>
        </div>
    `;
    
    // 设置位置
    tooltip.style.left = x + 'px';
    tooltip.style.top = (y - 50) + 'px';
    
    console.log('📍 气泡样式设置:', tooltip.style.left, tooltip.style.top);
    
    // 添加点击事件
    tooltip.addEventListener('click', () => {
        console.log('👆 气泡被点击');
        // 转换为输入框模式
        transformTooltipToInput(tooltip, x, y);
    });
    
    document.body.appendChild(tooltip);
    aiEditTooltip = tooltip;
    
    console.log('✅ 气泡已添加到DOM');
    
    // 添加淡入动画
    setTimeout(() => {
        tooltip.classList.add('show');
        console.log('🎭 气泡显示动画已触发');
        
        // 检查气泡是否真的可见
        const computedStyle = window.getComputedStyle(tooltip);
        console.log('🔍 气泡计算样式:', {
            opacity: computedStyle.opacity,
            display: computedStyle.display,
            visibility: computedStyle.visibility,
            zIndex: computedStyle.zIndex,
            position: computedStyle.position,
            left: computedStyle.left,
            top: computedStyle.top
        });
        
        // 检查气泡是否在视口内
        const rect = tooltip.getBoundingClientRect();
        console.log('📐 气泡位置信息:', {
            rect: rect,
            inViewport: rect.top >= 0 && rect.left >= 0 && 
                       rect.bottom <= window.innerHeight && 
                       rect.right <= window.innerWidth
        });
    }, 100);
    
    // 5秒后自动消失（仅对气泡有效，输入框状态不会自动消失）
    tooltipTimeout = setTimeout(() => {
        // 检查是否已经转换为输入框
        const inputContainer = document.getElementById('aiEditInputContainer');
        if (!inputContainer) {
            console.log('⏰ 气泡自动消失（未转换为输入框）');
            removeAIEditTooltip();
        } else {
            console.log('⏰ 气泡已转换为输入框，取消自动消失');
        }
    }, 5000);
}

// 将气泡转换为输入框 - 重新设计的简化版本
function transformTooltipToInput(tooltip, x, y) {
    console.log('🔄 转换气泡为输入框 - 新版本');
    
    // 清除自动消失的定时器
    if (tooltipTimeout) {
        clearTimeout(tooltipTimeout);
        tooltipTimeout = null;
    }
    
    // 移除原气泡
    if (tooltip && tooltip.parentNode) {
        tooltip.parentNode.removeChild(tooltip);
    }
    
    // 创建输入框容器 - 使用最简单的方式
    const inputContainer = document.createElement('div');
    inputContainer.id = 'aiEditInputContainer';
    inputContainer.className = 'ai-edit-input-container show'; // 直接添加show类
    inputContainer.style.cssText = `
        position: fixed;
        left: ${x}px;
        top: ${y - 60}px;
        z-index: 10000;
        background: white;
        border: 2px solid #007acc;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        min-width: 300px;
        max-width: 400px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;
    
    // 获取当前选中的文本
    const selectedText = getSelectedText();
    const displayText = selectedText ? selectedText.substring(0, 100) + (selectedText.length > 100 ? '...' : '') : '未选中文本';
    
    inputContainer.innerHTML = `
        <div style="padding: 12px; border-bottom: 1px solid #eee; display: flex; align-items: center; justify-content: space-between; background: #f8f9fa; border-radius: 6px 6px 0 0;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 16px;">🤖</span>
                <span style="font-weight: 600; color: #333;">AI编辑指令</span>
            </div>
            <button id="closeAIInput" style="background: none; border: none; font-size: 18px; cursor: pointer; color: #666; padding: 4px; border-radius: 4px;" onmouseover="this.style.background='#eee'" onmouseout="this.style.background='none'">×</button>
        </div>
        <div style="padding: 16px;">
            <div style="margin-bottom: 12px; padding: 10px; background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; border-left: 4px solid #007acc;">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px; font-weight: 600;">📝 当前选中的文本:</div>
                <div style="font-size: 13px; color: #333; line-height: 1.4; max-height: 60px; overflow-y: auto; white-space: pre-wrap;">${displayText}</div>
            </div>
            <textarea id="quickAICommand" placeholder="请描述您希望AI如何修改上述选中的文本..." rows="3" style="width: 100%; border: 1px solid #ddd; border-radius: 4px; padding: 8px; font-size: 14px; resize: vertical; outline: none; box-sizing: border-box;"></textarea>
            <div style="margin-top: 12px; display: flex; gap: 8px; justify-content: flex-end;">
                <button id="cancelAIInput" style="padding: 8px 16px; border: 1px solid #ddd; background: white; border-radius: 4px; cursor: pointer; font-size: 14px;">取消</button>
                <button id="confirmAIInput" class="input-btn confirm" style="padding: 8px 16px; border: none; background: #007acc; color: white; border-radius: 4px; cursor: pointer; font-size: 14px;">✨ 生成</button>
            </div>
        </div>
    `;
    
    // 添加到页面
    document.body.appendChild(inputContainer);
    aiEditTooltip = inputContainer;
    
    // 绑定关闭事件 - 只通过按钮关闭
    const closeBtn = inputContainer.querySelector('#closeAIInput');
    const cancelBtn = inputContainer.querySelector('#cancelAIInput');
    const confirmBtn = inputContainer.querySelector('#confirmAIInput');
    const textarea = inputContainer.querySelector('#quickAICommand');
    
    closeBtn.onclick = () => {
        console.log('🗑️ 用户点击关闭按钮');
        removeAIEditTooltip();
    };
    
    cancelBtn.onclick = () => {
        console.log('🗑️ 用户点击取消按钮');
        removeAIEditTooltip();
    };
    
    confirmBtn.onclick = () => {
        console.log('✨ 用户点击生成按钮');
        processQuickAIEdit();
    };
    
    // 阻止容器内的点击事件冒泡
    inputContainer.onclick = (e) => {
        e.stopPropagation();
    };
    
    // 聚焦到输入框
    setTimeout(() => {
        textarea.focus();
        console.log('✅ 输入框已创建并聚焦，永久显示直到用户主动关闭');
    }, 100);
    
    // 强制保持显示的机制 - 定期检查并恢复
    const keepAliveInterval = setInterval(() => {
        const container = document.getElementById('aiEditInputContainer');
        if (!container && aiEditTooltip) {
            console.log('⚠️ 检测到输入框被意外移除，正在恢复...');
            // 如果容器被意外移除，重新添加
            if (aiEditTooltip.parentNode !== document.body) {
                document.body.appendChild(aiEditTooltip);
            }
        }
    }, 1000);
    
    // 将定时器ID保存到容器上，以便清理
    inputContainer.keepAliveInterval = keepAliveInterval;
    
    console.log('🛡️ 输入框保护机制已启动');
}

// 处理快速AI编辑
async function processQuickAIEdit() {
    const quickAICommand = document.getElementById('quickAICommand');
    const command = quickAICommand ? quickAICommand.value.trim() : '';
    
    if (!command) {
        showNotification('请输入编辑指令', 'warning');
        return;
    }
    
    console.log('🚀 开始处理快速AI编辑:', command);
    
    // 获取当前活跃的编辑器
    let activeEditor = document.getElementById('markdownEditor');
    const modalEditor = document.getElementById('modalMarkdownEditor');
    
    // 如果模态编辑器存在且可见，优先使用模态编辑器
    if (modalEditor && modalEditor.offsetParent !== null) {
        activeEditor = modalEditor;
    }
    
    if (!activeEditor) {
        showNotification('未找到活跃的编辑器', 'error');
        return;
    }
    
    const selectionStart = activeEditor.selectionStart;
    const selectionEnd = activeEditor.selectionEnd;
    const selectedText = activeEditor.value.substring(selectionStart, selectionEnd);
    
    if (!selectedText.trim()) {
        showNotification('请先选择要编辑的文本', 'warning');
        return;
    }
    
    // 更新当前编辑选择
    currentEditorSelection = {
        text: selectedText,
        start: selectionStart,
        end: selectionEnd,
        originalContent: activeEditor.value,
        editorId: activeEditor.id
    };
    
    // 显示加载状态
    const confirmBtn = document.querySelector('.input-btn.confirm');
    if (confirmBtn) {
        confirmBtn.innerHTML = `
            <div style="display: inline-flex; align-items: center; gap: 8px;">
                <div class="ai-loading-spinner" style="
                    width: 16px;
                    height: 16px;
                    border: 2px solid rgba(255,255,255,0.3);
                    border-radius: 50%;
                    border-top-color: white;
                    animation: spin 1s ease-in-out infinite;
                "></div>
                <span>处理中...</span>
            </div>
        `;
        confirmBtn.disabled = true;
        confirmBtn.style.opacity = '0.8';
        confirmBtn.style.cursor = 'not-allowed';
    }
    
    // 添加旋转动画样式（如果还没有的话）
    if (!document.getElementById('ai-loading-styles')) {
        const style = document.createElement('style');
        style.id = 'ai-loading-styles';
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
    
    try {
        // 调用AI编辑API
        const modifiedText = await callAIEditorAPI(selectedText, command);
        
        // 显示差异对比界面
        showDiffComparison(selectedText, modifiedText, activeEditor, selectionStart, selectionEnd);
        
        // 恢复确认按钮状态
        if (confirmBtn) {
            confirmBtn.innerHTML = '✨ 生成';
            confirmBtn.disabled = false;
            confirmBtn.style.opacity = '1';
            confirmBtn.style.cursor = 'pointer';
        }
        
        console.log('✅ 快速AI编辑完成，等待用户确认');
        
    } catch (error) {
        console.error('❌ 快速AI编辑失败:', error);
        showNotification('AI编辑失败: ' + error.message, 'error');
        
        // 恢复按钮状态
        if (confirmBtn) {
            confirmBtn.innerHTML = '✨ 生成';
            confirmBtn.disabled = false;
            confirmBtn.style.opacity = '1';
            confirmBtn.style.cursor = 'pointer';
        }
    }
}

// 显示差异对比界面
function showDiffComparison(originalText, modifiedText, activeEditor, selectionStart, selectionEnd) {
    // 创建diff_match_patch实例
    const dmp = new diff_match_patch();
    
    // 生成差异
    const diffs = dmp.diff_main(originalText, modifiedText);
    dmp.diff_cleanupSemantic(diffs);
    
    // 生成HTML格式的差异显示
    const diffHtml = dmp.diff_prettyHtml(diffs);
    
    // 创建差异显示容器
    const diffContainer = document.createElement('div');
    diffContainer.id = 'aiDiffContainer';
    diffContainer.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 80%;
        max-width: 800px;
        max-height: 70vh;
        background: white;
        border: 2px solid #007acc;
        border-radius: 8px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        z-index: 10000;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    `;
    
    // 创建标题栏
    const titleBar = document.createElement('div');
    titleBar.style.cssText = `
        background: linear-gradient(135deg, #007acc, #005a9e);
        color: white;
        padding: 12px 16px;
        font-weight: bold;
        font-size: 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    `;
    titleBar.innerHTML = `
        <span>📝 AI编辑差异对比</span>
        <button id="closeDiffBtn" style="
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
        ">×</button>
    `;
    
    // 创建内容区域
    const contentArea = document.createElement('div');
    contentArea.style.cssText = `
        flex: 1;
        overflow-y: auto;
        padding: 16px;
    `;
    
    // 创建说明文字
    const description = document.createElement('div');
    description.style.cssText = `
        margin-bottom: 16px;
        padding: 12px;
        background: #f8f9fa;
        border-radius: 6px;
        font-size: 14px;
        color: #666;
    `;
    description.innerHTML = `
        <strong>差异说明：</strong>
        <span style="background: #ffe6e6; padding: 2px 4px; border-radius: 3px; margin: 0 4px;">红色删除线</span>表示删除的内容，
        <span style="background: #e6ffe6; padding: 2px 4px; border-radius: 3px; margin: 0 4px;">绿色下划线</span>表示新增的内容
    `;
    
    // 创建差异显示区域
    const diffDisplay = document.createElement('div');
    diffDisplay.style.cssText = `
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 16px;
        background: #fafafa;
        font-family: 'Courier New', monospace;
        font-size: 14px;
        line-height: 1.6;
        white-space: pre-wrap;
        word-wrap: break-word;
        margin-bottom: 16px;
        max-height: 300px;
        overflow-y: auto;
    `;
    diffDisplay.innerHTML = diffHtml;
    
    // 创建按钮区域
    const buttonArea = document.createElement('div');
    buttonArea.style.cssText = `
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        padding: 16px;
        border-top: 1px solid #eee;
        background: #f8f9fa;
    `;
    
    // 创建拒绝按钮
    const rejectBtn = document.createElement('button');
    rejectBtn.textContent = '❌ 拒绝修改';
    rejectBtn.style.cssText = `
        padding: 10px 20px;
        border: 2px solid #dc3545;
        background: white;
        color: #dc3545;
        border-radius: 6px;
        cursor: pointer;
        font-weight: bold;
        transition: all 0.2s;
    `;
    rejectBtn.onmouseover = () => {
        rejectBtn.style.background = '#dc3545';
        rejectBtn.style.color = 'white';
    };
    rejectBtn.onmouseout = () => {
        rejectBtn.style.background = 'white';
        rejectBtn.style.color = '#dc3545';
    };
    
    // 创建接受按钮
    const acceptBtn = document.createElement('button');
    acceptBtn.textContent = '✅ 接受修改';
    acceptBtn.style.cssText = `
        padding: 10px 20px;
        border: 2px solid #28a745;
        background: #28a745;
        color: white;
        border-radius: 6px;
        cursor: pointer;
        font-weight: bold;
        transition: all 0.2s;
    `;
    acceptBtn.onmouseover = () => {
        acceptBtn.style.background = '#218838';
        acceptBtn.style.borderColor = '#218838';
    };
    acceptBtn.onmouseout = () => {
        acceptBtn.style.background = '#28a745';
        acceptBtn.style.borderColor = '#28a745';
    };
    
    // 组装界面
    contentArea.appendChild(description);
    contentArea.appendChild(diffDisplay);
    buttonArea.appendChild(rejectBtn);
    buttonArea.appendChild(acceptBtn);
    diffContainer.appendChild(titleBar);
    diffContainer.appendChild(contentArea);
    diffContainer.appendChild(buttonArea);
    
    // 添加到页面
    document.body.appendChild(diffContainer);
    
    // 绑定事件
    const closeDiff = () => {
        if (diffContainer.parentNode) {
            diffContainer.parentNode.removeChild(diffContainer);
        }
    };
    
    // 关闭按钮事件
    document.getElementById('closeDiffBtn').onclick = closeDiff;
    
    // 拒绝修改事件
    rejectBtn.onclick = () => {
        closeDiff();
        showNotification('已拒绝修改', 'info');
        
        // 清空输入框
        const quickAICommandInput = document.getElementById('quickAICommand');
        if (quickAICommandInput) {
            quickAICommandInput.value = '';
            quickAICommandInput.placeholder = '请输入AI编辑指令...';
        }
    };
    
    // 接受修改事件
    acceptBtn.onclick = () => {
        // 应用修改
        activeEditor.value = currentEditorSelection.originalContent.substring(0, selectionStart) + 
                            modifiedText + 
                            currentEditorSelection.originalContent.substring(selectionEnd);
        
        // 触发输入事件以更新预览
        activeEditor.dispatchEvent(new Event('input', { bubbles: true }));
        
        // 清空输入框内容，但保持显示状态
        const quickAICommandInput = document.getElementById('quickAICommand');
        if (quickAICommandInput) {
            quickAICommandInput.value = '';
            quickAICommandInput.placeholder = '编辑完成！可继续输入新指令或点击关闭按钮';
        }
        
        closeDiff();
        showNotification('AI编辑完成', 'success');
    };
    
    // ESC键关闭
    const handleKeyDown = (e) => {
        if (e.key === 'Escape') {
            closeDiff();
            document.removeEventListener('keydown', handleKeyDown);
        }
    };
    document.addEventListener('keydown', handleKeyDown);
    
    // 点击背景关闭（可选）
    diffContainer.onclick = (e) => {
        if (e.target === diffContainer) {
            closeDiff();
        }
    };
}

// 导出新函数到全局
window.transformTooltipToInput = transformTooltipToInput;
window.processQuickAIEdit = processQuickAIEdit;

// 移除AI编辑提示气泡 - 增强版本，确保完全清理
function removeAIEditTooltip() {
    console.log('🗑️ 开始移除AI编辑提示气泡（用户主动操作）');
    
    // 清理所有可能存在的气泡和输入框元素
    const elementsToRemove = [
        aiEditTooltip,
        document.getElementById('aiEditTooltip'),
        document.getElementById('aiEditInputContainer')
    ].filter(Boolean);
    
    elementsToRemove.forEach(element => {
        if (element) {
            console.log('📦 找到元素，类型:', element.className, 'ID:', element.id);
            
            // 清理保活定时器
            if (element.keepAliveInterval) {
                console.log('🧹 清理保活定时器');
                clearInterval(element.keepAliveInterval);
                element.keepAliveInterval = null;
            }
            
            // 立即移除元素，不使用动画
            if (element.parentNode) {
                console.log('🔥 从DOM中移除元素，ID:', element.id);
                element.parentNode.removeChild(element);
            }
            
            console.log('✅ 元素已清理');
        }
    });
    
    // 重置全局变量
    aiEditTooltip = null;
    
    // 清理自动消失定时器
    if (tooltipTimeout) {
        console.log('⏰ 清除自动消失定时器');
        clearTimeout(tooltipTimeout);
        tooltipTimeout = null;
    }
    
    // 清理全局点击监听器（如果存在）
    if (globalClickHandler) {
        console.log('🧹 清理全局点击监听器');
        document.removeEventListener('click', globalClickHandler);
        globalClickHandler = null;
    }
    
    console.log('🧹 移除流程完成，所有资源已清理');
}

// 检测复制/剪切操作 - 简化版本，移除自动关闭逻辑
function detectCopyPasteOperations() {
    const addEditorListeners = (editor) => {
        if (!editor) return;
        
        editor.addEventListener('keydown', (e) => {
            // 只在粘贴操作时移除气泡，因为粘贴会改变文本内容
            if (e.ctrlKey && e.key === 'v') {
                // 只有在气泡状态时才移除，输入框状态不移除
                const tooltip = document.getElementById('aiEditTooltip');
                if (tooltip && !document.getElementById('aiEditInputContainer')) {
                    console.log('📋 检测到粘贴操作，移除气泡');
                    removeAIEditTooltip();
                }
            }
            // 复制和剪切操作不移除气泡，让用户有机会使用AI编辑功能
        });
        
        // 完全移除blur事件的自动关闭逻辑
        // 输入框现在只能通过用户主动点击关闭按钮来关闭
        editor.addEventListener('blur', () => {
            console.log('📝 编辑器失去焦点，但不执行任何自动关闭操作');
            // 不执行任何移除操作，确保输入框稳定显示
        });
    };
    
    // 为侧边栏编辑器添加监听
    const markdownEditor = document.getElementById('markdownEditor');
    addEditorListeners(markdownEditor);
    
    // 为模态窗口编辑器添加监听
    const modalMarkdownEditor = document.getElementById('modalMarkdownEditor');
    addEditorListeners(modalMarkdownEditor);
    
    // 监听DOM变化，为新创建的模态编辑器添加监听
    const observer = new MutationObserver(() => {
        const newModalEditor = document.getElementById('modalMarkdownEditor');
        if (newModalEditor && !newModalEditor.hasCopyPasteListener) {
            addEditorListeners(newModalEditor);
            newModalEditor.hasCopyPasteListener = true;
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
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
