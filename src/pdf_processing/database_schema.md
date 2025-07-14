# PDF Processing 数据库表结构设计

## 概述

本文档描述了PDF Processing模块的数据库表结构设计，支持统一的元数据管理和高效的向量检索。

## 数据库架构

### 1. 向量数据库 (Chroma/Pinecone)
- **用途**: 存储embedding向量和基础元数据
- **存储内容**: 文档摘要、章节摘要、文本块、图片描述、表格描述、衍生问题

### 2. 关系数据库 (PostgreSQL)
- **用途**: 存储结构化元数据和关联关系
- **存储内容**: 完整的元数据信息、文件路径、关联关系

## 关系数据库表结构

### 1. documents 表 (文档基础信息)
```sql
CREATE TABLE documents (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(1000) NOT NULL,
    summary TEXT,
    total_pages INTEGER,
    file_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_version VARCHAR(50)
);
```

### 2. chapters 表 (章节信息)
```sql
CREATE TABLE chapters (
    id VARCHAR(255) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chapter_id VARCHAR(100) NOT NULL,  -- "1", "2.1", "3.2.1"
    title VARCHAR(1000) NOT NULL,
    level INTEGER NOT NULL,
    content TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (document_id) REFERENCES documents(id),
    INDEX idx_doc_chapter (document_id, chapter_id),
    INDEX idx_level (level)
);
```

### 3. content_metadata 表 (统一内容元数据)
```sql
CREATE TABLE content_metadata (
    content_id VARCHAR(255) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chapter_id VARCHAR(100),
    
    -- 内容类型和层级
    content_type ENUM('document_summary', 'chapter_summary', 'text_chunk', 'image_chunk', 'table_chunk', 'derived_question') NOT NULL,
    content_level ENUM('document', 'chapter', 'chunk', 'question') NOT NULL,
    
    -- 内容信息
    content TEXT NOT NULL,
    content_summary TEXT,
    
    -- 位置信息
    page_number INTEGER,
    position_in_page INTEGER,
    position_in_chapter INTEGER,
    
    -- 文件信息 (仅用于图片/表格)
    file_path VARCHAR(500),
    file_size BIGINT,
    file_format VARCHAR(20),
    image_dimensions VARCHAR(50),
    
    -- 质量信息
    extraction_confidence DECIMAL(3,2),
    ai_description_confidence DECIMAL(3,2),
    content_quality_score DECIMAL(3,2),
    
    -- 检索优化
    keywords JSON,
    tags JSON,
    language VARCHAR(10),
    
    -- 系统信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    extra_metadata JSON,
    
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id),
    
    INDEX idx_doc_type (document_id, content_type),
    INDEX idx_chapter_type (chapter_id, content_type),
    INDEX idx_content_level (content_level),
    INDEX idx_page (page_number),
    INDEX idx_file_path (file_path)
);
```

### 4. content_relationships 表 (内容关联关系)
```sql
CREATE TABLE content_relationships (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_content_id VARCHAR(255) NOT NULL,
    target_content_id VARCHAR(255) NOT NULL,
    relationship_type ENUM('related_image', 'related_table', 'related_chunk', 'derived_question') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (source_content_id) REFERENCES content_metadata(content_id),
    FOREIGN KEY (target_content_id) REFERENCES content_metadata(content_id),
    
    UNIQUE KEY unique_relationship (source_content_id, target_content_id, relationship_type),
    INDEX idx_source (source_content_id),
    INDEX idx_target (target_content_id),
    INDEX idx_relationship_type (relationship_type)
);
```

## 向量数据库集合结构

### Chroma集合配置
```python
# 向量数据库集合配置
CHROMA_COLLECTION_CONFIG = {
    "name": "gauz_document_embeddings",
    "metadata": {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,
        "hnsw:M": 16
    },
    "embedding_function": "text-embedding-3-large"  # 或其他embedding模型
}

# 存储在向量数据库中的元数据字段
VECTOR_DB_METADATA_FIELDS = [
    "content_id",
    "document_id", 
    "chapter_id",
    "content_type",
    "content_level",
    "page_number",
    "chapter_title",
    "document_title",
    "file_path",  # 仅用于图片/表格
    "file_format",  # 仅用于图片/表格
    "keywords",
    "tags"
]
```

### 向量数据库存储示例
```python
# 存储到向量数据库的数据格式
vector_db_record = {
    "ids": ["text_chunk_alphaevolve_2024_chunk_001"],
    "embeddings": [embedding_vector],  # 1536维向量
    "metadatas": [{
        "content_id": "text_chunk_alphaevolve_2024_chunk_001",
        "document_id": "alphaevolve_2024",
        "chapter_id": "2.1",
        "content_type": "text_chunk",
        "content_level": "chunk",
        "page_number": 5,
        "chapter_title": "Task specification",
        "document_title": "AlphaEvolve: A coding agent for scientific discovery",
        "keywords": ["AlphaEvolve", "代码生成", "科学发现"],
        "tags": ["技术", "AI", "算法"]
    }],
    "documents": ["AlphaEvolve通过生成代码来解决科学问题..."]
}
```

## 查询模式

### 1. 精确检索查询 (小块检索)
```python
def search_precise_chunks(query: str, filters: Dict = None) -> List[Dict]:
    """精确检索相关的chunks"""
    # 向量检索
    vector_results = chroma_collection.query(
        query_texts=[query],
        n_results=10,
        where=filters or {},
        include=["metadatas", "documents", "distances"]
    )
    
    # 从关系数据库获取完整元数据
    chunk_ids = [result["content_id"] for result in vector_results["metadatas"]]
    complete_metadata = db.query(
        "SELECT * FROM content_metadata WHERE content_id IN %s",
        (chunk_ids,)
    )
    
    return complete_metadata
```

### 2. 上下文检索查询 (大块喂养)
```python
def get_chapter_context(chapter_id: str, document_id: str) -> Dict:
    """获取章节完整上下文"""
    # 获取章节基本信息
    chapter_info = db.query(
        "SELECT * FROM chapters WHERE chapter_id = %s AND document_id = %s",
        (chapter_id, document_id)
    )
    
    # 获取章节内所有内容
    chapter_contents = db.query(
        """
        SELECT * FROM content_metadata 
        WHERE chapter_id = %s AND document_id = %s
        ORDER BY position_in_chapter
        """,
        (chapter_id, document_id)
    )
    
    return {
        "chapter_info": chapter_info,
        "contents": chapter_contents
    }
```

### 3. 混合检索查询
```python
def hybrid_search(
    query: str,
    document_ids: List[str] = None,
    content_types: List[str] = None,
    top_k: int = 5
) -> Dict:
    """混合检索：向量 + 元数据过滤"""
    
    # 构建过滤条件
    filters = {}
    if document_ids:
        filters["document_id"] = {"$in": document_ids}
    if content_types:
        filters["content_type"] = {"$in": content_types}
    
    # 向量检索
    vector_results = chroma_collection.query(
        query_texts=[query],
        n_results=top_k * 2,  # 获取更多结果用于重排序
        where=filters,
        include=["metadatas", "documents", "distances"]
    )
    
    # 重排序和后处理
    reranked_results = rerank_results(vector_results, query)
    
    return {
        "results": reranked_results[:top_k],
        "total_found": len(vector_results["ids"]),
        "query": query
    }
```

## 索引策略

### 1. 关系数据库索引
```sql
-- 基础索引
CREATE INDEX idx_content_doc_type ON content_metadata(document_id, content_type);
CREATE INDEX idx_content_chapter_type ON content_metadata(chapter_id, content_type);
CREATE INDEX idx_content_level ON content_metadata(content_level);
CREATE INDEX idx_page_number ON content_metadata(page_number);

-- 复合索引
CREATE INDEX idx_doc_chapter_page ON content_metadata(document_id, chapter_id, page_number);
CREATE INDEX idx_type_level_page ON content_metadata(content_type, content_level, page_number);

-- 文本搜索索引
CREATE FULLTEXT INDEX idx_content_fulltext ON content_metadata(content, content_summary);
```

### 2. 向量数据库索引
```python
# Chroma向量索引配置
VECTOR_INDEX_CONFIG = {
    "hnsw:space": "cosine",        # 余弦相似度
    "hnsw:construction_ef": 200,   # 构建时的ef参数
    "hnsw:M": 16,                  # 每个节点的最大连接数
    "hnsw:ef_search": 100          # 搜索时的ef参数
}
```

## 性能优化

### 1. 批量操作
```python
def batch_insert_metadata(metadata_list: List[UnifiedMetadata], batch_size: int = 1000):
    """批量插入元数据"""
    for i in range(0, len(metadata_list), batch_size):
        batch = metadata_list[i:i + batch_size]
        
        # 准备向量数据库数据
        vector_data = prepare_vector_data(batch)
        chroma_collection.add(**vector_data)
        
        # 准备关系数据库数据
        relational_data = prepare_relational_data(batch)
        db.bulk_insert("content_metadata", relational_data)
```

### 2. 缓存策略
```python
# Redis缓存配置
CACHE_CONFIG = {
    "chapter_context": {"ttl": 3600},      # 章节上下文缓存1小时
    "search_results": {"ttl": 1800},       # 搜索结果缓存30分钟
    "metadata": {"ttl": 7200}              # 元数据缓存2小时
}
```

### 3. 分区策略
```sql
-- 按文档ID分区
CREATE TABLE content_metadata_partitioned (
    -- 所有字段同上
) PARTITION BY HASH(document_id) PARTITIONS 8;
```

## 数据一致性

### 1. 事务管理
```python
def create_document_with_content(document_data: Dict, content_list: List[UnifiedMetadata]):
    """事务性创建文档和内容"""
    with db.transaction():
        # 创建文档记录
        db.insert("documents", document_data)
        
        # 创建章节记录
        chapters = extract_chapters(content_list)
        db.bulk_insert("chapters", chapters)
        
        # 创建内容元数据
        metadata_records = [m.to_dict() for m in content_list]
        db.bulk_insert("content_metadata", metadata_records)
        
        # 创建关联关系
        relationships = extract_relationships(content_list)
        db.bulk_insert("content_relationships", relationships)
        
        # 同步到向量数据库
        sync_to_vector_db(content_list)
```

### 2. 数据同步
```python
def sync_metadata_to_vector_db(content_id: str):
    """同步元数据到向量数据库"""
    # 从关系数据库获取最新数据
    metadata = db.query(
        "SELECT * FROM content_metadata WHERE content_id = %s",
        (content_id,)
    )
    
    # 更新向量数据库
    chroma_collection.update(
        ids=[content_id],
        metadatas=[prepare_vector_metadata(metadata)]
    )
```

## 监控和维护

### 1. 数据质量监控
```python
QUALITY_METRICS = {
    "embedding_coverage": "COUNT(*) FROM content_metadata WHERE content_id NOT IN (SELECT id FROM vector_db)",
    "broken_file_paths": "COUNT(*) FROM content_metadata WHERE file_path IS NOT NULL AND file_path NOT LIKE '%parser_output%'",
    "missing_relationships": "COUNT(*) FROM content_metadata cm1 WHERE content_type='text_chunk' AND NOT EXISTS (SELECT 1 FROM content_relationships cr WHERE cr.source_content_id = cm1.content_id)"
}
```

### 2. 性能监控
```python
PERFORMANCE_METRICS = {
    "avg_search_time": "向量检索平均响应时间",
    "cache_hit_rate": "缓存命中率",
    "index_usage": "索引使用率",
    "storage_growth": "存储增长率"
}
```

这个数据库设计支持高效的向量检索、灵活的元数据过滤、完整的关联关系管理，以及良好的扩展性和维护性。 