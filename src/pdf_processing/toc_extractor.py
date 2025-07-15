#!/usr/bin/env python3
"""
TOC提取器 - 生产版本
使用统一的QwenClient进行API调用
基于AI推理模式提取文档目录结构
"""

import json
import os
import sys
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.qwen_client import QwenClient

@dataclass
class TOCItem:
    """TOC条目数据结构"""
    title: str
    level: int
    start_text: str  # 用于匹配的开头文本
    id: str
    parent_id: Optional[str] = None

class TOCExtractor:
    """TOC提取器 - 使用统一的QwenClient"""
    
    def __init__(self, model: str = "qwen-plus"):
        """
        初始化TOC提取器
        
        Args:
            model: 使用的模型名称
        """
        self.client = QwenClient(
            model=model,
            temperature=0.1,
            max_retries=3
        )
        self.model = model
    
    def stitch_full_text(self, basic_result_path: str) -> str:
        """
        拼接完整文本，保持页面顺序
        
        Args:
            basic_result_path: 基础解析结果文件路径
            
        Returns:
            str: 拼接后的完整文本
        """
        if not os.path.exists(basic_result_path):
            raise FileNotFoundError(f"基础解析结果文件不存在: {basic_result_path}")
        
        with open(basic_result_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        pages = data.get('pages', [])
        full_text_parts = []
        
        # 全局计数器，用于生成唯一ID
        global_image_counter = 0
        global_table_counter = 0
        
        for page in pages:
            cleaned_text = page.get('cleaned_text', '') or ''
            images = page.get('images', [])
            tables = page.get('tables', [])
            
            # 添加页面文本
            if cleaned_text and cleaned_text.strip():
                full_text_parts.append(cleaned_text.strip())
            
            # 添加图片描述（包含唯一标识符）
            for image in images:
                global_image_counter += 1
                description = image.get('ai_description', '图片描述') or '图片描述'
                image_path = image.get('image_path', '')
                # 格式：[图片|ID:xxx|PATH:xxx: 描述]
                full_text_parts.append(f"[图片|ID:{global_image_counter}|PATH:{image_path}: {description}]")
            
            # 添加表格描述（包含唯一标识符）
            for table in tables:
                global_table_counter += 1
                description = table.get('ai_description', '表格描述') or '表格描述'
                table_path = table.get('table_path', '')
                # 格式：[表格|ID:xxx|PATH:xxx: 描述]
                full_text_parts.append(f"[表格|ID:{global_table_counter}|PATH:{table_path}: {description}]")
        
        # 用双换行连接，保持段落分隔
        full_text = "\n\n".join(full_text_parts)
        
        print(f"✅ 文本缝合完成，总长度: {len(full_text)} 字符")
        print(f"📄 总页数: {len(pages)}")
        print(f"🖼️ 包含图片: {global_image_counter} 个")
        print(f"📊 包含表格: {global_table_counter} 个")
        
        return full_text
    
    def extract_toc_with_reasoning(self, full_text: str) -> Tuple[List[TOCItem], str]:
        """
        使用AI推理模式提取TOC
        
        Args:
            full_text: 完整文档文本
            
        Returns:
            Tuple[List[TOCItem], str]: TOC项目列表和推理内容
        """
        print("🧠 开始使用AI推理模式提取TOC...")
        
        # 系统提示
        system_prompt = """你是一个专业的文档结构分析师。请分析文档文本，提取完整的目录结构(TOC)。

要求：
1. 识别所有层级的章节标题（一级、二级、三级等）
2. 为每个章节提供用于匹配的开头文本片段（20-40个字符）
3. 分析章节的层级关系，正确设置parent_id
4. 使用数字ID格式（1, 2, 3等）

返回JSON格式：
{
  "toc": [
    {
      "title": "章节标题",
      "level": 1,
      "start_text": "章节开头的文本片段，用于精确匹配",
      "id": "1",
      "parent_id": null
    },
    {
      "title": "子章节标题",
      "level": 2,
      "start_text": "子章节开头的文本片段",
      "id": "2",
      "parent_id": "1"
    }
  ]
}

注意：
- level从1开始（1=一级标题，2=二级标题，以此类推）
- start_text应该是章节标题后紧接着的文本，用于精确匹配
- id使用简单的数字格式：1, 2, 3, 4等
- parent_id指向上级章节的id，一级章节的parent_id为null
- 确保层级关系正确，二级章节的parent_id应该指向其所属的一级章节
"""
        
        # 用户提示
        user_prompt = f"""请仔细分析以下文档文本，提取完整的目录结构。

请使用推理模式分析文档结构，识别所有章节标题和层级关系：

{full_text}

请严格按照JSON格式返回结果，确保所有字段都正确填写。
"""
        
        try:
            print("🔄 正在调用AI推理模式...")
            
            # 使用统一的客户端进行API调用
            content, reasoning_content = self.client.generate_response_with_reasoning(
                prompt=user_prompt,
                system_prompt=system_prompt,
                enable_thinking=True,
                stream=True
            )
            
            print(f"\n✅ 推理内容收集完成，共 {len(reasoning_content)} 字符")
            print(f"📝 主要响应内容，共 {len(content)} 字符")
            
            # 处理JSON响应
            if content.startswith('```json'):
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    content = content[json_start:json_end]
            
            # 解析JSON
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
                        id=str(item.get('id', '')),
                        parent_id=item.get('parent_id')
                    )
                    toc_items.append(toc_item)
                
                print(f"✅ TOC提取成功，共识别 {len(toc_items)} 个章节")
                
                # 显示提取结果
                for item in toc_items:
                    indent = "  " * (item.level - 1)
                    parent_info = f" (父级: {item.parent_id})" if item.parent_id else ""
                    print(f"{indent}{item.level}. {item.title}{parent_info}")
                
                return toc_items, reasoning_content
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                print(f"🔍 原始响应: {content}")
                return [], reasoning_content
                
        except Exception as e:
            print(f"❌ API调用失败: {e}")
            return [], ""
    
    def save_toc_result(self, toc_items: List[TOCItem], reasoning_content: str, output_path: str):
        """
        保存TOC提取结果
        
        Args:
            toc_items: TOC项目列表
            reasoning_content: 推理内容
            output_path: 输出文件路径
        """
        # 转换为字典格式
        toc_dict = {
            "toc": [
                {
                    "title": item.title,
                    "level": item.level,
                    "start_text": item.start_text,
                    "id": item.id,
                    "parent_id": item.parent_id
                }
                for item in toc_items
            ],
            "extraction_time": time.time(),
            "total_chapters": len(toc_items),
            "reasoning_content": reasoning_content,
            "model_used": self.model
        }
        
        # 保存结果
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(toc_dict, f, ensure_ascii=False, indent=2)
        
        print(f"📁 TOC结果已保存到: {output_path}")
    
    def save_full_text_debug(self, full_text: str, output_path: str):
        """
        保存完整文本用于调试
        
        Args:
            full_text: 完整文本
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        print(f"📝 完整文本已保存到: {output_path}")
    
    def print_client_stats(self):
        """打印客户端统计信息"""
        print("\n📊 API调用统计:")
        self.client.print_stats()

def main():
    """主函数"""
    # 输入文件路径
    input_file = "parser_output/20250714_232720_vvmpc0/basic_processing_result.json"
    
    if not os.path.exists(input_file):
        print(f"❌ 输入文件不存在: {input_file}")
        return
    
    # 创建提取器
    extractor = TOCExtractor()
    
    # 缝合完整文本
    full_text = extractor.stitch_full_text(input_file)
    
    # 保存完整文本用于调试
    output_dir = os.path.dirname(input_file)
    full_text_path = os.path.join(output_dir, "full_text.txt")
    extractor.save_full_text_debug(full_text, full_text_path)
    
    # 提取TOC
    toc_items, reasoning_content = extractor.extract_toc_with_reasoning(full_text)
    
    # 输出推理内容
    if reasoning_content:
        print("\n" + "="*50)
        print("🧠 AI推理内容:")
        print("="*50)
        print(reasoning_content)
        print("="*50)
    
    # 保存结果
    if toc_items:
        result_path = os.path.join(output_dir, "toc_extraction_result.json")
        extractor.save_toc_result(toc_items, reasoning_content, result_path)
        print(f"\n🎉 TOC提取完成! 结果保存在: {result_path}")
    else:
        print("❌ TOC提取失败")
    
    # 打印统计信息
    extractor.print_client_stats()

if __name__ == "__main__":
    main() 