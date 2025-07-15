#!/usr/bin/env python3
"""
AI智能分块器
使用轻量模型(qwen turbo)对章节内容进行智能分块
替代正则表达式的段落切割
"""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio
import concurrent.futures
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.qwen_client import QwenClient

logger = logging.getLogger(__name__)

@dataclass
class MinimalChunk:
    """最小分块信息"""
    chunk_id: str
    content: str
    chunk_type: str  # paragraph, list_item, heading, image_desc, table_desc
    belongs_to_chapter: str  # 章节ID
    chapter_title: str
    start_pos: int  # 在章节中的位置
    end_pos: int
    word_count: int

class AIChunker:
    """AI智能分块器"""
    
    def __init__(self, model: str = "qwen-turbo"):
        """
        初始化AI分块器
        
        Args:
            model: 使用的轻量模型，默认qwen-turbo
        """
        self.client = QwenClient(
            model=model,
            temperature=0.1,
            max_retries=2
        )
        self.model = model
        print(f"✅ AI分块器初始化完成，使用模型: {model}")
    
    async def chunk_chapter_async(self, 
                                chapter_id: str, 
                                chapter_title: str, 
                                chapter_content: str,
                                start_chunk_id: int) -> List[MinimalChunk]:
        """
        异步对单个章节进行智能分块
        
        Args:
            chapter_id: 章节ID
            chapter_title: 章节标题
            chapter_content: 章节内容
            start_chunk_id: 起始分块ID
            
        Returns:
            List[MinimalChunk]: 分块结果列表
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, 
            self.chunk_chapter_sync,
            chapter_id, chapter_title, chapter_content, start_chunk_id
        )
    
    def chunk_chapter_sync(self, 
                          chapter_id: str, 
                          chapter_title: str, 
                          chapter_content: str,
                          start_chunk_id: int) -> List[MinimalChunk]:
        """
        同步对单个章节进行智能分块
        
        Args:
            chapter_id: 章节ID
            chapter_title: 章节标题
            chapter_content: 章节内容
            start_chunk_id: 起始分块ID
            
        Returns:
            List[MinimalChunk]: 分块结果列表
        """
        print(f"🔪 开始AI智能分块章节: {chapter_title}")
        
        # 如果内容太短，直接返回单个分块
        if len(chapter_content.strip()) < 100:
            return [MinimalChunk(
                chunk_id=f"{chapter_id}_{start_chunk_id}",
                content=chapter_content.strip(),
                chunk_type="paragraph",
                belongs_to_chapter=chapter_id,
                chapter_title=chapter_title,
                start_pos=0,
                end_pos=len(chapter_content),
                word_count=len(chapter_content.strip())
            )]
        
        # 构建提示词
        system_prompt = """你是一个专业的文档分块助手。请将给定的章节内容智能分割成合理的分块，每个分块应该是一个完整的语义单元。

分块原则：
1. 保持语义完整性 - 每个分块应该是一个完整的思想或概念
2. 适当的长度 - 每个分块100-500字符为宜
3. 尊重原文结构 - 保持段落、列表、表格的完整性
4. 图片表格位置 - [图片:...] 和 [表格:...] 应该与相关文本在同一分块中

请返回JSON格式：
{
  "chunks": [
    {
      "content": "分块内容",
      "type": "paragraph|list_item|heading|mixed",
      "reason": "分块原因说明"
    }
  ]
}

注意：
- 不要修改原文内容，只进行分块
- 保持[图片:...]和[表格:...]标记不变
- 如果图片/表格在段落中间，将其与相关文本放在同一分块中"""

        user_prompt = f"""请对以下章节内容进行智能分块：

章节标题：{chapter_title}

章节内容：
{chapter_content}

请严格按照JSON格式返回分块结果。"""
        
        try:
            # 调用AI模型进行分块
            response = self.client.generate_response(
                prompt=user_prompt,
                system_prompt=system_prompt
            )
            
            # 解析响应
            chunks_data = self._parse_chunking_response(response)
            
            # 转换为MinimalChunk对象
            chunks = self._convert_to_minimal_chunks(
                chunks_data, chapter_id, chapter_title, 
                chapter_content, start_chunk_id
            )
            
            print(f"✅ 章节 {chapter_title} 分块完成: {len(chunks)} 个分块")
            return chunks
            
        except Exception as e:
            print(f"❌ AI分块失败，使用回退方案: {e}")
            # 回退到简单分割
            return self._fallback_chunking(
                chapter_id, chapter_title, chapter_content, start_chunk_id
            )
    
    def _parse_chunking_response(self, response: str) -> List[Dict[str, Any]]:
        """解析AI分块响应"""
        try:
            # 提取JSON部分
            if '```json' in response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    response = response[json_start:json_end]
            
            # 解析JSON
            result = json.loads(response)
            return result.get('chunks', [])
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            print(f"尝试修复JSON...")
            
            # 尝试修复常见的JSON格式问题
            fixed_response = self._fix_json_response(response)
            if fixed_response:
                try:
                    result = json.loads(fixed_response)
                    return result.get('chunks', [])
                except json.JSONDecodeError:
                    print("❌ JSON修复失败")
            
            print(f"原始响应前500字符: {response[:500]}")
            return []
    
    def _fix_json_response(self, response: str) -> Optional[str]:
        """尝试修复JSON响应中的常见问题"""
        try:
            # 1. 移除可能的非JSON前缀和后缀
            response = response.strip()
            
            # 2. 查找JSON的开始和结束位置
            json_start = response.find('{')
            json_end = response.rfind('}')
            
            if json_start == -1 or json_end == -1 or json_end <= json_start:
                return None
            
            json_content = response[json_start:json_end + 1]
            
            # 3. 修复字符串中的未转义字符
            import re
            
            # 方法1：使用正则表达式修复字符串值
            def fix_string_value(match):
                """修复字符串值中的未转义字符"""
                full_match = match.group(0)
                key = match.group(1)
                value = match.group(2)
                
                # 转义字符串值中的特殊字符
                value = value.replace('\\', '\\\\')  # 转义反斜杠
                value = value.replace('"', '\\"')    # 转义引号
                value = value.replace('\n', '\\n')   # 转义换行符
                value = value.replace('\r', '\\r')   # 转义回车符
                value = value.replace('\t', '\\t')   # 转义制表符
                
                return f'"{key}": "{value}"'
            
            # 匹配 "key": "value" 格式，其中value可能包含未转义的字符
            pattern = r'"([^"]+)":\s*"([^"]*(?:[^"\\]|\\.)*)(?!["])'
            
            # 逐步修复
            lines = json_content.split('\n')
            fixed_lines = []
            
            for i, line in enumerate(lines):
                try:
                    # 尝试解析当前行，看是否有语法错误
                    if '"' in line and ':' in line:
                        # 检查是否是键值对行
                        if line.strip().startswith('"') and '":' in line:
                            # 查找值的开始位置
                            colon_pos = line.find('":')
                            if colon_pos != -1:
                                value_start = colon_pos + 2
                                # 跳过空白字符
                                while value_start < len(line) and line[value_start] in ' \t':
                                    value_start += 1
                                
                                if value_start < len(line) and line[value_start] == '"':
                                    # 找到值的结束位置
                                    value_end = len(line)
                                    for j in range(value_start + 1, len(line)):
                                        if line[j] == '"' and line[j-1] != '\\':
                                            value_end = j
                                            break
                                    
                                    # 如果没有找到结束引号，或者在结束引号后面还有内容
                                    if value_end == len(line) or (value_end < len(line) - 1 and line[value_end + 1:].strip() not in [',', '']):
                                        # 截取到逗号或行尾
                                        actual_end = len(line)
                                        for j in range(value_start + 1, len(line)):
                                            if line[j] == ',' and line[j-1] != '\\':
                                                actual_end = j
                                                break
                                        
                                        # 提取并清理值
                                        value_content = line[value_start + 1:actual_end]
                                        if value_content.endswith('"'):
                                            value_content = value_content[:-1]
                                        
                                        # 转义特殊字符
                                        value_content = value_content.replace('\\', '\\\\')
                                        value_content = value_content.replace('"', '\\"')
                                        value_content = value_content.replace('\n', '\\n')
                                        value_content = value_content.replace('\r', '\\r')
                                        value_content = value_content.replace('\t', '\\t')
                                        
                                        # 重构行
                                        key_part = line[:value_start]
                                        remaining = line[actual_end:]
                                        fixed_line = f'{key_part}"{value_content}"{remaining}'
                                        fixed_lines.append(fixed_line)
                                        continue
                    
                    # 如果不需要修复，直接添加
                    fixed_lines.append(line)
                    
                except Exception as e:
                    # 如果修复失败，使用原始行
                    fixed_lines.append(line)
            
            # 重新组装
            json_content = '\n'.join(fixed_lines)
            
            # 4. 确保JSON正确结束
            if not json_content.rstrip().endswith('}'):
                json_content = json_content.rstrip() + '}'
            
            return json_content
            
        except Exception as e:
            print(f"❌ 复杂JSON修复失败: {e}")
            
            # 备用方案：使用更简单的修复策略
            try:
                return self._simple_json_fix(response)
            except Exception as e2:
                print(f"❌ 简单JSON修复也失败: {e2}")
                return None
    
    def _simple_json_fix(self, response: str) -> Optional[str]:
        """简单的JSON修复策略"""
        try:
            # 1. 查找JSON边界
            json_start = response.find('{')
            json_end = response.rfind('}')
            
            if json_start == -1 or json_end == -1:
                return None
            
            json_content = response[json_start:json_end + 1]
            
            # 2. 简单粗暴的修复：移除所有换行符和多余的引号
            # 按行处理，修复字符串值
            lines = json_content.split('\n')
            fixed_lines = []
            
            for line in lines:
                # 跳过空行
                if not line.strip():
                    continue
                
                # 处理包含字符串值的行
                if '":' in line and '"' in line:
                    # 找到冒号位置
                    colon_pos = line.find('":')
                    if colon_pos != -1:
                        key_part = line[:colon_pos + 2]
                        value_part = line[colon_pos + 2:].strip()
                        
                        # 如果值部分以引号开始，这是一个字符串值
                        if value_part.startswith('"'):
                            # 移除开头的引号
                            value_content = value_part[1:]
                            
                            # 查找结束位置（逗号或行尾）
                            end_pos = len(value_content)
                            if ',' in value_content:
                                end_pos = value_content.rfind(',')
                            
                            actual_value = value_content[:end_pos].strip()
                            remaining = value_content[end_pos:] if end_pos < len(value_content) else ""
                            
                            # 移除可能的尾部引号
                            if actual_value.endswith('"'):
                                actual_value = actual_value[:-1]
                            
                            # 清理值：转义特殊字符
                            actual_value = actual_value.replace('\\', '\\\\')  # 先转义反斜杠
                            actual_value = actual_value.replace('"', '\\"')    # 转义引号
                            actual_value = actual_value.replace('\n', '\\n')   # 转义换行
                            actual_value = actual_value.replace('\r', '\\r')   # 转义回车
                            actual_value = actual_value.replace('\t', '\\t')   # 转义制表符
                            
                            # 重新构造行
                            fixed_line = f'{key_part} "{actual_value}"{remaining}'
                            fixed_lines.append(fixed_line)
                            continue
                
                # 对于其他行，直接添加
                fixed_lines.append(line)
            
            # 3. 重新组装
            result = '\n'.join(fixed_lines)
            
            # 4. 确保JSON正确结束
            if not result.rstrip().endswith('}'):
                result = result.rstrip() + '}'
            
            return result
            
        except Exception as e:
            print(f"❌ 简单JSON修复失败: {e}")
            return None
    
    def _convert_to_minimal_chunks(self,
                                  chunks_data: List[Dict[str, Any]],
                                  chapter_id: str,
                                  chapter_title: str,
                                  chapter_content: str,
                                  start_chunk_id: int) -> List[MinimalChunk]:
        """转换为MinimalChunk对象"""
        chunks = []
        current_pos = 0
        
        for i, chunk_data in enumerate(chunks_data):
            content = chunk_data.get('content', '').strip()
            chunk_type = chunk_data.get('type', 'paragraph')
            
            if not content:
                continue
            
            # 在章节内容中查找这个分块的位置
            start_pos = chapter_content.find(content, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            
            end_pos = start_pos + len(content)
            current_pos = end_pos
            
            chunk = MinimalChunk(
                chunk_id=f"{chapter_id}_{start_chunk_id + i}",
                content=content,
                chunk_type=chunk_type,
                belongs_to_chapter=chapter_id,
                chapter_title=chapter_title,
                start_pos=start_pos,
                end_pos=end_pos,
                word_count=len(content)
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _fallback_chunking(self,
                          chapter_id: str,
                          chapter_title: str,
                          chapter_content: str,
                          start_chunk_id: int) -> List[MinimalChunk]:
        """回退分块方案 - 基于简单规则"""
        print(f"🔄 使用回退分块方案")
        
        chunks = []
        
        # 简单的段落分割
        paragraphs = chapter_content.split('\n\n')
        
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 判断类型
            chunk_type = "paragraph"
            if paragraph.startswith('#'):
                chunk_type = "heading"
            elif paragraph.startswith('-') or paragraph.startswith('•'):
                chunk_type = "list_item"
            elif '[图片:' in paragraph:
                chunk_type = "mixed"
            elif '[表格:' in paragraph:
                chunk_type = "mixed"
            
            chunk = MinimalChunk(
                chunk_id=f"{chapter_id}_{start_chunk_id + i}",
                content=paragraph,
                chunk_type=chunk_type,
                belongs_to_chapter=chapter_id,
                chapter_title=chapter_title,
                start_pos=0,
                end_pos=len(paragraph),
                word_count=len(paragraph)
            )
            
            chunks.append(chunk)
        
        return chunks
    
    async def chunk_chapters_batch(self, 
                                 chapters: List[Dict[str, Any]],
                                 max_workers: int = 3) -> List[MinimalChunk]:
        """
        批量异步处理章节分块
        
        Args:
            chapters: 章节列表，每个包含chapter_id, title, content
            max_workers: 最大并发数
            
        Returns:
            List[MinimalChunk]: 所有分块结果
        """
        print(f"🚀 开始批量异步分块，共 {len(chapters)} 个章节")
        
        all_chunks = []
        chunk_counter = 0
        
        # 创建异步任务
        tasks = []
        for chapter in chapters:
            task = self.chunk_chapter_async(
                chapter['chapter_id'],
                chapter['title'],
                chapter['content'],
                chunk_counter
            )
            tasks.append(task)
            
            # 估算分块数量（用于ID计算）
            estimated_chunks = max(1, len(chapter['content']) // 200)
            chunk_counter += estimated_chunks
        
        # 控制并发数
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_with_semaphore(task):
            async with semaphore:
                return await task
        
        # 执行所有任务
        results = await asyncio.gather(*[process_with_semaphore(task) for task in tasks])
        
        # 合并结果
        for chapter_chunks in results:
            all_chunks.extend(chapter_chunks)
        
        print(f"✅ 批量分块完成，共生成 {len(all_chunks)} 个分块")
        return all_chunks

# 便捷函数
def chunk_chapters_with_ai(chapters: List[Dict[str, Any]], 
                          model: str = "qwen-turbo",
                          max_workers: int = 3) -> List[MinimalChunk]:
    """
    使用AI对章节进行智能分块的便捷函数
    
    Args:
        chapters: 章节列表
        model: 使用的模型
        max_workers: 最大并发数
        
    Returns:
        List[MinimalChunk]: 分块结果
    """
    chunker = AIChunker(model=model)
    
    # 运行异步任务
    return asyncio.run(chunker.chunk_chapters_batch(chapters, max_workers))

# 测试函数
async def test_ai_chunker():
    """测试AI分块器"""
    chunker = AIChunker()
    
    # 测试章节
    test_chapter = {
        'chapter_id': '1',
        'title': '设计依据',
        'content': '''## 设 计 依 据

- 2.占地基建面积：125.9平方米，门前花园占地面积：65平方米，总建筑面积：473.6平方米
- 3.建筑物层数为：2层
- 4.本工程为多层建筑，耐火等级为二级，抗震设防为七度，防水等级为二级。

1. 《中华人民共和国文物保护法》（2024 年修订）
2. 《中华人民共和国文物保护法实施条例》（2015年）

[图片: Error: An unexpected error occurred while fetching the image description.]

[图片: Error: An unexpected error occurred while fetching the image description.]

3. 《民用建筑设计通则》［GB50352-2015］
4. 《住宅建筑设计规范》［GB 50096-2011］
5. 《建筑设计防火规范》[GB50016-2014]
6. 《建筑抗震设计规范》[GB50011-2010]
7. 《建筑内部装修设计防火规范》[GB50222-2015]
8. 《住宅建筑规范》[GB50368-2005]
9. 《住宅设计规范》[GB50096-2011]
- 10.《城市道路和建筑物无障碍设计规范》[JGJ50-2013]
- 11.《建筑防水工程技术规程》[DBJ15-19-2016]'''
    }
    
    chunks = await chunker.chunk_chapter_async(
        test_chapter['chapter_id'],
        test_chapter['title'],
        test_chapter['content'],
        0
    )
    
    print(f"\n🎯 测试结果: {len(chunks)} 个分块")
    for i, chunk in enumerate(chunks):
        print(f"\n--- 分块 {i+1} ---")
        print(f"ID: {chunk.chunk_id}")
        print(f"类型: {chunk.chunk_type}")
        print(f"内容: {chunk.content[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_ai_chunker()) 