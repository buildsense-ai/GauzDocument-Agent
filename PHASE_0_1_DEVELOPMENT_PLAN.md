# 📋 Phase 0 & Phase 1 详细开发计划

> **项目**: PDF处理V3重构 | **阶段**: Phase 0-1 | **状态**: 待确认  
> **更新时间**: {{TODAY}} | **预计完成时间**: 5-7个工作日

---

## 🎯 总体目标

1. **Phase 0**: 完成团队对齐，创建新的V3 Schema定义
2. **Phase 1**: 集成Mineru外部服务，实现Step A数据流

---

## 📊 Phase 0: 团队对齐 & Schema设计

### 0.1 Schema V3 设计确认（1天）

#### 任务清单
- [ ] **字段命名规范最终确认**
  - `emb_*` - 向量化内容字段
  - `rtr_*` - 检索过滤字段（高频+坐标）
  - `ana_*` - 统计分析字段
  - `prc_*` - 过程数据字段（将迁移至对象存储）
  - `sys_*` - 系统字段

- [ ] **项目隔离设计**
  - 所有对象统一添加 `rtr_project_id` 字段
  - 确认项目隔离在检索层的实现方式

#### 技术决策点
1. **字段存储策略**:
   - Vector DB: `emb_*` + `rtr_*` 字段
   - Object Storage: `prc_*` 字段（大文本数据）
   - Relational DB: `ana_*` + `sys_*` 字段

2. **坐标系统重设计**:
   - 移除 `page_number` 依赖
   - 基于 `rtr_chapter_id` + `rtr_index_in_chapter` 定位
   - 利用Mineru的顺序输出特性

### 0.2 创建 final_schema_v3.py（1天）

#### 文件结构
```python
src/pdf_processing_3/
├── __init__.py
├── final_schema_v3.py     # 新Schema定义
├── mineru_client.py       # Phase 1创建
└── config.py              # 配置管理
```

#### Schema类设计
```python
# 六大核心对象重新设计
@dataclass
class DocumentSummaryV3:
    # 核心字段
    content_id: str
    rtr_document_id: str
    rtr_project_id: str        # 新增项目隔离
    rtr_content_type: str = "document_summary"
    
    # 向量化字段
    emb_summary: Optional[str] = None
    
    # 检索字段
    rtr_source_path: str = ""
    rtr_file_name: str = ""
    
    # 过程数据字段（将存储到对象存储）
    prc_full_raw_text_url: Optional[str] = None
    prc_page_texts_url: Optional[str] = None
    prc_toc_url: Optional[str] = None
    
    # 统计字段
    ana_total_pages: int = 0
    ana_word_count: Optional[int] = None
    ana_image_count: int = 0
    ana_table_count: int = 0
    
    # 系统字段
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sys_schema_version: str = "3.0.0"
```

#### 交付物
- `final_schema_v3.py` - 完整的V3数据模型
- `migration_mapping.json` - V2→V3字段映射配置
- Schema文档更新

---

## 🔌 Phase 1: Mineru外部服务集成

### 1.1 Mineru API 研究与封装（2天）

#### API研究任务
- [ ] **Mineru API文档分析**
  - 上传PDF的接口规格
  - 返回数据格式分析
  - 错误处理机制
  - 并发限制和速率限制

- [ ] **认证与安全**
  ```python
  # 预期的配置结构
  MINERU_CONFIG = {
      "access_key": "kvzbwqj2zw9ovz2q20rl",
      "secret_key": "yqyb14wpqezo79jaxebo7q5per2nrkdm3pegoj5n",
      "base_url": "https://api.mineru.xxx/",  # 待确认
      "timeout": 300,
      "max_file_size": 100 * 1024 * 1024  # 100MB
  }
  ```

#### 创建 mineru_client.py
```python
class MineruClient:
    def __init__(self, access_key: str, secret_key: str, base_url: str):
        """Mineru API客户端初始化"""
        
    async def upload_pdf(self, file_path: str, project_id: str) -> str:
        """上传PDF，返回任务ID"""
        
    async def get_processing_status(self, task_id: str) -> Dict:
        """查询处理状态"""
        
    async def get_result(self, task_id: str) -> Dict:
        """获取处理结果（完整的JSON数据）"""
        
    def parse_mineru_output(self, raw_output: Dict) -> Tuple[DocumentSummaryV3, List[ImageChunk], List[TableChunk]]:
        """解析Mineru输出，填充V3 Schema骨架"""
```

#### 技术要点
1. **异步处理支持**: 使用 `asyncio` 处理大文件上传
2. **重试机制**: 网络错误、超时的自动重试
3. **进度跟踪**: 实时更新处理进度
4. **错误分类**: 区分业务错误和技术错误

### 1.2 Step A 数据流实现（2天）

#### 核心流程设计
```python
async def process_pdf_step_a(pdf_path: str, project_id: str) -> FinalMetadataSchemaV3:
    """
    Step A: 外部服务处理阶段
    
    输入: PDF文件路径, 项目ID
    输出: 填充基础数据的V3 Schema
    """
    
    # 1. 上传PDF到Mineru
    task_id = await mineru_client.upload_pdf(pdf_path, project_id)
    
    # 2. 轮询处理状态
    while not is_complete:
        status = await mineru_client.get_processing_status(task_id)
        # 更新进度，处理错误
        
    # 3. 获取结果并解析
    raw_output = await mineru_client.get_result(task_id)
    
    # 4. 填充V3 Schema
    doc_summary, images, tables = mineru_client.parse_mineru_output(raw_output)
    
    # 5. 保存中间结果
    schema = FinalMetadataSchemaV3(document_id=doc_summary.rtr_document_id)
    schema.document_summary = doc_summary
    schema.image_chunks = images
    schema.table_chunks = tables
    
    # 6. 保存原始数据到对象存储
    await save_process_data(raw_output, task_id)
    
    return schema
```

#### 数据映射策略
```python
def map_mineru_to_v3_schema(mineru_data: Dict) -> Tuple[DocumentSummaryV3, List, List]:
    """
    Mineru数据 → V3 Schema映射
    
    关键映射逻辑:
    1. 提取文档基础信息 → DocumentSummaryV3
    2. 图片数据 → ImageChunk (skeleton, 缺AI描述)
    3. 表格数据 → TableChunk (skeleton, 缺AI描述)
    4. 文本块数据 → 暂存，等待Chapter分析
    """
    
    # 预期Mineru返回格式 (需要验证)
    {
        "document_info": {
            "total_pages": 30,
            "file_size": 1024000,
            "word_count": 5000
        },
        "text_blocks": [
            {"content": "...", "page": 1, "order": 0},
            # ...
        ],
        "images": [
            {
                "path": "img_001.png",
                "page": 1,
                "bbox": [x, y, w, h],
                "caption": "图1: ..."
            }
        ],
        "tables": [
            {
                "path": "table_001.png", 
                "page": 2,
                "bbox": [x, y, w, h],
                "caption": "表1: ..."
            }
        ]
    }
```

### 1.3 集成测试与验证（1天）

#### 测试用例设计
1. **基础功能测试**
   - 小文件PDF（<5MB, <10页）
   - 中等文件PDF（10-50MB, 10-50页）
   - 包含复杂图表的工程文档

2. **边界条件测试**
   - 超大文件处理
   - 网络超时场景
   - API配额限制测试

3. **数据完整性验证**
   - Mineru输出数据格式验证
   - V3 Schema字段填充完整性
   - 坐标系统准确性验证

#### 性能基准
- 处理时间: <30秒/10页
- 数据准确性: >95% 图表识别率
- 稳定性: 99% 成功率

---

## 🗓️ 时间规划

| 阶段 | 任务 | 负责人 | 预计时间 | 依赖关系 |
|------|------|--------|----------|----------|
| **Phase 0.1** | Schema V3设计确认 | 架构师 | 1天 | - |
| **Phase 0.2** | final_schema_v3.py | 开发 | 1天 | 0.1完成 |
| **Phase 1.1** | Mineru客户端开发 | 开发 | 2天 | 0.2完成 |
| **Phase 1.2** | Step A数据流实现 | 开发 | 2天 | 1.1完成 |
| **Phase 1.3** | 集成测试验证 | QA+开发 | 1天 | 1.2完成 |

**总计**: 7个工作日

---

## 🚀 技术栈与工具

### 新增依赖
```python
# requirements_v3.txt 新增
aiohttp>=3.8.0           # 异步HTTP客户端
aiofiles>=0.8.0          # 异步文件操作
tenacity>=8.0.0          # 重试机制
pydantic>=1.10.0         # 数据验证增强
```

### 配置管理
```python
# config/mineru_config.py
@dataclass
class MineruConfig:
    access_key: str
    secret_key: str
    base_url: str = "https://api.mineru.xxx/"
    timeout: int = 300
    max_retries: int = 3
    upload_chunk_size: int = 8 * 1024 * 1024  # 8MB chunks
```

---

## 📋 验收标准

### Phase 0 完成标准
- [ ] V3 Schema文件创建完成，包含所有6大对象
- [ ] 字段命名规范100%符合新标准
- [ ] 项目隔离字段已添加到所有对象
- [ ] 迁移映射文档完整

### Phase 1 完成标准
- [ ] Mineru客户端可以成功上传PDF并获取结果
- [ ] Step A数据流可以生成V3 Schema骨架数据
- [ ] 3份测试PDF处理成功率>95%
- [ ] 图片、表格的坐标和基础信息正确提取
- [ ] 过程数据正确保存到对象存储

---

## ⚠️ 风险点与缓解措施

### 高风险
1. **Mineru API不稳定或文档不全**
   - 缓解: 提前与Mineru技术支持沟通，准备降级方案
   
2. **数据格式不符合预期**
   - 缓解: 创建数据适配层，支持多版本格式

### 中风险
1. **处理时间过长影响用户体验**
   - 缓解: 实现异步处理+进度通知
   
2. **大文件上传失败**
   - 缓解: 分块上传+断点续传

---

## 🎯 下阶段预告

**Phase 2 准备**:
- AI Processor V3重构（复用现有Stage 2逻辑）
- TOC提取和校验
- Gemini Flash多模态描述生成
- 语义分块验证和优化

**需要提前准备的资源**:
- Gemini API配额确认
- 对象存储服务搭建（MinIO/AWS S3）
- 监控和日志系统升级

---

## 📞 沟通与确认

请在开始实施前确认以下事项：

1. **Mineru API访问确认**
   - API文档获取
   - 测试环境访问权限
   - 配额和限制说明

2. **技术方案确认**
   - V3 Schema设计是否符合预期
   - 对象存储方案选择
   - 异步处理架构认可

3. **时间安排确认**
   - 7天工作周期是否可接受
   - 人员安排和优先级
   - 风险点应对策略

**请回复确认后，我们即可开始Phase 0的具体实施。** 