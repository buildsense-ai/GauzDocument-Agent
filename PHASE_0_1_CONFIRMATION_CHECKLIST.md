# ✅ Phase 0-1 确认清单

> **目的**: 在开始实施前，明确所有技术决策和实施细节  
> **请逐项确认**: ✅同意 / ❌需要调整 / ❓需要讨论

---

## 🏗️ 核心架构决策

### A1. 字段命名规范
- [ ] **`emb_*`** - 向量化内容字段（如 `emb_summary`, `emb_content`）
- [ ] **`rtr_*`** - 检索过滤字段（如 `rtr_project_id`, `rtr_document_id`, `rtr_chapter_id`）
- [ ] **`ana_*`** - 统计分析字段（如 `ana_total_pages`, `ana_word_count`）
- [ ] **`prc_*`** - 过程数据字段（如 `prc_full_raw_text_url`，存储到对象存储）
- [ ] **`sys_*`** - 系统字段（如 `sys_created_at`, `sys_schema_version`）

**🤔 问题**: 这套命名规范是否清晰易懂？是否有更好的建议？
✅同意
---

### A2. 项目隔离策略
- [ ] 所有对象统一添加 `rtr_project_id: str` 字段
- [ ] 检索时强制过滤 `rtr_project_id`（硬隔离）
- [ ] 项目ID格式: `"proj_20250101_companyname"` 或 UUID

**🤔 问题**: 项目隔离的粒度是否合适？需要支持跨项目检索吗？
❓需要讨论 ， 没明白，这三个有什么不同
---

### A3. 坐标系统重设计
- [ ] **移除 `page_number` 依赖**（由于Mineru按内容顺序输出）
- [ ] **新坐标系**: `rtr_document_id` → `rtr_chapter_id` → `rtr_index_in_chapter`
- [ ] **关联逻辑**: 同一 chapter_id 下的图片、表格、文本自动关联

**🤔 问题**: 没有页码信息是否会影响现有检索逻辑？需要保留页码作为备选坐标吗？
❌ 需要调整。“坐标系” 这个之后可能会调整。先不考虑页码。看mineru怎么实现的。有可能甚至有它原始chunk id作为坐标。
---

## 🗄️ 数据存储策略

### B1. 三层存储架构
- [ ] **Vector DB**: `emb_*` + `rtr_*` 字段（向量化+高频查询）
- [ ] **Object Storage**: `prc_*` 字段（大文本数据，TTL 90天）
- [ ] **Relational DB**: `ana_*` + `sys_*` 字段（统计+元数据）

**🤔 问题**: 
1. 对象存储选择？MinIO本地部署 vs AWS S3 vs 阿里云OSS？
2. 90天TTL是否合适？是否需要永久保存某些过程数据？
❌ 需要调整：目前都先保存到本地json文件，后续再考虑持久化到对象存储
---

### B2. Schema版本控制
- [ ] **Schema版本**: `sys_schema_version: "3.0.0"`
- [ ] **向后兼容**: 支持V2→V3数据迁移
- [ ] **版本检测**: 运行时检测schema版本，自动选择处理逻辑

**🤔 问题**: 是否需要支持多版本并存？迁移策略是一次性还是增量？

---

## 🔌 Mineru集成细节

### C1. API认证配置
```yaml
mineru:
  access_key: "kvzbwqj2zw9ovz2q20rl"
  secret_key: "yqyb14wpqezo79jaxebo7q5per2nrkdm3pegoj5n"
  base_url: "https://api.mineru.xxx/"  # 待确认实际地址
  timeout: 300
  max_file_size: 100MB
```

**🤔 问题**: 
1. Mineru的实际API地址是什么？
这个需要你阅读 Mineru的官方文档。
2. 是否有官方文档链接？ 
https://mineru.net/apiManage
3. API是否有请求频率限制？
```
Currently, MinerU API is in the beta testing phase. To ensure a stable service experience, we are implementing the following rate-limiting policies for users:

Upload Restrictions: Individual file size must not exceed 200 MB, and the number of pages per uploaded file must not exceed 600 pages.
Page Parsing Limit: Each account has no daily limit on the number of pages parsed, but must adhere to our priority policy. Each user is entitled to a highest priority parsing quota of 2000 pages, and the priority for parsing beyond 2000 pages is reduced (counted within a calendar day).
```

4. 是否支持批量上传？
先不考虑批量上传
---

### C2. 错误处理策略
- [ ] **网络超时**: 自动重试3次，指数退避
- [ ] **API额度限制**: 降级到本地Docling处理
- [ ] **文件格式不支持**: 返回明确错误信息
- [ ] **处理失败**: 保存原始文件，支持手动重新处理

**🤔 问题**: 降级到Docling的触发条件是什么？需要保留V2处理逻辑作为备选吗？
保留V2，但是不考虑Docling。我们就单从新做一个V3，用mineru完成第一步。
---

### C3. 预期数据格式
```json
{
  "document_info": {
    "total_pages": 30,
    "file_size": 1024000,
    "word_count": 5000
  },
  "text_blocks": [
    {"content": "...", "order": 0, "type": "paragraph"}
  ],
  "images": [
    {
      "path": "img_001.png",
      "bbox": [x, y, w, h],
      "caption": "图1: ..."
    }
  ],
  "tables": [
    {
      "path": "table_001.png", 
      "bbox": [x, y, w, h],
      "caption": "表1: ..."
    }
  ]
}
```

**🤔 问题**: 这个格式是基于推测的，实际格式可能不同。如何快速适配？

---

## 🧪 测试与验证

### D1. 测试文件准备
- [ ] **小文件**: `testfiles/1_page_test.pdf` (已有)
- [ ] **中等文件**: `testfiles/医灵古庙设计方案.pdf` (已有)
- [ ] **复杂图表**: 需要准备包含工程图纸、表格的PDF

**🤔 问题**: 是否有特定类型的PDF需要重点测试（如扫描件、手绘图纸等）？

---

### D2. 性能基准
- [ ] **处理时间**: <30秒/10页（可接受范围？）
- [ ] **准确率**: >95% 图表识别率（标准是否过高/过低？）
- [ ] **稳定性**: 99% 成功率（网络异常除外）

**🤔 问题**: 这些指标是否现实？需要根据实际测试调整吗？

---

## 📅 实施计划确认

### E1. 时间安排
```
Day 1: Schema V3设计确认 + final_schema_v3.py创建
Day 2-3: Mineru客户端开发 + API测试
Day 4-5: Step A数据流实现
Day 6-7: 集成测试 + 问题修复
```

**🤔 问题**: 
1. 7天时间是否充足？是否需要预留缓冲时间？
2. 是否需要并行开发以加快进度？

---

### E2. 人员安排
- [ ] **架构设计**: 1人 (Schema设计、技术决策)
- [ ] **后端开发**: 1-2人 (Mineru客户端、数据流)
- [ ] **测试验证**: 1人 (测试用例、性能验证)

**🤔 问题**: 人员配置是否合适？是否需要前端支持？

---

## 🚨 风险评估与应对

### F1. 高风险项
1. **Mineru API不稳定**
   - 应对: 准备Docling降级方案
   - 确认: 是否可接受？

2. **数据格式差异过大**
   - 应对: 创建适配层，支持多格式
   - 确认: 开发适配层的时间成本？

### F2. 中风险项
1. **处理时间过长**
   - 应对: 异步处理+进度通知
   - 确认: 前端是否支持异步UI？

2. **大文件上传失败**
   - 应对: 分块上传+断点续传
   - 确认: Mineru是否支持分块上传？

---

## 💡 开放性问题

### G1. 未来扩展
- [ ] 是否计划支持其他格式（Word、PPT、Excel）？
- [ ] 是否需要考虑多语言PDF处理？
- [ ] 是否需要实时协作编辑功能？

### G2. 运维监控
- [ ] 需要什么级别的日志记录？
- [ ] 是否需要实时监控和告警？
- [ ] 数据备份和恢复策略？

---

## 📋 最终确认清单

请在每项后标注：✅同意 / ❌需要调整 / ❓需要讨论

### 关键决策
- [ ] 字段命名规范（A1）
- [ ] 项目隔离策略（A2）
- [ ] 坐标系统重设计（A3）
- [ ] 三层存储架构（B1）

### 技术细节
- [ ] Mineru API配置（C1）
- [ ] 错误处理策略（C2）
- [ ] 测试标准（D2）
- [ ] 时间安排（E1）

### 风险应对
- [ ] 降级方案可接受（F1.1）
- [ ] 异步处理方案（F2.1）

---

## 🎯 下一步行动

**如果全部确认**:
- 立即开始Phase 0.1 (Schema V3设计)
- 同步准备Mineru API文档和测试环境

**如果有需要调整的项目**:
- 请具体说明调整建议
- 重新评估时间安排
- 必要时召开技术讨论会

---

**请回复确认结果，我们将根据您的反馈立即开始实施！** 🚀 