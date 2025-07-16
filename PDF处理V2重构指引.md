# PDF处理V2重构指引

## 🎯 重构目标

将现有的线性10步pipeline重构为**渐进式填充Final Schema**的架构，提升容错性、可调试性和处理效率。

## 📋 核心设计原则

1. **Schema First**: 一开始就创建完整的final metadata schema文件
2. **渐进填充**: 每个阶段只负责填充自己能确定的字段  
3. **原子操作**: 每个阶段的更新都是原子的，失败不影响已有数据
4. **可续处理**: 任何阶段失败后，可以从该阶段重新开始
5. **进度可见**: 通过schema完整度实时显示处理进度

## 🏗️ 重构架构

```
src/pdf_processing_2/
├── __init__.py                     # 包初始化和导出
├── final_schema.py                 # Final Schema定义和管理
├── stage1_docling_processor.py     # 阶段1: Docling解析处理器
├── stage2_intelligent_processor.py # 阶段2: 智能修复与重组处理器
├── stage3_chunking_processor.py    # 阶段3: 内容分块处理器（可选/合并到Stage2）
├── stage4_summary_processor.py     # 阶段4: 章节摘要处理器
├── stage5_question_processor.py    # 阶段5: 问题生成处理器
├── shared/                         # 共享组件
│   ├── config.py                   # 配置管理
│   ├── utils.py                    # 工具函数
│   └── legacy_adapters.py          # 与V1版本的适配器
└── tests/                          # 阶段性测试
    ├── test_stage1.py
    ├── test_stage2.py
    └── ...
```

## 📊 处理阶段设计

### 阶段1: Docling解析 + 初始Schema填充 (3-4分钟) ✅ 已完成
**输入**: PDF文件路径
**输出**: 初始化的final_metadata.json

**处理内容**:
- 🔄 Docling解析PDF (不可避免的串行步骤)
- ✅ 创建complete final schema结构
- ✅ 填充document_summary基础信息 (包含full_raw_text作为content)
- ✅ 填充image_chunks基础信息 (除ai_description和chapter_id外)
- ✅ 填充table_chunks基础信息 (除ai_description和chapter_id外)
- ✅ 设置processing_status
- ✅ 实现重试机制和离线模式

**关键设计**:
- full_raw_text保存在document_summary.content中，用于后续处理和中断恢复
- 图片表格获得除AI描述和章节归属外的所有信息
- 使用content_id标记代替文件路径，便于后续关联
- 重试机制确保网络问题和单页失败的容错性

### 阶段2: 智能修复与重组 (5-8分钟)
**输入**: 阶段1的final_metadata.json
**输出**: 包含清理文本、TOC结构和text_chunks的final_metadata.json

**核心理念**: "修复与重组"而非"创作与总结"

#### 🔧 Step 2.1: 局部修复 (Page-Level) [2-3分钟]
**目标**: 修正OCR错误和局部格式问题，绝不进行任何形式的总结或改写

**输入**: `document_summary.page_texts` (逐页的原始文本)

**处理策略**:
- 并行处理每一页的raw_text
- 使用极其严格的AI prompt，唯一任务是"修复"而非"创作"
- 参考V1 ai_content_reorganizer.py的提示词风格：
  > - 保持原文完整性: 不删除任何内容，不改变原文表达，不进行意思解释或重组
  > - 输出要求: 纯文本格式，保持原文的完整结构和层次

**输出**: 在document_summary中增加 `cleaned_page_texts` 字段
- 同时保留原始的page_texts和修复后的版本
- 便于追溯和调试，风险可控

**典型修复内容**:
- OCR错误：自云区 → 白云区
- 格式问题：错误的换行和空格
- 字符识别：特殊符号和标点

#### 🗺️ Step 2.2: 全局结构识别 (Document-Level) [1-2分钟]
**目标**: 在修复好的文本基础上，重建整个文档的宏观结构（TOC）

**输入**: 从 `cleaned_page_texts` 拼接成的 `full_cleaned_text`

**处理策略**:
- 调用toc_extractor.py的逻辑，在更干净的文本上提取TOC
- 比在充满噪音的raw_text上提取准确得多
- 识别标题层级、章节边界、特殊结构

**输出**: 结构化的、可靠的文档目录
- 保存到 `document_summary.metadata.toc`
- 包含标题、层级、start_text等信息
- 为下一步的章节切分提供锚点

#### ✂️ Step 2.3: 内容提取与切分 (Chapter-Level) [2-3分钟]
**目标**: 基于识别出的文档结构，提取出忠于原文且干净的章节内容

**输入**: `full_cleaned_text` 和 `metadata.toc`

**处理策略**:
- **章节内容提取**: 使用TOC中的start_text作为锚点，从full_cleaned_text中精确切分出每个章节的完整、连续内容
- **智能分块**: 对每个章节内容，调用ai_chunker.py的逻辑进行语义边界分割
- **跨页修复**: 解决跨页段落被切断的问题

**输出**: `text_chunks` 列表
- 内容是经过"修复"但未被"创作"的
- 按逻辑结构组织，可直接用于Embedding
- 每个chunk都有对应的chapter_id

#### 🎨 Step 2.4: 多模态描述生成 (并行执行) [3-5分钟]
**目标**: 为图片和表格生成AI描述

**输入**: image_chunks, table_chunks, 和 `cleaned_page_texts` (作为上下文)

**处理策略**:
- 与Step 2.1并行执行，提升效率
- 使用修复后的cleaned_page_texts作为page_context
- 比使用原始文本更准确

**输出**: 填充image_chunks和table_chunks的ai_description字段

### 🔗 阶段2数据结构更新

#### document_summary新增字段:
```json
{
  "content": "使用content_id引用的full_text",  // 不再包含=== Page N ===
  "page_texts": {"1": "原始页面文本", ...},
  "cleaned_page_texts": {"1": "修复后页面文本", ...},  // 新增
  "metadata": {
    "toc": [
      {
        "title": "章节标题",
        "level": 1,
        "start_text": "定位锚点",
        "chapter_id": "chapter_1"
      }
    ]
  }
}
```

#### content字段格式更新:
```
原来: [IMAGE:parser_output_v2/page_1/picture-1.png:CAPTION:图表标题]
现在: [IMAGE:doc_xxx_image_1:CAPTION:图表标题]
```

### 阶段3-5: 后续处理阶段 (可选优化)
- **阶段3**: 可能合并到阶段2，或用于高级分块优化
- **阶段4**: 章节摘要和文档级摘要生成
- **阶段5**: 基于TOC和关键chunks的问题生成

## 📈 重构进度

### ✅ 已完成
- [x] 创建pdf_processing_2文件夹结构
- [x] 设计重构架构和阶段划分
- [x] 创建重构指引文档
- [x] **阶段1实现与验证**: Docling解析 + 初始Schema填充 🎉
  - [x] 创建FinalMetadataSchema类（支持渐进填充）
  - [x] 创建Stage1DoclingProcessor类
  - [x] **V2版本**: 采用页面切割方式，确保页码准确
  - [x] 实现并行处理（CPU核心数的一半，避免系统过载）
  - [x] 实现full_raw_text生成（含媒体标记）
  - [x] 实现Final Schema基础填充
  - [x] 修复Schema加载问题（完整恢复所有chunks）
  - [x] 创建完整性测试文件
  - [x] **完整性测试通过**: 31页PDF，28图片+3表格，100%成功
  - [x] **重试机制实现**: 最大3次重试，智能质量检查
  - [x] **离线模式配置**: 解决HuggingFace连接问题
  - [x] **简化测试脚本**: 适合Cursor窗口环境

### 🔄 进行中  
- [ ] **阶段2设计完成**: 智能修复与重组架构 ✅
- [ ] **阶段2实现**: 三步骤处理流程
  - [ ] Step 2.1: 局部修复处理器
  - [ ] Step 2.2: 全局结构识别器  
  - [ ] Step 2.3: 内容提取与切分器
  - [ ] Step 2.4: 多模态描述生成器

### ⏳ 待完成
- [ ] 阶段2测试和验证
- [ ] 阶段3实现: 高级内容分块（可选）
- [ ] 阶段4实现: 章节摘要
- [ ] 阶段5实现: 问题生成
- [ ] 整体测试和验证

## 🧪 测试策略

每个阶段完成后都会进行独立测试:
1. **功能测试**: 阶段输入输出正确性
2. **完整性测试**: 数据一致性和媒体文件验证
3. **性能测试**: 处理时间和资源使用
4. **容错性测试**: 失败重试和错误恢复
5. **集成测试**: 与前后阶段的协作

**Stage2特殊测试**:
- **修复质量测试**: OCR错误修正效果
- **结构识别测试**: TOC提取准确性
- **分块质量测试**: text_chunks的语义完整性
- **并行性能测试**: 多步骤并行执行效率

## 📝 实现细节

### 并行处理配置指南

#### 🎛️ 进程池 

**进程池模式 (推荐)**
```python
processor = Stage1DoclingProcessor(use_process_pool=True)
```
- ✅ 真正的并行计算，充分利用多核CPU
- ✅ 绕过Python GIL限制
- ✅ 进程隔离，单页失败不影响其他页面
- ⚠️ 进程启动开销较大，内存使用较高

#### 💡 智能配置建议

```python
import multiprocessing
cpu_cores = multiprocessing.cpu_count()
# 保守配置（适合工作时后台运行）
conservative_cores = max(1, cpu_cores // 4)
# 平衡配置（推荐）
balanced_cores = max(1, cpu_cores // 2)
# 激进配置（专门处理时）
aggressive_cores = max(1, cpu_cores - 1)
```

#### 🎯 实际使用示例

您的电脑有11核CPU，建议配置：
- 日常使用：5进程（45% CPU使用率）
- 急需速度：10进程（91% CPU使用率）
- 避免设置：11进程（100% CPU，电脑会卡）

### Final Schema结构 (更新)
```python
{
    "document_summary": {
        "content_id": "doc_xxx_document_summary_1",
        "content": "使用content_id引用的full_text",  # 🌟 更新：不含页面分隔符
        "page_texts": {"1": "原始页面文本", ...},
        "cleaned_page_texts": {"1": "修复后页面文本", ...},  # 🌟 新增
        "ai_summary": "AI生成的摘要",
        "metadata": {
            "toc": [...],  # 🌟 新增：文档结构
            # ... 其他元数据
        }
        # ... 其他字段
    },
    "image_chunks": [...],  # ai_description将被填充
    "table_chunks": [...],  # ai_description将被填充
    "text_chunks": [...],   # 🌟 新增：基于TOC的智能分块
    "chapter_summaries": [...],
    "derived_questions": [...],
    "processing_status": {
        "current_stage": "stage2",
        "completion_percentage": 60,
        "last_updated": "timestamp"
    }
}
```

## 🔄 更新日志

### 2025-01-16

#### 项目初始化
- 创建重构项目结构
- 设计核心架构和阶段划分
- 创建重构指引文档

#### 阶段1完成 🎉
- ✅ 实现FinalMetadataSchema类，支持渐进式填充和中断恢复
- ✅ 实现Stage1DoclingProcessor V2版本，采用页面切割方式
- ✅ 解决了原版本docling页码混乱的核心问题
- ✅ 实现并行处理（CPU核心数的一半），平衡性能和系统稳定性
- ✅ 实现full_raw_text生成，包含图片表格标记用于后续处理
- ✅ 实现Final Schema的基础信息填充（document_summary、image_chunks、table_chunks）
- ✅ 修复Schema加载问题，确保所有chunks都能正确恢复
- ✅ 创建完整的测试框架，验证数据一致性
- ✅ 实现重试机制，最大3次重试，智能质量检查
- ✅ 配置离线模式，解决HuggingFace连接问题
- ✅ 简化测试脚本，适合Cursor窗口环境

**阶段1测试成果**：
- 📊 测试用例：31页PDF（testfiles/医灵古庙设计方案.pdf）
- ⚡ 处理性能：5进程并行，322秒完成
- 🖼️ 媒体提取：28个图片 + 3个表格，100%成功率
- ✅ 页码准确性：所有媒体都有正确的页码标注
- ✅ 上下文准确性：每个媒体的page_context都是对应页面的真实文本
- ✅ 数据一致性：统计数据、chunks数据、实际文件数量完全一致
- ✅ JSON完整性：83,511 bytes，重新加载验证100%通过
- 🔄 重试机制：0次重试（离线模式完全生效）

#### 阶段2设计完成 🎯
- ✅ 采用"修复与重组"理念，降低AI创作风险
- ✅ 三步骤处理流程：局部修复 → 全局结构识别 → 内容提取与切分
- ✅ 新增cleaned_page_texts字段，保留修复版本
- ✅ content_id引用机制，替代文件路径
- ✅ 并行优化策略，提升处理效率
- ✅ 质量检查点设计，确保每步输出质量

**下一步**：开始阶段2实现（智能修复与重组处理器）

---

*本文档将随着重构进度持续更新* 