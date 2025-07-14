# Qwen API 配置指南

## 添加 Qwen API 支持

我们已经添加了对阿里云通义千问（Qwen）模型的支持，以解决 DeepSeek 高 timeout 率的问题。

### 为什么选择 Qwen？

- **高 Rate Limit**: 每分钟 1,200 次调用，5,000,000 token
- **稳定性**: 阿里云基础设施，稳定性更好
- **兼容性**: 支持 OpenAI SDK，易于集成
- **批处理**: 支持批处理模式，提高并发性能

### 配置步骤

1. **设置环境变量**：
   ```bash
   export QWEN_API_KEY="sk-0f666c8a6d7147f69b1dd240aab34c75"
   export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
   ```

2. **或者创建 .env 文件**：
   ```
   # AI模型配置
   # 阿里云通义千问 API 配置
   QWEN_API_KEY=sk-0f666c8a6d7147f69b1dd240aab34c75
   QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   
   # DeepSeek API 配置 (备用)
   DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
   
   # OpenRouter API 配置 (用于多模态)
   OPENROUTER_API_KEY=sk-your-openrouter-api-key-here
   
   # PDF处理配置
   PDF_DEFAULT_LLM_MODEL=qwen-turbo-latest
   PDF_DEFAULT_VLM_MODEL=google/gemini-2.5-flash
   PDF_MAX_WORKERS=10
   PDF_ENABLE_TEXT_CLEANING=true
   PDF_ENABLE_IMAGE_DESCRIPTION=true
   PDF_ENABLE_TABLE_DESCRIPTION=true
   PDF_PARALLEL_PROCESSING=true
   
   # 输出配置
   PDF_OUTPUT_DIR=parser_output
   PDF_CUSTOM_OUTPUT_PATH=
   
   # 其他配置
   PDF_IMAGES_SCALE=2.0
   ```

### 支持的模型

- `qwen-turbo-latest` - 默认模型，高性能
- `qwen-plus-latest` - 高级模型
- `qwen-max-latest` - 最强模型

### 降级策略

系统会按以下顺序尝试模型：
1. Qwen（主要）
2. DeepSeek（备用）
3. 跳过处理（如果都失败）

### 使用示例

```python
from src.qwen_client import QwenClient

# 初始化客户端
client = QwenClient(
    model="qwen-turbo-latest",
    max_tokens=4000,
    timeout=60,
    max_retries=3,
    enable_batch_mode=True
)

# 单个请求
response = client.generate_response("请清洗这段文本...")

# 批量请求
responses = client.batch_generate_responses([
    "请求1",
    "请求2",
    "请求3"
], max_workers=10)

# 查看统计信息
client.print_stats()
```

### 性能优化特性

1. **批处理模式**: 支持并行处理多个请求
2. **自动重试**: 支持指数退避重试
3. **统计监控**: 实时监控成功率和性能
4. **错误分类**: 区分超时错误和API错误

### 测试连接

```bash
# 测试 Qwen API 连接
python -c "
from src.qwen_client import QwenClient
client = QwenClient()
print(client.generate_response('你好'))
client.print_stats()
"
```

### 故障排查

1. **API Key 错误**: 检查环境变量设置
2. **网络连接**: 确保可以访问阿里云服务
3. **超时问题**: 增加 timeout 设置
4. **Rate Limit**: 减少并发数或增加重试间隔

### 配置已完成的更新

- ✅ 创建了 `src/qwen_client.py` 客户端
- ✅ 更新了 `src/pdf_processing/config.py` 配置
- ✅ 更新了 `src/pdf_processing/ai_content_reorganizer.py`
- ✅ 更新了 `src/pdf_processing/document_structure_analyzer.py`
- ✅ 更新了 `src/pdf_processing/metadata_enricher.py`
- ✅ 设置了优雅降级策略

现在系统默认使用 Qwen，如果失败会降级到 DeepSeek。 