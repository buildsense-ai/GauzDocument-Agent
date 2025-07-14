# 并行开发接口定义

## 1. PDF Processing 输出接口

### DocumentStructure (核心输出)
```python
@dataclass
class DocumentStructure:
    total_pages: int
    toc: List[ChapterInfo]
    
@dataclass 
class ChapterInfo:
    chapter_id: str          # "1", "2.1", "3.2.1" 
    level: int               # 1, 2, 3...
    title: str               # 章节标题
    content_summary: str     # 章节概要
    start_marker: str        # 用于定位的文本标记
```

### MinimalChunk (分块输出)
```python
@dataclass
class MinimalChunk:
    chunk_id: int
    content: str
    chunk_type: str          # paragraph, list_item, image_desc, table_desc
    belongs_to_chapter: str  # 所属章节ID
    chapter_title: str       # 所属章节标题
    chapter_level: int       # 所属章节层级
```

### EnrichedChunk (最终输出)
```python
@dataclass
class EnrichedChunk:
    # 基础信息
    chunk_id: int
    content: str
    chunk_type: str
    
    # 章节归属
    belongs_to_chapter: str
    chapter_title: str
    chapter_level: int
    chapter_summary: str
    
    # 媒体关联
    related_images: List[Dict]
    related_tables: List[Dict]
    
    # 检索优化
    hypothetical_questions: List[str]
```

## 2. RAG 系统接口

### KnowledgeSearchTool 输入
```python
@dataclass
class SearchRequest:
    queries: List[str]                    # 必需：查询文本列表
    document_ids: Optional[List[str]]     # 可选：文档ID限制
    search_mode: str = "text_and_media"   # 检索模式
    top_k: int = 5                        # 返回数量
    filters: Optional[Dict] = None        # 元数据过滤
```

### KnowledgeSearchTool 输出
```python
@dataclass
class SearchResult:
    chunks: List[EnrichedChunk]  # 检索到的分块
    metadata: Dict               # 检索元数据
    total_found: int            # 总匹配数
    query_analysis: Dict        # 查询分析结果
```

### RetrievalAgent 输出
```python
@dataclass
class RetrievalResult:
    user_query: str
    relevant_chunks: List[EnrichedChunk]  # 精确匹配的小块
    context_chapters: List[ChapterInfo]   # 相关章节信息
    organized_context: str                # 整理后的上下文
    confidence_score: float               # 检索置信度
```

## 3. 长文生成接口

### DocumentPlan (总监输出)
```python
@dataclass
class DocumentPlan:
    goal: str                    # 生成目标
    outline: List[SectionSpec]   # 详细大纲
    total_sections: int          # 总章节数
    estimated_length: int        # 预估长度
```

### SectionSpec (章节规格)
```python
@dataclass
class SectionSpec:
    section_id: str
    title: str
    description: str
    required_info: List[str]     # 需要的信息类型
    dependencies: List[str]      # 依赖的其他章节
    estimated_length: int        # 预估长度
```

### PerfectContext (经理输出)
```python
@dataclass
class PerfectContext:
    section_spec: SectionSpec
    relevant_chunks: List[EnrichedChunk]
    chapter_summaries: List[str]
    structured_info: Dict
    writing_instructions: str
```

## 4. Mock 数据格式

### Mock EnrichedChunk
```python
MOCK_CHUNKS = [
    EnrichedChunk(
        chunk_id=1,
        content="文物保护是一项综合性工程...",
        chunk_type="paragraph",
        belongs_to_chapter="1.1",
        chapter_title="文物保护概述",
        chapter_level=2,
        chapter_summary="介绍文物保护的基本概念和重要性",
        related_images=[],
        related_tables=[],
        hypothetical_questions=["什么是文物保护？"]
    ),
    # ... 更多模拟数据
]
```

### Mock SearchResult
```python
MOCK_SEARCH_RESULT = SearchResult(
    chunks=MOCK_CHUNKS[:3],
    metadata={"search_time": 0.1, "total_docs": 5},
    total_found=10,
    query_analysis={"intent": "factual", "complexity": "medium"}
)
```

## 5. 开发优先级

### 第一阶段：接口定义和Mock实现
- [ ] 定义所有数据结构
- [ ] 创建Mock数据
- [ ] 实现Mock RAG系统
- [ ] 验证接口设计

### 第二阶段：并行开发
- [ ] PDF Processing：基于接口开发TOC和Chunk
- [ ] RAG：基于Mock数据开发Agent逻辑
- [ ] 长文生成：基于Mock RAG开发三层架构

### 第三阶段：集成测试
- [ ] 真实数据替换Mock
- [ ] 端到端测试
- [ ] 性能优化 