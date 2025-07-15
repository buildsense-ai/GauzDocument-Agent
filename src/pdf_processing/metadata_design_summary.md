# PDF元数据设计方案（精简版）

## 设计原则

1. **避免重复**：删除冗余字段，单一数据源
2. **关注核心**：聚焦于实际业务需求，删除不必要的字段
3. **分离关注点**：独立的类型管理和TOC管理
4. **简化维护**：减少不必要的复杂性
5. **实用优先**：只保留当前确实需要的字段

## 通用元数据字段

所有embedding内容都包含这些字段：

```python
UNIVERSAL_METADATA_FIELDS = {
    "content_id": str,           # 唯一标识  
    "document_id": str,          # 文档ID
    "content_type": str,         # 内容类型
    "content_level": str,        # "document"|"chapter"|"chunk"|"question"
    
    # === 层级关系（高频使用）===
    "chapter_id": str,           # "1"|"2"|"3" (仅一级章节)
    "document_title": str,       # 文档标题
    "chapter_title": str,        # 章节标题
    
    # === 项目分类 ===
    "document_scope": str,       # "project"|"general"
    "project_name": str,         # 项目名称（scope=project时）
    
    # === 处理信息 ===
    "created_at": datetime,      # 创建时间
}
```

## 独立管理表

### 1. 文档类型管理表

```python
@dataclass
class DocumentType:
    type_id: str                       # 类型ID
    type_name: str                     # 类型名称  
    category: str                      # 大类别（工程资料/法规文件/标准规范等）
    description: str                   # 描述
    typical_structure: List[str]       # 典型结构（章节模式）
    created_at: datetime              # 创建时间
```

**用途**：统一管理文档类型，其他表通过`document_type_id`关联

### 2. TOC存储表（简化版）

```python
@dataclass
class DocumentTOC:
    """文档TOC存储"""
    document_id: str                    # 文档ID
    toc_json: str                       # TOC的JSON字符串
    chapter_count: int                  # 一级章节数量
    total_sections: int                 # 总章节数量
    created_at: datetime               # 创建时间
```

**用途**：简化TOC存储，避免复杂的表结构，TOC的ID本身就是按顺序生成的

**TOC JSON格式示例**：
```json
{
  "toc": [
    {"title": "项目概况", "level": 1, "id": "1", "parent_id": null},
    {"title": "项目背景", "level": 2, "id": "2", "parent_id": "1"},
    {"title": "技术方案", "level": 1, "id": "3", "parent_id": null}
  ]
}
```

## 具体内容类型元数据

### 1. 图片chunk元数据

```python
@dataclass
class ImageChunkMetadata:
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: Optional[str]          # 所属章节ID（可能在章节外）
    
    # === 文件信息 ===
    image_path: str                    # 图片路径
    page_number: int                   # 页码
    caption: str                       # 图片标题
    
    # === 尺寸信息 ===
    width: int                         # 宽度
    height: int                        # 高度
    size: int                          # 文件大小
    aspect_ratio: float                # 宽高比
    
    # === 内容信息 ===
    ai_description: str                # AI生成的描述
    page_context: str                  # 页面上下文（包含前后文本）
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间
```

### 2. 表格chunk元数据

```python
@dataclass
class TableChunkMetadata:
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: Optional[str]          # 所属章节ID（可能在章节外）
    
    # === 文件信息 ===
    table_path: str                    # 表格图片路径
    page_number: int                   # 页码
    caption: str                       # 表格标题
    
    # === 尺寸信息 ===
    width: int                         # 宽度
    height: int                        # 高度
    size: int                          # 文件大小
    aspect_ratio: float                # 宽高比
    
    # === 内容信息 ===
    ai_description: str                # AI生成的描述
    page_context: str                  # 页面上下文（包含前后文本）
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间
```

### 3. 文本chunk元数据

```python
@dataclass
class TextChunkMetadata:
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: str                    # 所属章节ID
    
    # === 内容信息 ===
    chunk_type: str                    # "title"|"paragraph"|"list_item"
    word_count: int                    # 字数
    
    # === 位置信息 ===
    position_in_chapter: int           # 在章节中的位置顺序
    
    # === 段落信息 ===
    paragraph_index: int               # 段落索引（如果是段落）
    is_first_paragraph: bool           # 是否是章节首段
    is_last_paragraph: bool            # 是否是章节末段
    
    # === 上下文信息 ===
    preceding_chunk_id: Optional[str]  # 前一个chunk的ID
    following_chunk_id: Optional[str]  # 后一个chunk的ID
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间
```

**删除的字段及原因**：
- `language`/`has_formulas`/`has_code`/`has_citations`: 当前业务不需要这些特征检测

### 4. 章节摘要元数据

```python
@dataclass
class ChapterSummaryMetadata:
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: str                    # 章节ID（同时作为顺序标识）
    toc_id: str                        # 关联的TOC条目ID
    
    # === 章节顺序 ===
    chapter_order: int                 # 章节顺序（1,2,3...）
    
    # === 内容统计 ===
    word_count: int                    # 字数
    paragraph_count: int               # 段落数
    text_chunk_count: int              # 文本块数量
    image_count: int                   # 图片数量
    table_count: int                   # 表格数量
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间
```

**删除的字段及原因**：
- `page_start`/`page_end`: 页面信息用处不大
- `main_topics`/`has_formulas`/`has_code`/`has_citations`: 当前不需要这些AI分析功能

### 5. 文档摘要元数据

```python
@dataclass
class DocumentSummaryMetadata:
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 文档ID
    document_type_id: str              # 文档类型ID（关联DocumentType表）
    
    # === 文档信息 ===
    source_file_path: str              # 源文件路径
    file_name: str                     # 文件名
    file_size: int                     # 文件大小
    
    # === 内容统计 ===
    total_pages: int                   # 总页数
    total_word_count: int              # 总字数
    chapter_count: int                 # 章节数
    image_count: int                   # 图片总数
    table_count: int                   # 表格总数
    
    # === 处理信息 ===
    processing_time: float             # 处理时间（秒）
    created_at: datetime               # 创建时间
    
    # === 关联信息 ===
    toc_root_id: str                   # 根TOC条目ID
```

**删除的字段及原因**：
- `main_topics`/`language`: 当前不需要这些AI分析功能

### 6. 派生问题元数据

```python
@dataclass
class DerivedQuestionMetadata:
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: str                    # 所属章节ID
    
    # === 问题信息 ===
    question_category: str             # 问题分类（基于章节内容）
    
    # === 生成信息 ===
    generated_from_chunk_id: str       # 基于哪个chunk生成的问题
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间
```

**删除的字段及原因**：
- `generation_method`: 都是AI生成的，没有区分必要

## 现有流程中的数据获取

### 1. PDF解析阶段（basic_processing_result.json）

可以直接获取：
- 图片/表格的文件信息：`image_path`, `page_number`, `caption`
- 尺寸信息：`width`, `height`, `size`, `aspect_ratio`
- 内容信息：`ai_description`, `page_context`

### 2. TOC提取阶段（toc_extractor.py）

可以直接获取：
- 章节结构：`level`, `title`, `id`, `parent_id`
- 层级关系：通过`parent_id`维护
- 章节顺序：通过ID的数字顺序（"1", "2", "3"...）

### 3. 文本分块阶段（ai_chunker.py）

可以直接获取：
- 位置信息：`position_in_chapter`
- 内容类型：`chunk_type`
- 统计信息：`word_count`

### 4. 需要新增的组件

- **document_summary_generator.py**：生成文档摘要
- **chapter_summary_generator.py**：生成章节摘要
- **question_generator.py**：生成派生问题（可选）

### 5. 需要轻微扩展的信息

- **章节关联**：在图片/表格处理时，根据页面位置确定所属章节
- **链接关系**：在文本分块时建立chunk间的前后关系
- **段落信息**：在ai_chunker中添加paragraph_index等信息

## 存储架构

### 向量数据库（高频查询）
存储`UNIVERSAL_METADATA_FIELDS`中的字段，用于：
- 项目隔离过滤
- 内容类型过滤
- 章节层级过滤

### 关系数据库（复杂查询）
存储具体的内容元数据，用于：
- 详细信息查询
- 复杂关联查询
- 统计分析

## 辅助函数

```python
def get_metadata_class(content_type: str):
    """根据内容类型获取对应的元数据类"""

def create_content_id(document_id: str, content_type: str, sequence: int) -> str:
    """创建内容ID"""

def filter_by_project(metadata_list: List[Any], project_name: str) -> List[Any]:
    """按项目过滤元数据"""
```

## 设计优势

1. **简化维护**：删除冗余和不必要字段，减少数据不一致
2. **关注核心**：聚焦于实际业务需求，避免过度设计
3. **扩展性**：通过独立的管理表支持未来扩展
4. **性能优化**：双层存储架构，高频查询走向量库，复杂查询走关系库
5. **实用优先**：只保留当前确实需要的字段，避免不必要的复杂性

## 问题生成的必要性讨论

**DerivedQuestionMetadata**的必要性需要进一步评估：
- **优势**：可以提供更丰富的检索入口，支持问答式查询
- **劣势**：增加系统复杂度，问题质量难以保证
- **建议**：可以作为后续扩展功能，当前重点关注核心的文本、图片、表格chunk 