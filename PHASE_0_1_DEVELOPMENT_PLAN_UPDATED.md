# 📋 Phase 0 & Phase 1 更新开发计划

> **项目**: PDF处理V3重构 | **阶段**: Phase 0-1 | **状态**: 基于反馈更新  
> **更新时间**: 2025-01-25 | **预计完成时间**: 5-7个工作日

---

## 🎯 总体目标调整

1. **Phase 0**: 完成团队对齐，创建新的V3 Schema定义
2. **Phase 1**: 集成Mineru外部服务，实现Step A数据流
3. **关键调整**: 本地JSON存储，基于Mineru原始坐标，保留V2作为备选方案

---

## ❓ 用户反馈解答

### 项目隔离策略说明
"项目隔离的粒度是否合适？需要支持跨项目检索吗？" - 这里说的"三个不同"是指：

1. **`rtr_project_id`** - 硬隔离，每个项目的数据完全独立，默认检索只在项目内
2. **`rtr_document_id`** - 文档级隔离，一个项目内可能有多个文档
3. **`rtr_chapter_id`** - 章节级关联，用于同章节内容的关联检索加权

**具体场景**：
- 项目A的PDF文档 → `project_id=projA`, `document_id=doc1`
- 项目B的PDF文档 → `project_id=projB`, `document_id=doc2`  
- 检索时默认只在相同`project_id`内查找，除非明确指定跨项目检索

### 坐标系统调整策略
基于你的反馈，我们将：
1. **暂时移除页码依赖** - 等待Mineru实际数据格式
2. **使用Mineru原始坐标** - 可能是chunk_id或其他标识符
3. **保持灵活性** - 支持后续根据Mineru输出调整

---

## 📊 Phase 0: Schema V3设计（更新版）

### 0.1 Schema V3 设计确认（1天）

#### 核心调整
```python
@dataclass 
class DocumentSummaryV3:
    # 核心字段
    content_id: str
    rtr_document_id: str
    rtr_project_id: str                    # 新增项目隔离
    rtr_content_type: str = "document_summary"
    
    # 向量化字段
    emb_summary: Optional[str] = None
    
    # 检索字段  
    rtr_source_path: str = ""
    rtr_file_name: str = ""
    
    # 过程数据字段（本地JSON存储）
    prc_full_raw_text: Optional[str] = None      # 调整：直接存储文本而非URL
    prc_mineru_raw_output: Optional[Dict] = None # 新增：Mineru原始输出
    prc_page_texts: Optional[Dict] = None        # 保留用于调试
    
    # 统计字段
    ana_total_pages: int = 0
    ana_word_count: Optional[int] = None
    ana_image_count: int = 0
    ana_table_count: int = 0
    
    # 系统字段
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sys_schema_version: str = "3.0.0"
    sys_mineru_task_id: Optional[str] = None     # 新增：Mineru任务ID


@dataclass
class ImageChunkV3:
    # 核心字段
    content_id: str
    rtr_document_id: str
    rtr_project_id: str                    # 新增项目隔离
    rtr_content_type: str = "image_chunk"
    
    # 检索字段
    rtr_media_path: str = ""               # 图片存储路径
    rtr_caption: str = ""                  # 简短标题
    
    # 坐标字段（基于Mineru）
    rtr_mineru_chunk_id: Optional[str] = None    # 新增：Mineru原始坐标
    rtr_chapter_id: Optional[str] = None         # 章节关联（待Mineru数据确定）
    rtr_sequence_index: Optional[int] = None     # 在文档中的顺序
    
    # 过程数据
    prc_mineru_metadata: Optional[Dict] = None   # Mineru原始元数据
    
    # 向量化字段（AI生成）
    emb_search_summary: Optional[str] = None
    emb_detail_desc: Optional[str] = None
    emb_engineering_desc: Optional[str] = None
    
    # 统计字段
    ana_width: int = 0
    ana_height: int = 0
    ana_file_size: int = 0
    ana_aspect_ratio: float = 0.0
    
    # 系统字段
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TextChunkV3:
    # 核心字段
    content_id: str
    rtr_document_id: str
    rtr_project_id: str                    # 新增项目隔离
    rtr_content_type: str = "text_chunk"
    
    # 向量化字段
    emb_content: str = ""                  # 主要向量化内容
    
    # 坐标字段（基于Mineru）
    rtr_mineru_chunk_id: Optional[str] = None    # Mineru原始chunk标识
    rtr_chapter_id: Optional[str] = None         # 章节关联
    rtr_sequence_index: Optional[int] = None     # 在章节中的顺序
    
    # 统计字段
    ana_word_count: int = 0
    
    # 系统字段
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())
```

#### 存储策略调整
```python
# 所有数据本地JSON存储，目录结构：
project_data/
├── {project_id}/
│   ├── {document_id}/
│   │   ├── v3_final_metadata.json      # 最终Schema
│   │   ├── mineru_raw_output.json      # Mineru原始输出
│   │   ├── process_data.json           # 过程数据
│   │   └── media/                      # 图片、表格文件
│   │       ├── images/
│   │       └── tables/
│   └── project_metadata.json          # 项目级元数据
```

---

## 🔌 Phase 1: Mineru服务集成（更新版）

### 1.1 Mineru API研究与封装（2天）

#### API研究重点
基于提供的信息：
- **API地址**: https://mineru.net/apiManage
- **文件限制**: 最大200MB，600页
- **配额限制**: 每日2000页高优先级，超出后降级处理
- **认证**: Access Key + Secret Key

#### MineruClient设计
```python
class MineruClient:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = "kvzbwqj2zw9ovz2q20rl"
        self.secret_key = "yqyb14wpqezo79jaxebo7q5per2nrkdm3pegoj5n"
        self.base_url = "https://api.mineru.net"  # 需要验证实际地址
        self.daily_quota_used = 0
        self.priority_quota_remaining = 2000
    
    async def upload_pdf(self, file_path: str, project_id: str) -> str:
        """上传PDF，返回任务ID"""
        # 检查文件大小和页数限制
        # 上传并返回task_id
        
    async def get_processing_status(self, task_id: str) -> Dict:
        """查询处理状态"""
        # 轮询任务状态
        
    async def get_result(self, task_id: str) -> Dict:
        """获取完整处理结果"""
        # 获取Mineru的完整JSON输出
        
    def parse_mineru_output(self, raw_output: Dict, project_id: str) -> FinalMetadataSchemaV3:
        """解析Mineru输出，填充V3 Schema"""
        # 关键：保留所有Mineru原始坐标信息
        # 基于实际数据格式调整解析逻辑
```

#### 降级处理机制
```python
class ProcessingManager:
    def __init__(self):
        self.mineru_client = MineruClient()
        self.fallback_processor = V2Processor()  # 保留V2作为备选
    
    async def process_pdf(self, file_path: str, project_id: str) -> FinalMetadataSchemaV3:
        try:
            # 优先使用Mineru
            if self.check_mineru_available(file_path):
                return await self.process_with_mineru(file_path, project_id)
            else:
                # 降级到V2处理
                return await self.process_with_v2(file_path, project_id)
        except Exception as e:
            logger.warning(f"Mineru处理失败，降级到V2: {e}")
            return await self.process_with_v2(file_path, project_id)
```

### 1.2 Step A数据流实现（2天）

#### 核心处理流程
```python
async def process_pdf_step_a(pdf_path: str, project_id: str) -> FinalMetadataSchemaV3:
    """
    Step A: Mineru外部服务处理
    
    输入: PDF文件路径, 项目ID
    输出: 填充基础数据的V3 Schema
    """
    
    # 1. 文件预检查
    file_info = validate_pdf_file(pdf_path)
    if not file_info.is_valid:
        raise ValueError(f"PDF文件无效: {file_info.error}")
    
    # 2. 上传到Mineru
    task_id = await mineru_client.upload_pdf(pdf_path, project_id)
    
    # 3. 轮询处理状态
    max_wait_time = 300  # 5分钟超时
    start_time = time.time()
    
    while (time.time() - start_time) < max_wait_time:
        status = await mineru_client.get_processing_status(task_id)
        if status['state'] == 'completed':
            break
        elif status['state'] == 'failed':
            raise Exception(f"Mineru处理失败: {status.get('error', 'Unknown error')}")
        await asyncio.sleep(10)  # 10秒轮询间隔
    
    # 4. 获取结果
    raw_output = await mineru_client.get_result(task_id)
    
    # 5. 解析并填充V3 Schema
    schema = mineru_client.parse_mineru_output(raw_output, project_id)
    
    # 6. 保存数据到本地JSON
    save_path = get_project_data_path(project_id, schema.document_summary.rtr_document_id)
    await save_schema_to_json(schema, save_path)
    await save_raw_output(raw_output, save_path)
    
    return schema
```

#### 数据解析策略（待Mineru实际格式确定）
```python
def parse_mineru_output(raw_output: Dict, project_id: str) -> FinalMetadataSchemaV3:
    """
    基于Mineru实际返回格式进行解析
    
    预期格式（需要验证）:
    {
        "document_info": {...},
        "chunks": [
            {
                "chunk_id": "chunk_001",
                "type": "text|image|table",
                "content": "...",
                "position": {...},
                "metadata": {...}
            }
        ]
    }
    """
    
    # 提取文档基础信息
    doc_info = raw_output.get('document_info', {})
    document_id = generate_document_id()
    
    # 创建DocumentSummary
    doc_summary = DocumentSummaryV3(
        content_id=generate_content_id(),
        rtr_document_id=document_id,
        rtr_project_id=project_id,
        prc_mineru_raw_output=raw_output,
        ana_total_pages=doc_info.get('total_pages', 0),
        sys_mineru_task_id=raw_output.get('task_id')
    )
    
    # 解析chunks
    chunks = raw_output.get('chunks', [])
    text_chunks = []
    image_chunks = []
    table_chunks = []
    
    for chunk in chunks:
        chunk_type = chunk.get('type')
        base_fields = {
            'rtr_document_id': document_id,
            'rtr_project_id': project_id,
            'rtr_mineru_chunk_id': chunk.get('chunk_id'),
            'rtr_sequence_index': chunk.get('position', {}).get('sequence', 0)
        }
        
        if chunk_type == 'text':
            text_chunks.append(TextChunkV3(
                content_id=generate_content_id(),
                emb_content=chunk.get('content', ''),
                **base_fields
            ))
        elif chunk_type == 'image':
            image_chunks.append(ImageChunkV3(
                content_id=generate_content_id(),
                rtr_media_path=chunk.get('path', ''),
                rtr_caption=chunk.get('caption', ''),
                prc_mineru_metadata=chunk.get('metadata', {}),
                **base_fields
            ))
        # ... 表格处理类似
    
    # 构建完整Schema
    schema = FinalMetadataSchemaV3(document_id=document_id)
    schema.document_summary = doc_summary
    schema.text_chunks = text_chunks
    schema.image_chunks = image_chunks
    schema.table_chunks = table_chunks
    
    return schema
```

### 1.3 本地存储与文件管理（1天）

#### 存储管理器
```python
class LocalStorageManager:
    def __init__(self, base_path: str = "./project_data"):
        self.base_path = Path(base_path)
    
    def get_project_path(self, project_id: str) -> Path:
        """获取项目根目录"""
        return self.base_path / project_id
    
    def get_document_path(self, project_id: str, document_id: str) -> Path:
        """获取文档目录"""
        return self.get_project_path(project_id) / document_id
    
    async def save_final_metadata(self, schema: FinalMetadataSchemaV3) -> str:
        """保存最终metadata"""
        doc_path = self.get_document_path(
            schema.document_summary.rtr_project_id,
            schema.document_summary.rtr_document_id
        )
        doc_path.mkdir(parents=True, exist_ok=True)
        
        file_path = doc_path / "v3_final_metadata.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(schema.to_dict(), f, ensure_ascii=False, indent=2)
        
        return str(file_path)
    
    async def save_mineru_raw_output(self, raw_output: Dict, project_id: str, document_id: str) -> str:
        """保存Mineru原始输出"""
        doc_path = self.get_document_path(project_id, document_id)
        file_path = doc_path / "mineru_raw_output.json"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(raw_output, f, ensure_ascii=False, indent=2)
        
        return str(file_path)
    
    async def save_media_files(self, media_data: List[Dict], project_id: str, document_id: str) -> Dict[str, str]:
        """保存图片和表格文件"""
        doc_path = self.get_document_path(project_id, document_id)
        media_path = doc_path / "media"
        
        images_path = media_path / "images"
        tables_path = media_path / "tables"
        images_path.mkdir(parents=True, exist_ok=True)
        tables_path.mkdir(parents=True, exist_ok=True)
        
        saved_files = {}
        for item in media_data:
            # 保存文件逻辑
            pass
        
        return saved_files
```

---

## 🧪 测试与验证计划

### 测试用例设计
1. **Mineru API连接测试**
   - 认证功能测试
   - 文件上传测试
   - 状态查询测试

2. **数据解析测试**
   - 小文件PDF（`testfiles/1_page_test.pdf`）
   - 中等复杂度PDF（`testfiles/医灵古庙设计方案.pdf`）
   - 边界条件测试（接近200MB、600页限制）

3. **存储功能测试**
   - JSON文件读写
   - 媒体文件保存
   - 项目隔离验证

### 性能与限制测试
- 每日配额管理
- 高优先级配额跟踪
- 降级机制触发测试

---

## 📋 验收标准（更新）

### Phase 0 完成标准
- [ ] V3 Schema完整定义，支持Mineru坐标系统
- [ ] 字段命名符合新规范（emb_*, rtr_*, ana_*, prc_*, sys_*）
- [ ] 项目隔离字段添加完成
- [ ] 本地JSON存储方案实现

### Phase 1 完成标准
- [ ] Mineru API客户端可以成功上传PDF并获取结果
- [ ] Step A数据流可以生成V3 Schema基础数据
- [ ] 降级到V2机制正常工作
- [ ] 本地存储系统稳定运行
- [ ] 支持项目隔离的数据管理

---

## ⚠️ 风险控制

### 高风险项目
1. **Mineru API实际格式未知**
   - 缓解: 创建灵活的数据适配层
   - 应对: 先实现基础框架，数据格式确定后快速适配

2. **API配额限制**
   - 缓解: 实现智能配额管理和降级机制
   - 应对: V2作为完整备选方案

### 中风险项目
1. **本地存储空间管理**
   - 缓解: 实现数据清理和归档机制
   - 应对: 可配置的存储策略

---

## 🎯 下一步行动

**立即开始任务**:
1. 创建`src/pdf_processing_3/`目录和基础文件
2. 实现V3 Schema定义
3. 研究Mineru API实际接口格式
4. 创建本地存储管理器

**等待确认事项**:
1. Mineru API的实际地址和接口格式
2. 项目隔离策略的具体实现需求
3. 本地存储的目录结构偏好

---

请确认这个更新后的计划是否符合你的需求，我们可以立即开始实施Phase 0的工作！ 🚀 