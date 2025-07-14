# 第二周开发计划：并行开发阶段

## 开发者A：PDF Processing 真实实现

### 关键任务：解决TOC提取问题

#### 方案1：大模型识别 + 标注切割
```python
# src/pdf_processing/toc_extractor.py
class SmartTOCExtractor:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def extract_toc_with_markers(self, full_text: str) -> List[ChapterMarker]:
        """
        使用大模型识别章节结构，返回标注信息
        """
        prompt = f"""
        请分析以下文档的章节结构，识别所有章节标题。
        
        要求：
        1. 识别章节的完整标题
        2. 确定章节层级（1=主章节，2=子章节，3=小节）
        3. 提供章节开始处的标识文本（前15-30个字符）
        4. 提供简要的章节概述
        
        输出格式：JSON数组，每个元素包含：
        {{
            "chapter_id": "1", // 或 "2.1", "3.2.1"
            "title": "章节标题",
            "level": 1,
            "start_marker": "章节开始的标识文本",
            "content_summary": "章节概述"
        }}
        
        文档内容：
        {full_text[:10000]}...
        """
        
        response = self.llm.generate(prompt)
        markers = self._parse_markers(response)
        return self._validate_markers(markers, full_text)
    
    def _validate_markers(self, markers: List[Dict], full_text: str) -> List[ChapterMarker]:
        """验证标注的准确性"""
        validated_markers = []
        for marker in markers:
            # 在原文中查找标识文本
            if marker['start_marker'] in full_text:
                validated_markers.append(ChapterMarker(**marker))
            else:
                # 尝试模糊匹配
                fuzzy_match = self._find_fuzzy_match(marker['start_marker'], full_text)
                if fuzzy_match:
                    marker['start_marker'] = fuzzy_match
                    validated_markers.append(ChapterMarker(**marker))
        
        return validated_markers
```

#### 方案2：正则匹配切割
```python
class RegexChapterSplitter:
    def __init__(self):
        self.chapter_patterns = [
            r'^(\d+\.?\s+[A-Z][^\\n]+)$',  # "1. Introduction"
            r'^([A-Z][^\\n]{10,100})$',     # 全大写标题
            r'^(\d+\.\d+\.?\s+[A-Z][^\\n]+)$',  # "2.1 Methods"
        ]
    
    def split_by_markers(self, full_text: str, markers: List[ChapterMarker]) -> List[Chapter]:
        """基于标注信息进行精确切割"""
        chapters = []
        
        for i, marker in enumerate(markers):
            # 找到章节开始位置
            start_pos = full_text.find(marker.start_marker)
            if start_pos == -1:
                continue
                
            # 找到章节结束位置
            if i + 1 < len(markers):
                end_pos = full_text.find(markers[i + 1].start_marker)
                if end_pos == -1:
                    end_pos = len(full_text)
            else:
                end_pos = len(full_text)
            
            # 提取章节内容
            chapter_content = full_text[start_pos:end_pos].strip()
            
            chapters.append(Chapter(
                id=marker.chapter_id,
                title=marker.title,
                level=marker.level,
                content=chapter_content,
                content_summary=marker.content_summary,
                start_position=start_pos,
                end_position=end_pos
            ))
        
        return chapters
```

#### 方案3：章节级细分块
```python
class ChapterChunker:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def chunk_chapter(self, chapter: Chapter) -> List[MinimalChunk]:
        """对单个章节进行细分块"""
        if len(chapter.content) < 2000:
            # 短章节可以信任大模型
            return self._llm_chunk(chapter)
        else:
            # 长章节使用标注+正则方式
            return self._marker_chunk(chapter)
    
    def _llm_chunk(self, chapter: Chapter) -> List[MinimalChunk]:
        """使用大模型进行分块"""
        prompt = f"""
        请将以下章节内容分割为最小语义单元：
        
        要求：
        1. 每个段落作为一个chunk
        2. 每个列表项作为一个chunk  
        3. 图片描述作为一个chunk
        4. 表格描述作为一个chunk
        
        输出格式：JSON数组，每个元素包含：
        {{
            "content": "具体内容",
            "chunk_type": "paragraph|list_item|image_desc|table_desc"
        }}
        
        章节内容：
        {chapter.content}
        """
        
        response = self.llm.generate(prompt)
        chunks_data = self._parse_chunks(response)
        
        return [
            MinimalChunk(
                chunk_id=i,
                content=chunk_data['content'],
                chunk_type=chunk_data['chunk_type'],
                belongs_to_chapter=chapter.id,
                chapter_title=chapter.title,
                chapter_level=chapter.level
            )
            for i, chunk_data in enumerate(chunks_data)
        ]
```

### 第二周具体任务安排

#### 第1-2天：TOC提取器实现
- 实现SmartTOCExtractor
- 测试不同文档的TOC提取效果
- 优化识别准确率

#### 第3-4天：章节切割器实现
- 实现RegexChapterSplitter
- 验证切割的准确性
- 处理边界情况

#### 第5-6天：章节分块器实现
- 实现ChapterChunker
- 测试分块效果
- 优化分块策略

#### 第7天：集成测试
- 端到端测试整个流程
- 性能优化
- 与Mock系统对接验证

## 开发者B：RAG 真实实现

### 核心任务：Agentic RAG架构

#### 任务1：RetrievalAgent实现
```python
class RetrievalAgent:
    def __init__(self, knowledge_tool: KnowledgeSearchTool, llm_client):
        self.knowledge_tool = knowledge_tool
        self.llm = llm_client
    
    def retrieve(self, user_query: str) -> RetrievalResult:
        # 1. 理解用户意图
        intent = self._analyze_intent(user_query)
        
        # 2. 制定检索策略
        search_strategy = self._plan_search_strategy(intent)
        
        # 3. 执行多轮检索
        results = self._execute_search(search_strategy)
        
        # 4. 整理和重排序
        return self._organize_results(results, user_query)
    
    def _analyze_intent(self, query: str) -> QueryIntent:
        """分析用户查询意图"""
        prompt = f"""
        分析以下查询的意图：
        
        查询：{query}
        
        请判断：
        1. 查询类型：factual/procedural/analytical/comparative
        2. 信息需求：specific/general/comprehensive
        3. 预期答案长度：short/medium/long
        4. 所需信息类型：text/image/table/mixed
        
        输出JSON格式。
        """
        
        response = self.llm.generate(prompt)
        return QueryIntent.from_dict(json.loads(response))
    
    def _plan_search_strategy(self, intent: QueryIntent) -> SearchStrategy:
        """制定检索策略"""
        if intent.query_type == "factual":
            return SearchStrategy(
                queries=[intent.original_query],
                search_mode="text_only",
                top_k=3
            )
        elif intent.query_type == "comprehensive":
            # 生成多个角度的查询
            expanded_queries = self._expand_queries(intent.original_query)
            return SearchStrategy(
                queries=expanded_queries,
                search_mode="text_and_media",
                top_k=10
            )
        # ... 其他策略
```

#### 任务2：KnowledgeSearchTool实现
```python
class KnowledgeSearchTool:
    def __init__(self, vector_db, metadata_db):
        self.vector_db = vector_db
        self.metadata_db = metadata_db
    
    def search(self, request: SearchRequest) -> SearchResult:
        """执行检索"""
        # 1. 向量检索
        vector_results = self._vector_search(request.queries, request.top_k)
        
        # 2. 元数据过滤
        if request.filters:
            vector_results = self._apply_filters(vector_results, request.filters)
        
        # 3. 重排序
        reranked_results = self._rerank_results(vector_results, request.queries)
        
        # 4. 构建结果
        return SearchResult(
            chunks=reranked_results,
            metadata=self._build_metadata(vector_results),
            total_found=len(vector_results)
        )
    
    def _vector_search(self, queries: List[str], top_k: int) -> List[EnrichedChunk]:
        """向量相似度检索"""
        all_results = []
        for query in queries:
            query_embedding = self._embed_query(query)
            similar_chunks = self.vector_db.similarity_search(
                query_embedding, 
                top_k=top_k
            )
            all_results.extend(similar_chunks)
        
        # 去重和合并
        return self._deduplicate_results(all_results)
```

### 第二周任务安排

#### 第1-2天：向量数据库集成
- 集成Chroma/Pinecone
- 实现embedding和检索逻辑
- 测试检索性能

#### 第3-4天：RetrievalAgent实现
- 实现意图分析
- 实现检索策略规划
- 测试不同查询类型

#### 第5-6天：KnowledgeSearchTool实现
- 实现多模态检索
- 实现元数据过滤
- 优化检索精度

#### 第7天：集成测试
- 端到端RAG测试
- 性能优化
- 与Mock系统对接

## 开发者C：长文生成真实实现

### 核心任务：三层架构实现

#### 任务1：总监Agent实现
```python
class OrchestratorAgent:
    def __init__(self, rag_agent: RetrievalAgent, llm_client):
        self.rag = rag_agent
        self.llm = llm_client
    
    def plan_document(self, goal: str, source_docs: List[str]) -> DocumentPlan:
        """生成文档大纲"""
        # 1. 分析目标文档需求
        doc_requirements = self._analyze_requirements(goal)
        
        # 2. 获取源文档结构
        source_structure = self._get_source_structure(source_docs)
        
        # 3. 生成详细大纲
        outline = self._generate_outline(doc_requirements, source_structure)
        
        # 4. 任务分解
        sections = self._decompose_sections(outline)
        
        return DocumentPlan(
            goal=goal,
            outline=sections,
            total_sections=len(sections),
            estimated_length=sum(s.estimated_length for s in sections)
        )
    
    def _generate_outline(self, requirements: Dict, structure: Dict) -> List[Dict]:
        """生成详细大纲"""
        prompt = f"""
        请根据以下要求生成详细的文档大纲：
        
        目标：{requirements['goal']}
        类型：{requirements['doc_type']}
        长度：{requirements['target_length']}
        
        源文档结构：
        {json.dumps(structure, indent=2)}
        
        请生成包含以下信息的大纲：
        1. 章节标题和描述
        2. 每个章节需要的信息类型
        3. 章节间的依赖关系
        4. 预估字数
        
        输出JSON格式。
        """
        
        response = self.llm.generate(prompt)
        return json.loads(response)
```

#### 任务2：经理Agent实现
```python
class SectionWriterAgent:
    def __init__(self, rag_agent: RetrievalAgent, llm_client):
        self.rag = rag_agent
        self.llm = llm_client
    
    def write_section(self, section_spec: SectionSpec) -> PerfectContext:
        """为特定章节收集完美上下文"""
        # 1. 分析章节需求
        info_needs = self._analyze_section_needs(section_spec)
        
        # 2. 制定信息收集计划
        collection_plan = self._plan_information_collection(info_needs)
        
        # 3. 执行多轮检索
        collected_info = self._collect_information(collection_plan)
        
        # 4. 整理上下文
        perfect_context = self._organize_context(collected_info, section_spec)
        
        return perfect_context
    
    def _collect_information(self, plan: CollectionPlan) -> CollectedInfo:
        """执行信息收集"""
        collected = CollectedInfo()
        
        for query_group in plan.query_groups:
            for query in query_group.queries:
                # 使用RAG检索相关信息
                result = self.rag.retrieve(query)
                
                # 按类型分类收集的信息
                if query_group.info_type == "factual":
                    collected.factual_info.extend(result.relevant_chunks)
                elif query_group.info_type == "procedural":
                    collected.procedural_info.extend(result.relevant_chunks)
                # ... 其他类型
        
        return collected
```

### 第二周任务安排

#### 第1-2天：总监Agent实现
- 实现需求分析
- 实现大纲生成
- 测试不同类型文档的规划

#### 第3-4天：经理Agent实现
- 实现信息收集策略
- 实现多轮RAG调用
- 测试上下文质量

#### 第5-6天：员工Agent实现
- 实现纯粹的内容生成
- 优化生成质量
- 测试不同写作风格

#### 第7天：集成测试
- 端到端长文生成测试
- 质量评估
- 性能优化

## 开发者D：集成和测试

### 第二周任务：真实系统集成

#### 第1-7天：持续集成测试
- 每日集成测试
- 接口兼容性验证
- 性能监控和优化
- 问题追踪和修复

#### 关键测试场景
1. PDF处理 → RAG数据库构建
2. RAG检索 → 长文生成
3. 端到端文档处理流程
4. 错误处理和恢复
5. 性能基准测试

## 第二周交付物

### 三大模块真实实现
- ✅ PDF Processing：智能TOC提取和分块
- ✅ RAG System：Agentic检索架构
- ✅ Long Document：三层生成架构

### 集成验证
- ✅ 模块间接口验证
- ✅ 数据流完整性验证
- ✅ 性能指标达标

### 为第三周优化做准备
- ✅ 识别性能瓶颈
- ✅ 确定优化方向
- ✅ 准备生产环境测试 