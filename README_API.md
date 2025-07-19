# ReAct Agent 文档查询 FastAPI 服务

基于ReAct Agent的智能文档检索系统，提供自然语言查询API接口。

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制环境变量模板并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少配置以下必需项：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

### 3. 启动服务

```bash
# 方法1：使用启动脚本
python start_api.py

# 方法2：直接运行app.py
python app.py

# 方法3：使用uvicorn命令
uvicorn app:app --host 0.0.0.0 --port 8000
```

## API 接口文档

### 主要接口

#### POST `/react_agent`

**功能**: ReAct Agent 文档查询接口

**请求格式**:
```json
{
  "query": "请全面介绍中山纪念堂"
}
```

**响应格式**:
```json
{
  "final_answer": {
    "retrieved_text": "中山纪念堂是为纪念孙中山先生而建，于1929年动工..."
  }
}
```

### 辅助接口

#### GET `/`
- **功能**: 服务状态查询
- **响应**: 基本服务信息

#### GET `/health`
- **功能**: 健康检查
- **响应**: 服务健康状态

#### GET `/docs`
- **功能**: Swagger API文档
- **访问**: http://localhost:8000/docs

## 使用示例

### 1. 使用 curl

```bash
curl -X POST "http://localhost:8000/react_agent" \
     -H "Content-Type: application/json" \
     -d '{"query": "请介绍中山纪念堂"}'
```

### 2. 使用 Python requests

```python
import requests
import json

url = "http://localhost:8000/react_agent"
payload = {"query": "请介绍中山纪念堂"}

response = requests.post(url, json=payload)
result = response.json()

print(json.dumps(result, ensure_ascii=False, indent=2))
```

### 3. 使用 JavaScript fetch

```javascript
const response = await fetch('http://localhost:8000/react_agent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: '请介绍中山纪念堂'
  })
});

const result = await response.json();
console.log(result);
```

## 部署说明

### 本地开发

```bash
# 开发模式（支持热重载）
python app.py

# 或者使用uvicorn
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 生产环境

```bash
# 生产模式
python start_api.py

# 或者使用gunicorn
pip install gunicorn
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker部署

```dockerfile
FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "start_api.py"]
```

### 使用 cpolar 内网穿透

1. 安装cpolar
2. 启动API服务：`python start_api.py`
3. 启动cpolar：`cpolar http 8000`
4. 获得公网访问地址，如：`https://tall-koala.cpolar.cn`

最终接口地址为：`POST https://tall-koala.cpolar.cn/react_agent`

## 系统架构

```
用户查询 → FastAPI接口 → SimplifiedReactAgent → 搜索工具 → 返回结果
                           ↓
                    两个核心工具：
                    1. template_search_tool (模板搜索)
                    2. search_document (文档搜索)
```

## 错误处理

API会返回标准的HTTP状态码：

- `200`: 请求成功
- `422`: 请求参数错误
- `500`: 内部服务错误
- `503`: 服务不可用

错误响应格式：
```json
{
  "detail": "错误描述信息"
}
```

## 日志

服务日志保存在 `logs/fastapi_service.log` 文件中，包含：
- 请求处理日志
- ReAct Agent执行过程
- 错误信息和堆栈

## 性能优化

1. **启动优化**: Agent在服务启动时初始化，避免每次请求重新初始化
2. **并发处理**: 支持多用户并发查询
3. **错误恢复**: 完善的异常处理和错误恢复机制
4. **日志记录**: 详细的执行日志便于调试和监控

## 联系支持

如有问题，请检查：
1. 环境变量配置是否正确
2. 依赖包是否安装完整  
3. 日志文件中的错误信息
4. API文档：http://localhost:8000/docs 