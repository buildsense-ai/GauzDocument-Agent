#!/usr/bin/env python3
"""
TOC提取器 V2 - 改进版本
解决页码噪音、章节ID和parent_id逻辑问题
使用qwen_plus thinking模式提取文档目录结构
"""

import json
import os
import sys
import time
from typing import Dict, List, Any, Optional, Tuple
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
    id: str
    parent_id: Optional[str] = None

class TOCExtractorV2:
    """TOC提取器 V2"""
    
    def __init__(self, model: str = "qwen-plus"):
        """
        初始化TOC提取器
        
        Args:
            model: 使用的模型名称
        """
        self.client = OpenAI(
            api_key=os.getenv("QWEN_API_KEY"),
            base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        )
        self.model = model
        
        if not self.client.api_key:
            raise ValueError("未找到API密钥，请设置QWEN_API_KEY环境变量")
    
    def stitch_full_text(self, basic_result_path: str) -> str:
        """
        缝合完整文本（不包含页码标记）
        
        Args:
            basic_result_path: 基础处理结果文件路径
            
        Returns:
            str: 缝合后的完整文本
        """
        print("🧵 开始缝合full_text...")
        
        # 读取基础处理结果
        with open(basic_result_path, 'r', encoding='utf-8') as f:
            basic_result = json.load(f)
        
        # 提取页面数据
        pages = basic_result.get('pages', [])
        if not pages:
            raise ValueError("未找到页面数据")
        
        # 按页码排序
        pages.sort(key=lambda x: x.get('page_number', 0))
        
        # 缝合文本（不包含页码标记）
        full_text_parts = []
        
        for page in pages:
            page_num = page.get('page_number', 0)
            cleaned_text = page.get('cleaned_text', '')
            images = page.get('images', [])
            tables = page.get('tables', [])
            
            # 添加页面文本（不添加页码标记）
            if cleaned_text.strip():
                full_text_parts.append(cleaned_text.strip())
            
            # 添加图片信息
            for i, image in enumerate(images, 1):
                description = image.get('ai_description', '图片描述')
                full_text_parts.append(f"[图片: {description}]")
            
            # 添加表格信息
            for i, table in enumerate(tables, 1):
                description = table.get('ai_description', '表格描述')
                full_text_parts.append(f"[表格: {description}]")
        
        # 用双换行连接，保持段落分隔
        full_text = "\n\n".join(full_text_parts)
        
        print(f"✅ 文本缝合完成，总长度: {len(full_text)} 字符")
        print(f"📄 总页数: {len(pages)}")
        
        return full_text
    
    def extract_toc_with_qwen_plus(self, full_text: str) -> Tuple[List[TOCItem], str]:
        """
        使用qwen_plus推理模式提取TOC
        
        Args:
            full_text: 完整文档文本
            
        Returns:
            Tuple[List[TOCItem], str]: TOC项目列表和thinking内容
        """
        print("🧠 开始使用qwen_plus推理模式提取TOC...")
        
        # 构建系统提示
        system_prompt = """你是一个专业的文档结构分析师。请分析给定的文档文本，提取完整的目录结构(TOC)。

要求：
1. 识别所有层级的章节标题（一级、二级、三级等）
2. 为每个章节提供用于匹配的开头文本片段（20-40个字符）
3. 分析章节的层级关系，正确设置parent_id
4. 使用数字ID格式（1, 2, 3等）

请以JSON格式返回结果，格式如下：
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
        
        # 不限制文本长度，让AI完整分析
        # limited_text = full_text[:50000] if len(full_text) > 50000 else full_text
        
        # 构建用户提示
        user_prompt = f"""请仔细分析以下文档文本，提取完整的目录结构。

请使用推理模式分析文档结构，识别所有章节标题和层级关系：

{full_text}

请严格按照JSON格式返回结果，确保所有字段都正确填写。
"""
        
        try:
            # 使用流式输出和thinking模式
            print("🔄 正在调用qwen-plus推理模式...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                stream=True,  # 启用流式输出
                extra_body={
                    "enable_thinking": True  # 启用推理模式
                }
            )
            
            # 收集响应内容和推理内容
            content_chunks = []
            reasoning_chunks = []
            
            print("🧠 正在接收推理内容...")
            
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    
                    # 收集主要内容
                    if hasattr(delta, 'content') and delta.content:
                        content_chunks.append(delta.content)
                    
                    # 收集推理内容
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        reasoning_chunks.append(delta.reasoning_content)
                        print(delta.reasoning_content, end='', flush=True)
            
            # 合并内容
            content = ''.join(content_chunks)
            reasoning_content = ''.join(reasoning_chunks)
            
            print(f"\n✅ 推理内容收集完成，共 {len(reasoning_content)} 字符")
            print(f"📝 主要响应内容，共 {len(content)} 字符")
            
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
        保存TOC结果
        
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
            "reasoning_content": reasoning_content  # 保存推理内容
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

def main():
    """主函数"""
    # 输入文件路径
    input_file = "parser_output/20250714_145102_zpdlfg/basic_processing_result.json"
    
    if not os.path.exists(input_file):
        print(f"❌ 输入文件不存在: {input_file}")
        return
    
    # 创建提取器
    extractor = TOCExtractorV2()
    
    # 缝合完整文本
    full_text = extractor.stitch_full_text(input_file)
    
    # 保存完整文本用于调试
    output_dir = os.path.dirname(input_file)
    full_text_path = os.path.join(output_dir, "full_text_v2.txt")
    extractor.save_full_text_debug(full_text, full_text_path)
    
    # 提取TOC
    toc_items, reasoning_content = extractor.extract_toc_with_qwen_plus(full_text)
    
    # 输出推理内容
    if reasoning_content:
        print("\n" + "="*50)
        print("🧠 QWEN_PLUS 推理内容:")
        print("="*50)
        print(reasoning_content)
        print("="*50)
    
    # 保存结果
    if toc_items:
        result_path = os.path.join(output_dir, "toc_extraction_result_v2.json")
        extractor.save_toc_result(toc_items, reasoning_content, result_path)
        print(f"\n🎉 TOC提取完成! 结果保存在: {result_path}")
    else:
        print("❌ TOC提取失败")

if __name__ == "__main__":
    main() 