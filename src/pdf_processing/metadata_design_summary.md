# PDF Processing 元数据设计总结

## 🎯 需求分析与解决方案

### 用户核心需求
根据您的要求，PDF Processing模块需要支持：

1. **document summary** - 文档级摘要
2. **chapter summary** - 章节级摘要  
3. **minimal chunk** - 最小颗粒度分块（包括图片和表格描述）
4. **衍生问题** - 每个章节3-5个相关问题
5. **统一元数据** - 所有内容使用统一的元数据结构
6. **embedding支持** - 所有内容都可以embedding到向量空间
7. **图表路径** - 图片和表格需要file_path用于插入

### 解决方案概述

我们设计了一个**统一的元数据结构 (`UnifiedMetadata`)**，通过`content_type`和`content_level`字段来区分不同类型和层级的内容。

## 📋 完整的元数据映射

### 1. 内容类型映射 (`ContentType`)

| 用户需求 | 系统类型 | 描述 | 示例 |
|----------|----------|------|------|
| document summary | `DOCUMENT_SUMMARY` | 文档级摘要 | 整个论文的概述 |
| chapter summary | `CHAPTER_SUMMARY` | 章节级摘要 | 第2.1节的概述 |
| text chunk | `TEXT_CHUNK` | 文本块 | 段落、列表项等 |
| image chunk | `IMAGE_CHUNK` | 图片块 | 图片的AI描述 |
| table chunk | `TABLE_CHUNK` | 表格块 | 表格的AI描述 |
| 衍生问题 | `DERIVED_QUESTION` | 章节相关问题 | "AlphaEvolve如何工作？" |

### 2. 内容层级映射 (`ContentLevel`)

| 层级 | 用途 | 包含内容 |
|------|------|----------|
| `DOCUMENT` | 文档级别 | document_summary |
| `CHAPTER` | 章节级别 | chapter_summary |
| `CHUNK` | 块级别 | text_chunk, image_chunk, table_chunk |
| `QUESTION` | 问题级别 | derived_question |

### 3. 统一元数据字段

```python
@dataclass
class UnifiedMetadata:
    # === 基础标识 === 
    content_id: str                    # 唯一标识
    document_id: str                   # 文档ID
    content_type: ContentType          # 内容类型
    content_level: ContentLevel        # 内容层级
    
    # === 层级关系 ===
    chapter_id: Optional[str]          # 章节ID ("1", "2.1", "3.2.1")
    chapter_title: Optional[str]       # 章节标题
    chapter_level: Optional[int]       # 章节数字层级 (1, 2, 3...)
    
    # === 内容信息 ===
    content: str                       # 实际内容/描述
    document_title: Optional[str]      # 文档标题
    document_summary: Optional[str]    # 文档摘要
    
    # === 位置信息 ===
    page_number: Optional[int]         # 页码
    position_in_chapter: Optional[int] # 章节内位置
    
    # === 媒体文件信息 ===
    file_path: Optional[str]           # 文件路径 (图片/表格)
    file_size: Optional[int]           # 文件大小
    file_format: Optional[str]         # 文件格式
    image_dimensions: Optional[str]    # 图片尺寸
    
    # === 质量信息 ===
    ai_description_confidence: Optional[float]  # AI描述置信度
    content_quality_score: Optional[float]     # 内容质量分数
    
    # === 检索优化 ===
    keywords: Optional[List[str]]      # 关键词
    tags: Optional[List[str]]          # 标签
    
    # === 关联关系 ===
    related_images: Optional[List[str]]    # 相关图片
    related_tables: Optional[List[str]]    # 相关表格
    derived_questions: Optional[List[str]] # 衍生问题
```

## 🎯 具体使用示例

### 1. 文档摘要 (Document Summary)
```python
doc_summary = create_document_summary_metadata(
    document_id="alphaevolve_2024",
    document_title="AlphaEvolve: A coding agent for scientific discovery",
    content="AlphaEvolve是一个用于科学和算法发现的编程智能体，通过生成代码来解决复杂问题...",
    content_summary="AlphaEvolve系统介绍",
    total_pages=44
)
# 结果：content_type=DOCUMENT_SUMMARY, content_level=DOCUMENT
```

### 2. 章节摘要 (Chapter Summary)
```python
chapter_summary = create_chapter_summary_metadata(
    document_id="alphaevolve_2024",
    chapter_id="2.1",
    chapter_title="Task specification", 
    chapter_level=2,
    content="任务规范部分详细描述了AlphaEvolve的任务定义和处理流程...",
    content_summary="任务规范章节",
    document_title="AlphaEvolve: A coding agent for scientific discovery",
    document_summary="AlphaEvolve系统介绍"
)
# 结果：content_type=CHAPTER_SUMMARY, content_level=CHAPTER
```

### 3. 文本块 (Text Chunk)
```python
text_chunk = create_text_chunk_metadata(
    document_id="alphaevolve_2024",
    chunk_id="chunk_001",
    chapter_id="2.1",
    chapter_title="Task specification",
    chapter_level=2,
    content="AlphaEvolve通过生成代码来解决科学问题，支持多种编程语言...",
    page_number=5,
    position_in_chapter=1,
    document_title="AlphaEvolve: A coding agent for scientific discovery",
    document_summary="AlphaEvolve系统介绍"
)
# 结果：content_type=TEXT_CHUNK, content_level=CHUNK
```

### 4. 图片块 (Image Chunk) - 包含file_path
```python
image_chunk = create_image_chunk_metadata(
    document_id="alphaevolve_2024",
    image_id="img_001",
    chapter_id="2.1",
    chapter_title="Task specification",
    chapter_level=2,
    ai_description="系统架构图显示了AlphaEvolve的主要组件和数据流",
    file_path="parser_output/alphaevolve_2024/picture-1.png",  # 用于插入
    page_number=5,
    position_in_chapter=2,
    document_title="AlphaEvolve: A coding agent for scientific discovery",
    document_summary="AlphaEvolve系统介绍",
    file_size=1024000,
    file_format="png",
    image_dimensions="800x600"
)
# 结果：content_type=IMAGE_CHUNK, content_level=CHUNK, file_path可用于插入
```

### 5. 表格块 (Table Chunk) - 包含file_path
```python
table_chunk = create_table_chunk_metadata(
    document_id="alphaevolve_2024",
    table_id="table_001",
    chapter_id="3.1",
    chapter_title="Results",
    chapter_level=2,
    ai_description="实验结果表格显示了不同算法的性能对比，包括准确率和执行时间",
    file_path="parser_output/alphaevolve_2024/table-1.png",   # 用于插入
    page_number=15,
    position_in_chapter=1,
    document_title="AlphaEvolve: A coding agent for scientific discovery",
    document_summary="AlphaEvolve系统介绍",
    file_size=2048000,
    file_format="png"
)
# 结果：content_type=TABLE_CHUNK, content_level=CHUNK, file_path可用于插入
```

### 6. 衍生问题 (Derived Questions)
```python
derived_questions = [
    create_derived_question_metadata(
        document_id="alphaevolve_2024",
        question_id="q_001",
        chapter_id="2.1",
        chapter_title="Task specification",
        chapter_level=2,
        question_content="AlphaEvolve如何处理复杂的科学计算任务？",
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        document_summary="AlphaEvolve系统介绍"
    ),
    create_derived_question_metadata(
        document_id="alphaevolve_2024",
        question_id="q_002",
        chapter_id="2.1",
        chapter_title="Task specification", 
        chapter_level=2,
        question_content="任务规范中包含哪些关键要素？",
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        document_summary="AlphaEvolve系统介绍"
    )
    # ... 3-5个问题
]
# 结果：content_type=DERIVED_QUESTION, content_level=QUESTION
```

## 🗄️ 向量数据库存储

### 所有内容都支持embedding
```python
# 所有类型的内容都可以embedding并存储到向量数据库
embedding_contents = [
    doc_summary,      # 文档摘要 - embedding
    chapter_summary,  # 章节摘要 - embedding
    text_chunk,       # 文本块 - embedding
    image_chunk,      # 图片描述 - embedding
    table_chunk,      # 表格描述 - embedding
    *derived_questions # 衍生问题 - embedding
]

# 批量存储到向量数据库
for content in embedding_contents:
    vector_db.add(
        ids=[content.content_id],
        embeddings=[embed_text(content.content)],
        metadatas=[{
            "content_id": content.content_id,
            "document_id": content.document_id,
            "chapter_id": content.chapter_id,
            "content_type": content.content_type.value,
            "content_level": content.content_level.value,
            "file_path": content.file_path,  # 图片/表格的路径
            "keywords": content.keywords,
            "tags": content.tags
        }],
        documents=[content.content]
    )
```

## 🔍 检索场景支持

### 1. 小块检索
```python
# 精确检索文本块
text_results = vector_db.query(
    query_texts=["AlphaEvolve的工作原理"],
    where={"content_type": "text_chunk"},
    n_results=5
)

# 检索图片描述
image_results = vector_db.query(
    query_texts=["系统架构图"],
    where={"content_type": "image_chunk"},
    n_results=3
)
```

### 2. 大块喂养
```python
# 基于小块检索结果，获取完整章节上下文
for result in text_results['metadatas']:
    chapter_id = result['chapter_id']
    document_id = result['document_id']
    
    # 获取整个章节的所有内容
    chapter_context = get_chapter_context(chapter_id, document_id)
    # 包含：章节摘要、所有文本块、图片、表格、衍生问题
```

### 3. 多模态检索
```python
# 同时检索文本、图片、表格
multimodal_results = vector_db.query(
    query_texts=["实验结果分析"],
    where={"content_type": {"$in": ["text_chunk", "image_chunk", "table_chunk"]}},
    n_results=10
)
```

## 🎨 建议的字段名改进

基于您的需求，我建议以下字段名优化：

| 原字段名 | 建议字段名 | 理由 |
|----------|------------|------|
| `content_level` | `content_tier` 或 `hierarchy_level` | 更直观地表示层级关系 |
| `derived_question` | `synthetic_question` 或 `generated_question` | 更准确地描述问题来源 |
| `ai_description_confidence` | `description_confidence` | 简化字段名 |
| `position_in_chapter` | `chapter_position` 或 `sequence_in_chapter` | 更清晰的位置表示 |

## 🚀 扩展性设计

### 1. 新内容类型支持
```python
# 未来可以轻松添加新的内容类型
class ContentType(Enum):
    # 现有类型
    DOCUMENT_SUMMARY = "document_summary"
    CHAPTER_SUMMARY = "chapter_summary"
    TEXT_CHUNK = "text_chunk"
    IMAGE_CHUNK = "image_chunk"
    TABLE_CHUNK = "table_chunk"
    DERIVED_QUESTION = "derived_question"
    
    # 未来扩展
    FORMULA_CHUNK = "formula_chunk"        # 数学公式
    CODE_CHUNK = "code_chunk"              # 代码片段
    REFERENCE_CHUNK = "reference_chunk"    # 引用信息
```

### 2. 自定义元数据
```python
# 通过extra_metadata字段支持自定义元数据
custom_metadata = UnifiedMetadata(
    # ... 标准字段
    extra_metadata={
        "domain": "machine_learning",
        "complexity": "advanced",
        "citation_count": 150,
        "custom_tags": ["deep_learning", "NLP"]
    }
)
```

## ✅ 需求满足确认

- ✅ **document summary** - 通过`DOCUMENT_SUMMARY`类型支持
- ✅ **chapter summary** - 通过`CHAPTER_SUMMARY`类型支持
- ✅ **minimal chunk** - 通过`TEXT_CHUNK`、`IMAGE_CHUNK`、`TABLE_CHUNK`类型支持
- ✅ **衍生问题** - 通过`DERIVED_QUESTION`类型支持，属于`QUESTION`层级
- ✅ **统一元数据** - 所有内容使用`UnifiedMetadata`结构
- ✅ **embedding支持** - 所有内容都可以embedding到向量空间
- ✅ **图表路径** - `file_path`字段专门用于图片/表格的插入路径
- ✅ **层级区分** - 通过`content_level`字段区分不同层级
- ✅ **章节关联** - 通过`chapter_id`、`chapter_title`、`chapter_level`字段关联

这个设计完全满足您的所有需求，并且具有良好的扩展性和维护性。 