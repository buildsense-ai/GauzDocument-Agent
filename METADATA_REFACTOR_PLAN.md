# 📑 Metadata Schema Refactor & Development Roadmap

> Status: **Draft v0.1**   Date: {{DATE}}

---

## 1. Field-Name Migration Matrix

下面对比 V2 现有 `final_schema.py` 与 **新版 Final Schema（讨论稿）** 的字段，标注变动类型：

Legend  
• **UNCH** = 字段保留（名字不变）  
• **RENAME** = 仅改名前缀 / 命名  
• **MOVE** = 迁到其它层（向量库→关系库 / 对象存储）  
• **DEL** = 删除  
• **ADD** = 新增字段

### 1.1 DocumentSummary
| V2 字段 | 新字段 | 变动 | 说明 |
|---------|--------|------|------|
| content_id | UNCH | UNCH | 主键、不进向量库 |
| document_id | rtr_document_id | RENAME | 检索隔离主键 |
| **NEW** | rtr_project_id | ADD | 项目隔离硬过滤 |
| content_type | rtr_content_type | RENAME | 常量 "document_summary" |
| content_level | **DEL** | DEL | 层级信息由 content_type 隐含 |
| full_raw_text | prc_full_raw_text (URL) | MOVE | 过程数据 → 对象存储 |
| ai_summary | emb_summary | RENAME | 送向量化文本 |
| source_file_path | rtr_source_path | RENAME | 检索可用（定位文件） |
| file_name | rtr_file_name | RENAME | UI 展示 / 排序 |
| file_size | ana_file_size | MOVE | 统计字段，仅关系库 |
| page_texts | prc_page_texts (URL) | MOVE | 过程数据，TTL 90d |
| cleaned_page_texts | prc_cleaned_page_texts (URL) | MOVE | 过程数据，TTL 90d |
| toc | prc_toc (JSON/URL) | MOVE | 调试用 |
| metadata | **DEL** | DEL | 模糊字段拆分后不再需要 |
| total_pages | ana_total_pages | MOVE | 统计字段 |
| total_word_count | ana_total_word_count | MOVE | 统计字段 |
| chapter_count | ana_chapter_count | MOVE | 统计字段 |
| image_count | ana_image_count | MOVE | 统计字段 |
| table_count | ana_table_count | MOVE | 统计字段 |
| processing_time | ana_processing_time | MOVE | 运维监控 |
| created_at | sys_created_at | RENAME | 系统公共字段 |

### 1.2 TextChunk
| V2 字段 | 新字段 | 变动 | 说明 |
|---------|--------|------|------|
| content_id | UNCH | UNCH | 主键 |
| document_id | rtr_document_id | RENAME | |
| **NEW** | rtr_project_id | ADD | |
| content_type | rtr_content_type | RENAME | 常量 "text_chunk" |
| content_level | **DEL** | DEL | 不再需要 |
| content | emb_content | RENAME | 向量文本 |
| chapter_id | rtr_chapter_id | RENAME | 坐标 |
| chunk_index | rtr_index_in_chapter | RENAME | 坐标 |
| word_count | ana_word_count | MOVE | 统计 |
| created_at | sys_created_at | RENAME | |

### 1.3 ImageChunk (TableChunk 同理)
| V2 字段 | 新字段 | 变动 | 说明 |
|---------|--------|------|------|
| image_path | rtr_media_path | RENAME | 存储地址 |
| page_number | **DEL** | DEL | 顺序由 index_in_chapter 代替 |
| caption | rtr_caption | RENAME | 简短标题 |
| chapter_id | rtr_chapter_id | RENAME | 坐标 |
| page_context | prc_page_context (URL) | MOVE | 过程文本 |
| width/height/aspect_ratio | rtr_width/… | RENAME | 排版过滤 |
| size | ana_size | MOVE | 统计 |
| search_summary | emb_search_summary | RENAME | 向量文本 |
| detailed_description | emb_detail_desc | RENAME | |
| engineering_details | emb_engineering_desc | RENAME | |
| created_at | sys_created_at | RENAME | |
| **NEW** | rtr_index_in_chapter | ADD | 坐标 |
| **NEW** | rtr_project_id | ADD | 项目隔离 |

### 1.4 ChapterSummary
| V2 字段 | 新字段 | 变动 | 说明 |
|---------|--------|------|------|
| raw_content | prc_raw_content (URL) | MOVE | 过程文本 |
| ai_summary | emb_ai_summary | RENAME | |
| chapter_id | rtr_chapter_id | RENAME | |
| chapter_title | rtr_chapter_title | RENAME | |
| word_count | ana_word_count | MOVE | |
| ... | 其余字段同上 |  |

### 1.5 DerivedQuestion
| 字段 | 新字段 | 变动 | 说明 |
|-------|---------|------|------|
| content | emb_content | RENAME | 问题文本 |
| question_type | rtr_question_type | RENAME | |
| confidence_score | rtr_confidence_score | RENAME | |
| source_context | prc_source_context (URL) | MOVE | 过程 |
| created_at | sys_created_at | RENAME | |
| **NEW** | rtr_project_id | ADD | |

> ⚠️ 以上表格只展示有变动或新增/删除的字段，未列出的字段保持不变。详细属性（类型、默认值）将在后续代码重构时统一更新。

---

## 2. Phased Development Roadmap

### Phase 0  │ 团队对齐 & 文档化
- [ ] 评审并定稿本文件（字段、命名前缀、存储策略）。
- [ ] 创建 `final_schema_v3.py`（草稿），仅包含 dataclass / Pydantic 模型定义。

### Phase 1  │ 外部服务整合（Mineru）
- [ ] 封装 Mineru SDK ⇒ `mineru_client.py`
- [ ] 实现 `Step A`：上传 PDF ➜ 获取 `raw_service_output.json` ➜ **填充 v3 Schema (DocumentSummary + Image/Table skeleton)**
- [ ] 单元测试：3 份样例 PDF，验证完整性。

### Phase 2  │ 内部 AI Processor 重构
- [ ] 复用现有 Stage 2 逻辑，改写为 `ai_processor_v3.py`，输入 v3 Schema。
  - OCR 质量检测 → 决定是否调用修复
  - TOC 校验 / 生成
  - 语义分块校验 / 回退
  - Gemini-Flash 生成多模态描述
- [ ] 输出完整的 v3 Final Schema (`final_metadata.json`)

### Phase 3  │ Ingestion & Retrieval Pipeline 更新
- [ ] 向量化脚本支持 v3 字段（仅 `emb_* + rtr_*`）
- [ ] 更新检索 API，强制注入 `rtr_project_id` 过滤
- [ ] Ranking 函数增加 “同章关联” 权重

### Phase 4  │ Back-fill & Migration
- [ ] 编写迁移脚本：V2 ➜ V3（字段映射表用本文件）
- [ ] 批量回填历史数据，增量双写 2 周，观察异常

### Phase 5  │ QA & Rollout
- [ ] 功能测试、性能基准
- [ ] 监控与告警配置（向量查询 QPS、延迟、磁盘增长）
- [ ] 切换流量到 V3，V2 进入维护期

### Phase 6  │ Cleanup & Docs
- [ ] 移除 V2 专用字段 / 代码路径
- [ ] 更新开发者文档、API 文档

---

### 📌 版本策略
- `schema_version: "3.0.0"` 将写入 Final Schema 顶层字段。
- 代码包版本：`pdf-processing==3.x`
- 迁移工具：`migration_v2_to_v3.py`（一次性执行）

---

### ✉️ 后续
对本文件有任何补充或异议，请在 PR 评论中留下意见，或在下次技术例会中讨论。创建正式 PR 前请勿修改现有运行代码。 