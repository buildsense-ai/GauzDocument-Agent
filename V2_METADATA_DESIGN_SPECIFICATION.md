# V2 Metadata设计规范

## 📋 设计概述

基于V2重构架构，本文档详细说明了Final Schema中各类metadata的具体用途，区分出：
1. **开发过程中的中间数据** - 用于调试、恢复、追溯
2. **Embedding内容数据** - 直接用于向量化和语义搜索  
3. **Filter元数据** - 用于语义搜索前的过滤和排序

## 🏗️ Final Schema完整结构

### DocumentSummary（文档摘要）
```python
@dataclass
class DocumentSummary:
    # === 核心标识 ===
    content_id: str                    # 🔍 FILTER - 唯一标识
    document_id: str                   # 🔍 FILTER - 文档ID
    content_type: str = "document_summary"  # 🔍 FILTER - 内容类型
    content_level: str = "document"    # 🔍 FILTER - 内容层级
    
    # === 中间数据（开发调试用）===
    full_raw_text: Optional[str] = None      # 🛠️ INTERMEDIATE - 完整原始文本
    page_texts: Optional[Dict[str, str]] = None          # 🛠️ INTERMEDIATE - 原始页面文本
    cleaned_page_texts: Optional[Dict[str, str]] = None  # 🛠️ INTERMEDIATE - 清洗后页面文本
    toc: Optional[List[Dict[str, Any]]] = None           # 🛠️ INTERMEDIATE - TOC结构数据
    metadata: Optional[Dict[str, Any]] = None            # 🛠️ INTERMEDIATE - 其他结构信息
    
    # === Embedding内容 ===
    ai_summary: Optional[str] = None         # 📄 EMBEDDING - AI生成的文档摘要（主要内容）
    
    # === Filter元数据（真正用于检索过滤）===
    source_file_path: str = ""         # 🔍 FILTER - 文件路径
    file_name: str = ""                # 🔍 FILTER - 文件名
    created_at: Optional[str] = None   # 🔍 FILTER - 创建时间
    
    # === 统计数据（开发优化用，偶尔检索）===
    total_pages: int = 0               # 📊 STATS - 总页数（偶尔用于检索：找短文档/长文档）
    image_count: int = 0               # 📊 STATS - 图片总数（偶尔用于检索：找图片丰富的文档）
    table_count: int = 0               # 📊 STATS - 表格总数（偶尔用于检索：找数据丰富的文档）
    
    # === 开发优化数据（中间数据性质）===
    file_size: int = 0                 # 🛠️ DEV_STATS - 文件大小（存储管理、性能分析）
    total_word_count: Optional[int] = None     # 🛠️ DEV_STATS - 总字数（处理性能分析）
    chapter_count: Optional[int] = None        # 🛠️ DEV_STATS - 章节数（结构分析统计）
    processing_time: float = 0.0       # 🛠️ DEV_STATS - 处理时间（性能优化）
    
    # === Embedding内容属性 ===
    @property
    def content(self) -> str:          # 📄 EMBEDDING - 实际用于embedding的内容
        """优先使用ai_summary，fallback到full_raw_text前2000字符"""
```

### ImageChunk（图片块）
```python
@dataclass
class ImageChunk:
    # === 核心标识 ===
    content_id: str                    # 🔍 FILTER - 唯一标识
    document_id: str                   # 🔍 FILTER - 文档ID
    content_type: str = "image_chunk"  # 🔍 FILTER - 内容类型
    content_level: str = "chunk"       # 🔍 FILTER - 内容层级
    
    # === Filter元数据 ===
    image_path: str = ""               # 🔍 FILTER - 图片路径
    page_number: int = 0               # 🔍 FILTER - 页码（高频过滤）
    chapter_id: Optional[str] = None   # 🔍 FILTER - 章节ID（高频过滤）
    caption: str = ""                  # 🔍 FILTER - 图片标题
    width: int = 0                     # 🔍 FILTER - 宽度
    height: int = 0                    # 🔍 FILTER - 高度
    size: int = 0                      # 🔍 FILTER - 文件大小
    aspect_ratio: float = 0.0          # 🔍 FILTER - 宽高比
    created_at: Optional[str] = None   # 🔍 FILTER - 创建时间
    
    # === 中间数据（开发调试用）===
    page_context: str = ""             # 🛠️ INTERMEDIATE - 页面上下文（用于生成描述）
    
    # === Embedding内容 ===
    search_summary: Optional[str] = None        # 📄 EMBEDDING - 简述（15字以内关键词）
    detailed_description: Optional[str] = None  # 📄 EMBEDDING - 详细描述
    engineering_details: Optional[str] = None   # 📄 EMBEDDING - 工程技术细节
    
    # === Embedding内容属性 ===
    @property 
    def content(self) -> str:          # 📄 EMBEDDING - 组合所有描述信息
        """组合search_summary + detailed_description + engineering_details + page_context"""
```

### TableChunk（表格块）
```python
@dataclass 
class TableChunk:
    # === 核心标识 ===
    content_id: str                    # 🔍 FILTER - 唯一标识
    document_id: str                   # 🔍 FILTER - 文档ID
    content_type: str = "table_chunk"  # 🔍 FILTER - 内容类型
    content_level: str = "chunk"       # 🔍 FILTER - 内容层级
    
    # === Filter元数据 ===
    table_path: str = ""               # 🔍 FILTER - 表格路径
    page_number: int = 0               # 🔍 FILTER - 页码（高频过滤）
    chapter_id: Optional[str] = None   # 🔍 FILTER - 章节ID（高频过滤）
    caption: str = ""                  # 🔍 FILTER - 表格标题
    width: int = 0                     # 🔍 FILTER - 宽度
    height: int = 0                    # 🔍 FILTER - 高度
    size: int = 0                      # 🔍 FILTER - 文件大小
    aspect_ratio: float = 0.0          # 🔍 FILTER - 宽高比
    created_at: Optional[str] = None   # 🔍 FILTER - 创建时间
    
    # === 中间数据（开发调试用）===
    page_context: str = ""             # 🛠️ INTERMEDIATE - 页面上下文（用于生成描述）
    
    # === Embedding内容 ===
    search_summary: Optional[str] = None        # 📄 EMBEDDING - 表格类型和关键信息
    detailed_description: Optional[str] = None  # 📄 EMBEDDING - 表格结构和内容
    engineering_details: Optional[str] = None   # 📄 EMBEDDING - 数据含义和技术解读
    
    # === Embedding内容属性 ===
    @property
    def content(self) -> str:          # 📄 EMBEDDING - 组合所有描述信息
        """组合search_summary + detailed_description + engineering_details + page_context"""
```

### TextChunk（文本块）
```python
@dataclass
class TextChunk:
    # === 核心标识 ===
    content_id: str                    # 🔍 FILTER - 唯一标识
    document_id: str                   # 🔍 FILTER - 文档ID
    content_type: str = "text_chunk"   # 🔍 FILTER - 内容类型
    content_level: str = "chunk"       # 🔍 FILTER - 内容层级
    
    # === Embedding内容 ===
    content: str = ""                  # 📄 EMBEDDING - 核心字段！实际文本内容
    
    # === Filter元数据 ===
    chapter_id: Optional[str] = ""     # 🔍 FILTER - 章节ID（高频过滤）
    chunk_index: int = 0               # 🔍 FILTER - 块索引
    word_count: int = 0                # 🔍 FILTER - 字数
    created_at: Optional[str] = None   # 🔍 FILTER - 创建时间
```

### ChapterSummary（章节摘要）
```python
@dataclass
class ChapterSummary:
    # === 核心标识 ===
    content_id: str                    # 🔍 FILTER - 唯一标识
    document_id: str                   # 🔍 FILTER - 文档ID
    content_type: str = "chapter_summary"  # 🔍 FILTER - 内容类型
    content_level: str = "chapter"     # 🔍 FILTER - 内容层级
    
    # === Filter元数据 ===
    chapter_id: str = ""               # 🔍 FILTER - 章节ID（高频过滤）
    chapter_title: str = ""            # 🔍 FILTER - 章节标题
    word_count: int = 0                # 🔍 FILTER - 字数
    created_at: Optional[str] = None   # 🔍 FILTER - 创建时间
    
    # === 中间数据（开发调试用）===
    raw_content: Optional[str] = None       # 🛠️ INTERMEDIATE - 章节原始文本（用于生成摘要）
    
    # === Embedding内容 ===
    ai_summary: Optional[str] = None        # 📄 EMBEDDING - AI生成的章节摘要
    
    # === Embedding内容属性 ===
    @property
    def content(self) -> str:          # 📄 EMBEDDING - 优先使用ai_summary，fallback到raw_content
        """返回要被embedding的内容"""
```

### DerivedQuestion（衍生问题）
```python
@dataclass
class DerivedQuestion:
    # === 核心标识 ===
    content_id: str                    # 🔍 FILTER - 唯一标识
    document_id: str                   # 🔍 FILTER - 文档ID
    content_type: str = "derived_question"  # 🔍 FILTER - 内容类型
    content_level: str = "document"    # 🔍 FILTER - 内容层级
    
    # === Embedding内容 ===
    content: str = ""                  # 📄 EMBEDDING - 问题文本本身
    
    # === Filter元数据 ===
    question_type: str = ""            # 🔍 FILTER - 问题类型
    confidence_score: Optional[float] = None  # 🔍 FILTER - 置信度
    created_at: Optional[str] = None   # 🔍 FILTER - 创建时间
    
    # === 中间数据（开发调试用）===
    source_context: Optional[str] = None      # 🛠️ INTERMEDIATE - 生成问题的源上下文
```

## 📊 数据用途分类总结

### 🛠️ **中间数据（INTERMEDIATE）**
**用途**：开发过程中的调试、错误恢复、质量追溯
**特点**：不直接用于检索，但对系统维护很重要

| 字段 | 位置 | 用途 |
|------|------|------|
| `full_raw_text` | DocumentSummary | 原始完整文本，用于恢复和再处理 |
| `page_texts` | DocumentSummary | 页面级原始文本，调试用 |
| `cleaned_page_texts` | DocumentSummary | 页面级清洗文本，质量对比 |
| `toc` | DocumentSummary | TOC结构数据，用于结构分析 |
| `metadata` | DocumentSummary | 其他处理元信息 |
| `page_context` | ImageChunk/TableChunk | 页面上下文，用于生成AI描述 |
| `raw_content` | ChapterSummary | 章节原始文本，用于生成摘要 |
| `source_context` | DerivedQuestion | 问题生成的源上下文 |

### 🛠️ **开发优化数据（DEV_STATS）**
**用途**：性能分析、存储管理、系统优化
**特点**：主要用于开发调优，不用于用户检索

| 字段 | 位置 | 用途 |
|------|------|------|
| `file_size` | DocumentSummary | 存储管理、性能分析 |
| `total_word_count` | DocumentSummary | 处理性能分析、复杂度评估 |
| `chapter_count` | DocumentSummary | 结构分析统计、复杂度评估 |
| `processing_time` | DocumentSummary | 性能优化、算法调优 |

### 📊 **统计数据（STATS）**
**用途**：系统统计为主，偶尔用于检索过滤
**特点**：介于中间数据和Filter数据之间

| 字段 | 位置 | 主要用途 | 偶尔检索场景 |
|------|------|----------|--------------|
| `total_pages` | DocumentSummary | 性能分析 | 找短文档/长文档 |
| `image_count` | DocumentSummary | 统计报告 | 找图片丰富的文档 |
| `table_count` | DocumentSummary | 统计报告 | 找数据表格丰富的文档 |

### 📄 **Embedding内容（EMBEDDING）**
**用途**：直接用于向量化和语义搜索的核心内容
**特点**：这些是用户实际搜索的对象

| 内容类型 | 主要embedding字段 | 内容来源 |
|----------|------------------|----------|
| **DocumentSummary** | `content` (property) | 优先`ai_summary`，fallback到`full_raw_text`前2000字符 |
| **TextChunk** | `content` | 直接是分块后的文本内容 |
| **ImageChunk** | `content` (property) | 组合`search_summary` + `detailed_description` + `engineering_details` |
| **TableChunk** | `content` (property) | 组合`search_summary` + `detailed_description` + `engineering_details` |
| **ChapterSummary** | `content` (property) | 优先`ai_summary`，fallback到`raw_content` |
| **DerivedQuestion** | `content` | 问题文本本身 |

### 🔍 **Filter元数据（FILTER）**
**用途**：语义搜索前的过滤、排序、分组
**特点**：提高检索精度，支持多维度筛选

#### 高频Filter字段（核心）
| 字段 | 类型 | 用途场景 |
|------|------|----------|
| **`content_type`** | 所有类型 | 内容类型过滤（只搜图片/只搜文本等）|
| **`document_id`** | 所有类型 | 文档范围限制 |
| **`chapter_id`** | Chunk类型 | 章节范围限制（高频使用）|
| **`page_number`** | Image/Table | 页面范围过滤 |
| **`content_level`** | 所有类型 | 内容层级过滤（文档级/章节级/块级）|

#### 项目隔离Filter字段（从V1继承）
| 字段 | 用途 |
|------|------|
| **`document_scope`** | "project" vs "general" 项目隔离 |
| **`project_name`** | 具体项目名称（当scope=project时）|

#### 媒体属性Filter字段
| 字段 | 适用类型 | 用途 |
|------|----------|------|
| `aspect_ratio` | Image/Table | 图片形状过滤（横版/竖版）|
| `width/height` | Image/Table | 尺寸过滤 |
| `caption` | Image/Table | 标题关键词过滤 |
| `word_count` | Chapter/Text | 内容长度过滤 |
| `created_at` | 所有类型 | 时间范围过滤 |

## 🔧 实际使用模式

### 1. **小块检索，大块喂养**
```python
# Step 1: 小块检索 - 使用embedding内容
vector_results = chroma_collection.query(
    query_texts=["古建筑修缮设计"],
    n_results=10,
    where={
        "content_type": {"$in": ["text_chunk", "image_chunk"]},  # Filter
        "chapter_id": "2.1"  # Filter
    }
)

# Step 2: 大块喂养 - 获取完整章节上下文
for result in vector_results:
    chapter_id = result.metadata["chapter_id"]
    document_id = result.metadata["document_id"]
    
    # 获取该章节的所有内容
    full_context = get_chapter_context(document_id, chapter_id)
```

### 2. **多模态检索**
```python
# 文本 + 图片联合检索
results = chroma_collection.query(
    query_texts=["建筑结构设计图"],
    where={
        "content_type": {"$in": ["text_chunk", "image_chunk"]},  # Filter
        "document_scope": "project",  # Filter: 只搜项目资料
        "project_name": "古庙修缮项目"  # Filter: 特定项目
    }
)
```

### 3. **项目隔离检索**
```python
# 只检索特定项目的资料
project_results = chroma_collection.query(
    query_texts=["文物保护方案"],
    where={
        "document_scope": "project",      # Filter
        "project_name": "医灵古庙项目"    # Filter
    }
)

# 只检索通用行业资料
general_results = chroma_collection.query(
    query_texts=["文物保护法规"],
    where={
        "document_scope": "general"       # Filter
    }
)
```

## 📈 存储策略

### 向量数据库存储（Chroma/Pinecone）
**存储内容**：
- **Embedding vectors**（基于`content`属性）
- **高频Filter字段**：`content_type`, `document_id`, `chapter_id`, `page_number`, `content_level`, `document_scope`, `project_name`, `created_at`
- **媒体Filter字段**：`aspect_ratio`, `width`, `height`, `caption`（仅Image/Table类型）

### 关系数据库存储（PostgreSQL）
**存储内容**：
- **完整的metadata记录**（所有字段）
- **中间数据**：`full_raw_text`, `page_texts`, `cleaned_page_texts`, `toc`, `page_context`, `raw_content`, `source_context`
- **开发优化数据**：`file_size`, `total_word_count`, `chapter_count`, `processing_time`
- **统计数据**：`total_pages`, `image_count`, `table_count`
- **复杂的关联关系**

### 存储原则
1. **向量数据库**：只存储真正用于检索过滤的字段，保持高性能
2. **关系数据库**：存储完整数据，支持复杂查询和数据分析
3. **不重复存储**：embedding内容不在关系数据库中重复存储

### 缓存策略
**高频访问数据**：
- 章节标题映射（`chapter_id` → `chapter_title`）
- 文档基本信息（`document_id` → `document_title`, `file_name`）
- 项目名称映射
- 统计数据（用于dashboard显示）

## 🎯 设计优势

1. **职责明确**：每类数据有明确的用途和访问模式
2. **检索优化**：高频Filter字段放在向量数据库，提升检索速度
3. **成本控制**：中间数据不进入向量化，节省embedding成本
4. **调试友好**：保留完整的中间数据，便于问题排查
5. **扩展性强**：清晰的数据分类，便于未来扩展新的filter维度

## ⚠️ 注意事项

1. **Embedding内容质量**：优先使用AI生成的摘要和描述，fallback到原始内容
2. **Filter字段一致性**：确保向量数据库和关系数据库的filter字段同步
3. **数据分层存储**：
   - 向量数据库：只存储真正的高频filter字段，避免过度冗余
   - 关系数据库：存储完整数据，包括开发优化和统计数据
4. **中间数据管理**：定期清理过期的中间数据（`page_texts`, `toc`等），控制存储成本
5. **统计数据用途**：`total_pages`, `image_count`等主要用于系统分析，偶尔用于检索
6. **开发优化数据隔离**：`file_size`, `processing_time`等纯开发数据不进入向量数据库
7. **性能监控**：重点监控真正的高频filter字段使用情况，优化索引策略 