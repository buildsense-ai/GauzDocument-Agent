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
├── stage2_parallel_processor.py    # 阶段2: 并行AI处理器
├── stage3_chunking_processor.py    # 阶段3: 内容分块处理器
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

### 阶段1: Docling解析 + 初始Schema填充 (3-4分钟)
**输入**: PDF文件路径
**输出**: 初始化的final_metadata.json

**处理内容**:
- 🔄 Docling解析PDF (不可避免的串行步骤)
- ✅ 创建complete final schema结构
- ✅ 填充document_summary基础信息 (包含full_raw_text作为content)
- ✅ 填充image_chunks基础信息 (除ai_description和chapter_id外)
- ✅ 填充table_chunks基础信息 (除ai_description和chapter_id外)
- ✅ 设置processing_status

**关键设计**:
- full_raw_text保存在document_summary.content中，用于后续处理和中断恢复
- 图片表格获得除AI描述和章节归属外的所有信息

### 阶段2: 并行AI处理 (2-3分钟)
**输入**: 阶段1的final_metadata.json
**输出**: 包含AI描述和TOC信息的final_metadata.json

**并行任务**:
- 🔄 2a: 图片/表格AI描述生成
- 🔄 2b: Document Summary AI摘要生成  
- 🔄 2c: TOC提取和章节关联

### 阶段3-5: 后续处理阶段
(详细设计将在前面阶段完成后补充)

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
  - [x] **完整性测试通过**: 12页PDF，10图片+3表格，100%成功

### 🔄 进行中  
- [ ] **阶段2设计**: 并行AI处理架构设计

### ⏳ 待完成
- [ ] 阶段2实现: 并行AI处理
- [ ] 阶段3实现: 内容分块  
- [ ] 阶段4实现: 章节摘要
- [ ] 阶段5实现: 问题生成
- [ ] 整体测试和验证

## 🧪 测试策略

每个阶段完成后都会进行独立测试:
1. **功能测试**: 阶段输入输出正确性
2. **完整性测试**: 数据一致性和媒体文件验证
3. **性能测试**: 处理时间和资源使用
4. **容错性测试**: 页面失败时的处理机制
5. **集成测试**: 与前后阶段的协作

**测试调整**:
- 优先进行完整性测试，暂时跳过恢复功能测试
- 使用保守的并行设置（CPU核心数的一半）
- 重点验证页码准确性和媒体标记正确性

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

### Final Schema结构
```python
{
    "document_summary": {
        "content_id": "doc_xxx_document_summary_1",
        "content": "full_raw_text",  # 🌟 关键设计
        "ai_summary": "AI生成的摘要",
        # ... 其他字段
    },
    "image_chunks": [...],
    "table_chunks": [...], 
    "text_chunks": [...],
    "chapter_summaries": [...],
    "derived_questions": [...],
    "processing_status": {
        "current_stage": "stage1",
        "completion_percentage": 30,
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

**阶段1测试成果**：
- 📊 测试用例：12页PDF（testfiles/测试文件.pdf）
- ⚡ 处理性能：5进程并行，53.74秒完成
- 🖼️ 媒体提取：10个图片 + 3个表格，100%成功率
- ✅ 页码准确性：所有媒体都有正确的页码标注
- ✅ 上下文准确性：每个媒体的page_context都是对应页面的真实文本
- ✅ 数据一致性：统计数据、chunks数据、实际文件数量完全一致
- ✅ JSON完整性：11994 bytes，重新加载验证100%通过

**下一步**：开始阶段2设计（并行AI处理）

---

*本文档将随着重构进度持续更新* 