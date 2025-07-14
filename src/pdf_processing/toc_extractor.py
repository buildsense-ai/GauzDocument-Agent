#!/usr/bin/env python3
"""
TOC提取器 - 基于生成式AI的目录结构提取
使用qwen_plus推理模式提取文档目录结构
"""

import json
import os
import sys
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

load_dotenv()

@dataclass
class TOCItem:
    """TOC条目"""
    title: str
    level: int
    start_text: str  # 用于匹配的开头文本
    page_number: Optional[int] = None
    parent_id: Optional[str] = None
    id: Optional[str] = None

class TOCExtractor:
    """TOC提取器"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化TOC提取器
        
        Args:
            api_key: Qwen API密钥
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        self.base_url = base_url or os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        if not self.api_key:
            raise ValueError("Qwen API key is required. Set QWEN_API_KEY environment variable.")
        
        # 初始化OpenAI兼容客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120  # 增加超时时间
        )
        
        print("✅ TOC提取器初始化成功")
        print(f"🎯 模型: qwen-plus")
        print(f"🔗 基础URL: {self.base_url}")
    
    def stitch_full_text(self, basic_result_path: str) -> str:
        """
        缝合完整文本
        
        Args:
            basic_result_path: basic_processing_result.json文件路径
            
        Returns:
            str: 缝合后的完整文本
        """
        print("🧵 开始缝合完整文本...")
        
        # 读取基础处理结果
        with open(basic_result_path, 'r', encoding='utf-8') as f:
            basic_result = json.load(f)
        
        pages = basic_result.get('pages', [])
        
        # 按页码排序
        pages.sort(key=lambda x: x.get('page_number', 0))
        
        full_text_parts = []
        
        for page in pages:
            page_num = page.get('page_number', 0)
            cleaned_text = page.get('cleaned_text', '')
            images = page.get('images', [])
            tables = page.get('tables', [])
            
            # 添加页码标记
            full_text_parts.append(f"\n===== 第 {page_num} 页 =====\n")
            
            # 添加页面文本
            if cleaned_text.strip():
                full_text_parts.append(cleaned_text.strip())
            
            # 添加图片信息
            for i, image in enumerate(images, 1):
                description = image.get('ai_description', '图片描述')
                full_text_parts.append(f"\n[图片 {page_num}-{i}: {description}]\n")
            
            # 添加表格信息
            for i, table in enumerate(tables, 1):
                description = table.get('ai_description', '表格描述')
                full_text_parts.append(f"\n[表格 {page_num}-{i}: {description}]\n")
        
        full_text = "\n".join(full_text_parts)
        
        print(f"✅ 文本缝合完成，总长度: {len(full_text)} 字符")
        print(f"📄 总页数: {len(pages)}")
        
        return full_text
    
    def extract_toc_with_reasoning(self, full_text: str) -> List[TOCItem]:
        """
        使用推理模式提取TOC
        
        Args:
            full_text: 完整文档文本
            
        Returns:
            List[TOCItem]: TOC项目列表
        """
        print("🧠 开始使用推理模式提取TOC...")
        
        # 构建系统提示
        system_prompt = """你是一个专业的文档结构分析师。请分析给定的文档文本，提取完整的目录结构(TOC)。

要求：
1. 识别所有层级的章节标题（一级、二级、三级等）
2. 为每个章节提供用于匹配的开头文本片段（15-30个字符）
3. 估算每个章节的页码位置
4. 保持章节的层级关系

请以JSON格式返回结果，格式如下：
{
  "toc": [
    {
      "title": "章节标题",
      "level": 1,
      "start_text": "章节开头的文本片段",
      "page_number": 1,
      "id": "chapter_1"
    }
  ]
}

注意：
- level从1开始（1=一级标题，2=二级标题，以此类推）
- start_text应该是章节标题后紧接着的文本，用于精确匹配
- page_number根据"===== 第 X 页 ====="标记来估算
- id使用chapter_1, chapter_2等格式
"""
        
        # 构建用户提示
        user_prompt = f"""请分析以下文档文本，提取完整的目录结构：

{full_text[:20000]}  # 限制文本长度避免超过token限制

请使用推理模式仔细分析文档结构，识别所有章节标题和层级关系。
"""
        
        try:
            # 调用qwen-plus推理模式
            response = self.client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=4000,
                temperature=0.1,
                # 启用推理模式
                extra_body={
                    "enable_reasoning": True,
                    "reasoning_effort": "high"
                }
            )
            
            # 提取响应内容
            content = response.choices[0].message.content
            
            # 处理```json格式的响应
            if content.startswith('```json'):
                # 提取JSON部分
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    content = content[json_start:json_end]
            
            # 尝试解析JSON
            try:
                result = json.loads(content)
                toc_data = result.get('toc', [])
                
                # 转换为TOCItem对象
                toc_items = []
                for item in toc_data:
                    toc_item = TOCItem(
                        title=item.get('title', ''),
                        level=item.get('level', 1),
                        start_text=item.get('start_text', ''),
                        page_number=item.get('page_number'),
                        id=item.get('id')
                    )
                    toc_items.append(toc_item)
                
                print(f"✅ TOC提取成功，共识别 {len(toc_items)} 个章节")
                
                # 显示提取结果
                for item in toc_items:
                    indent = "  " * (item.level - 1)
                    print(f"{indent}{item.level}. {item.title} (页码: {item.page_number})")
                
                return toc_items
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                print(f"🔍 原始响应: {content}")
                return []
                
        except Exception as e:
            print(f"❌ TOC提取失败: {e}")
            return []
    
    def save_toc_result(self, toc_items: List[TOCItem], output_path: str):
        """
        保存TOC提取结果
        
        Args:
            toc_items: TOC项目列表
            output_path: 输出文件路径
        """
        # 转换为可序列化的字典
        toc_data = []
        for item in toc_items:
            toc_data.append({
                "title": item.title,
                "level": item.level,
                "start_text": item.start_text,
                "page_number": item.page_number,
                "id": item.id,
                "parent_id": item.parent_id
            })
        
        result = {
            "toc": toc_data,
            "extraction_time": time.time(),
            "total_chapters": len(toc_items)
        }
        
        # 保存到文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"💾 TOC结果已保存到: {output_path}")

def main():
    """主函数"""
    # 输入文件路径
    basic_result_path = "parser_output/20250714_145102_zpdlfg/basic_processing_result.json"
    
    if not os.path.exists(basic_result_path):
        print(f"❌ 文件不存在: {basic_result_path}")
        return
    
    # 初始化TOC提取器
    extractor = TOCExtractor()
    
    # 缝合完整文本
    full_text = extractor.stitch_full_text(basic_result_path)
    
    # 保存缝合后的文本用于调试
    debug_path = "parser_output/20250714_145102_zpdlfg/full_text_debug.txt"
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
    print(f"🐛 调试文本已保存到: {debug_path}")
    
    # 提取TOC
    toc_items = extractor.extract_toc_with_reasoning(full_text)
    
    # 保存TOC结果
    if toc_items:
        output_path = "parser_output/20250714_145102_zpdlfg/toc_extraction_result.json"
        extractor.save_toc_result(toc_items, output_path)
        print(f"🎉 TOC提取完成! 结果保存在: {output_path}")
    else:
        print("❌ TOC提取失败，未能识别章节结构")

if __name__ == "__main__":
    main() 