#!/usr/bin/env python3
"""
Stage 2 Processor: 智能修复与重组处理器

实现"修复与重组"而非"创作与总结"的核心理念：
- Step 2.1: 局部修复 (Page-Level) - 修正OCR错误和格式问题
- Step 2.2: 全局结构识别 (Document-Level) - TOC提取和结构化
- Step 2.3: 内容提取与切分 (Chapter-Level) - 基于结构的智能分块
- Step 2.4: 多模态描述生成 (并行执行) - 图片表格AI描述

关键设计原则：
1. 修复而非创作 - 降低AI幻觉风险
2. 保留追溯性 - 原始+清理双版本
3. 结构优先 - 先理解骨架再分块
4. 并行友好 - 提升处理效率
"""

import os
import time
import json
import asyncio
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from .final_schema import FinalMetadataSchema

# 导入现有的AI客户端
try:
    from ..qwen_client import QwenClient
    QWEN_AVAILABLE = True
    print("✅ QwenClient可用")
except ImportError as e:
    QWEN_AVAILABLE = False
    print(f"⚠️ QwenClient不可用: {e}")

try:
    from ..openrouter_client import OpenRouterClient
    OPENROUTER_AVAILABLE = True
    print("✅ OpenRouterClient可用")
except ImportError as e:
    OPENROUTER_AVAILABLE = False
    print(f"⚠️ OpenRouterClient不可用: {e}")

# 导入TOC提取器和分块组件
try:
    from ..pdf_processing.toc_extractor import TOCExtractor
    from ..pdf_processing.ai_chunker import AIChunker
    TOC_EXTRACTOR_AVAILABLE = True
    print("✅ TOCExtractor可用")
except ImportError as e:
    TOC_EXTRACTOR_AVAILABLE = False
    print(f"⚠️ TOCExtractor不可用: {e}")


class Stage2IntelligentProcessor:
    """
    Stage2智能处理器：修复与重组
    实现"修复而非创作"的处理逻辑
    """
    
    def __init__(self):
        """初始化Stage2处理器"""
        
        # 初始化AI客户端
        self.ai_clients = {}
        self._initialize_ai_clients()
        
        # 工作目录
        self.base_output_dir = Path("parser_output_v2")
        
        # 优化的文本清洗prompt - 平衡版本
        self.text_cleaning_prompt = """请修复以下OCR识别文本中的错误，但不要改变原意或添加新内容。

要求：
1. **只修复明显的OCR错误**：错别字、乱码、分词问题
2. **整理格式问题**：删除多余空行、修正空格分布、整理段落间距、修正标点位置
3. **保持原文结构**：不要重写、总结或扩展内容
4. **保持专业术语**：工程、建筑、法规术语要准确

原文：{original_text}

修复后的文本："""

        # 图片描述prompt - 结构化输出
        self.image_description_prompt = """请分析这张图片并以JSON格式输出结构化描述。

图片上下文：{page_context}

请按以下JSON格式输出（直接返回JSON，不要用markdown代码块包装）：
{{
  "search_summary": "简述 - 15字以内的关键词描述，突出图片类型和核心内容",
  "detailed_description": "详细描述图片的具体内容、布局、文字等元素",
  "engineering_details": "如果是技术图纸、设计图或工程图，请描述关键技术信息、尺寸、规格等专业细节；如果不是技术图纸，则返回null"
}}

要求：
- search_summary要精炼，适合搜索匹配
- detailed_description要完整准确
- engineering_details仅针对技术图纸，普通图片返回null
- 输出必须是有效的JSON格式，直接返回JSON对象，不要用```json```包装"""

        # 表格描述prompt - 结构化输出
        self.table_description_prompt = """请分析这张表格并以JSON格式输出结构化描述。

表格上下文：{page_context}

请按以下JSON格式输出（直接返回JSON，不要用markdown代码块包装）：
{{
  "search_summary": "简述 - 15字以内的关键词描述，突出表格类型和核心内容",
  "detailed_description": "详细描述表格的具体内容、布局、文字等元素",
  "engineering_details": "如果是技术图表、设计图或工程图，请描述关键技术信息、尺寸、规格等专业细节；如果不是技术图表，则返回null"
}}

要求：
- search_summary要精炼，适合搜索匹配
- detailed_description要完整准确
- engineering_details仅针对技术图表，普通表格返回null
- 输出必须是有效的JSON格式，直接返回JSON对象，不要用```json```包装"""

        # 处理统计
        self.stats = {
            "pages_repaired": 0,
            "images_described": 0,
            "tables_described": 0,
            "toc_extracted": False
        }
        
        print("🔧 Stage2处理器初始化完成")
        print(f"📁 输出目录: {self.base_output_dir}")
        print(f"🤖 可用AI客户端: {list(self.ai_clients.keys())}")

    def _initialize_ai_clients(self):
        """初始化AI客户端 - 使用现有的QwenClient和OpenRouterClient"""
        print("🔧 初始化AI客户端...")
        
        # 初始化Qwen客户端（用于文本清洗）
        if QWEN_AVAILABLE:
            try:
                self.ai_clients['qwen'] = QwenClient(
                    model="qwen-turbo-latest",
                    max_tokens=2000,
                    temperature=0.1,
                    max_retries=3,
                    enable_batch_mode=True
                )
                print("✅ Qwen客户端初始化成功（用于文本清洗）")
            except Exception as e:
                print(f"⚠️ Qwen客户端初始化失败: {e}")
        
        # 初始化OpenRouter客户端（用于多模态处理）
        if OPENROUTER_AVAILABLE:
            try:
                self.ai_clients['openrouter'] = OpenRouterClient()
                print("✅ OpenRouter客户端初始化成功（用于多模态处理）")
            except Exception as e:
                print(f"⚠️ OpenRouter客户端初始化失败: {e}")
        
        if not self.ai_clients:
            print("❌ 警告: 没有可用的AI客户端，Stage2功能将受限")
            print("💡 请检查环境变量 QWEN_API_KEY 和 OPENROUTER_API_KEY")

    def _initialize_prompts(self):
        """初始化各种处理提示词"""
        print("📝 初始化处理提示词...")
        
        # 文本清洗prompt - 平衡版本
        self.text_cleaning_prompt = """请修复以下OCR识别文本中的错误，但不要改变原意或添加新内容。

要求：
1. **只修复明显的OCR错误**：错别字、乱码、分词问题
2. **整理格式问题**：删除多余空行、修正空格分布、整理段落间距、修正标点位置
3. **保持原文结构**：不要重写、总结或扩展内容
4. **保持专业术语**：工程、建筑、法规术语要准确

原文：{original_text}

修复后的文本："""

        # 图片描述prompt - 结构化输出
        self.image_description_prompt = """请分析这张图片并以JSON格式输出结构化描述。

图片上下文：{page_context}

请按以下JSON格式输出（直接返回JSON，不要用markdown代码块包装）：
{{
  "search_summary": "简述 - 15字以内的关键词描述，突出图片类型和核心内容",
  "detailed_description": "详细描述图片的具体内容、布局、文字等元素",
  "engineering_details": "如果是技术图纸、设计图或工程图，请描述关键技术信息、尺寸、规格等专业细节；如果不是技术图纸，则返回null"
}}

要求：
- search_summary要精炼，适合搜索匹配
- detailed_description要完整准确
- engineering_details仅针对技术图纸，普通图片返回null
- 输出必须是有效的JSON格式，直接返回JSON对象，不要用```json```包装"""

        # 表格描述prompt - 结构化输出
        self.table_description_prompt = """请分析这张表格并以JSON格式输出结构化描述。

表格上下文：{page_context}

请按以下JSON格式输出（直接返回JSON，不要用markdown代码块包装）：
{{
  "search_summary": "简述 - 15字以内的关键词描述，突出表格类型和核心内容",
  "detailed_description": "详细描述表格的具体内容、布局、文字等元素",
  "engineering_details": "如果是技术图表、设计图或工程图，请描述关键技术信息、尺寸、规格等专业细节；如果不是技术图表，则返回null"
}}

要求：
- search_summary要精炼，适合搜索匹配
- detailed_description要完整准确
- engineering_details仅针对技术图表，普通表格返回null
- 输出必须是有效的JSON格式，直接返回JSON对象，不要用```json```包装"""

    def process(self, input_path: str, output_dir: Optional[str] = None) -> str:
        """
        执行Stage2智能处理
        注意：直接更新input_path的metadata文件，不创建新文件
        """
        print(f"🚀 开始Stage2智能处理...")
        print(f"📂 输入路径: {input_path}")
        
        start_time = time.time()
        
        try:
            # 1. 加载Stage1数据
            print("📖 加载Stage1处理结果...")
            final_schema = self._load_stage1_data(input_path)
            
            # 2. Step 2.1: 页面文本修复
            print("🔧 Step 2.1: 执行页面文本修复...")
            self._process_step_2_1_text_repair(final_schema)
            
            # 3. Step 2.2: 全局结构识别 (TOC提取和结构化)
            print("🔗 Step 2.2: 执行全局结构识别...")
            self._process_step_2_2_toc_extraction(final_schema)
            
            # 4. Step 2.3: 内容提取与切分 (Chapter-Level)
            print("🧠 Step 2.3: 执行内容提取与切分...")
            self._process_step_2_3_content_chunking(final_schema)
            
            # 5. Step 2.4: 多模态描述生成 (暂跳过Step 2.2和2.3)
            print("🖼️  Step 2.4: 执行多模态描述生成...")
            self._process_step_2_4_multimodal(final_schema)
            
            # 6. 更新处理状态
            final_schema.processing_status.current_stage = "stage2_completed"
            final_schema.processing_status.completion_percentage = 60
            final_schema.processing_status.last_updated = datetime.now()
            
            # 7. 保存更新后的数据 - 直接覆盖原文件
            output_path = self._save_updated_metadata(final_schema, input_path)
            
            # 8. 统计与报告
            processing_time = time.time() - start_time
            self._print_processing_report(final_schema, processing_time)
            
            print(f"✅ Stage2处理完成! 用时: {processing_time:.2f}秒")
            print(f"📄 更新文件: {output_path}")
            
            return output_path
            
        except Exception as e:
            print(f"❌ Stage2处理失败: {str(e)}")
            raise
    
    def _save_updated_metadata(self, final_schema: FinalMetadataSchema, original_path: str) -> str:
        """
        保存更新后的metadata - 直接更新原文件
        """
        # 确定metadata文件路径
        original_path_obj = Path(original_path)
        
        if original_path_obj.is_file() and original_path_obj.name.endswith('.json'):
            # 输入是json文件，直接更新
            metadata_path = original_path_obj
        else:
            # 输入是目录，查找其中的final_metadata.json
            metadata_path = original_path_obj / "final_metadata.json"
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"找不到metadata文件: {metadata_path}")
        
        print(f"💾 更新metadata文件: {metadata_path}")
        
        # 保存更新后的数据
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(final_schema.to_dict(), f, ensure_ascii=False, indent=2)
        
        return str(metadata_path)
    
    def _process_step_2_1_text_repair(self, final_schema: FinalMetadataSchema):
        """Step 2.1: 页面文本修复 - 并行处理"""
        print("📝 开始页面级文本修复...")
        
        page_texts = final_schema.document_summary.page_texts if final_schema.document_summary else None
        if not page_texts:
            print("⚠️ 没有页面文本数据，跳过局部修复")
            return
        
        # 如果有Qwen客户端，进行文本修复 - 并行处理
        if self.ai_clients.get('qwen'):
            print(f"🚀 并行修复{len(page_texts)}页文本...")
            cleaned_texts = self._repair_pages_parallel(page_texts)
        else:
            print("⚠️ 无可用Qwen客户端，跳过文本修复")
            cleaned_texts = page_texts.copy()
        
        # 更新schema
        if final_schema.document_summary and final_schema.document_summary.cleaned_page_texts is None:
            final_schema.document_summary.cleaned_page_texts = {}
        if final_schema.document_summary and final_schema.document_summary.cleaned_page_texts is not None:
            final_schema.document_summary.cleaned_page_texts.update(cleaned_texts)
        print(f"✅ 页面修复完成，处理了{len(cleaned_texts)}页")
    
    def _repair_pages_parallel(self, page_texts: dict, max_workers: int = 5) -> dict:
        """并行修复页面文本"""
        cleaned_texts = {}
        
        def repair_single_page(page_item):
            page_num, raw_text = page_item
            try:
                print(f"🔧 修复第{page_num}页...")
                cleaned_text = self._clean_page_text(raw_text)
                return page_num, cleaned_text, True
            except Exception as e:
                print(f"⚠️ 第{page_num}页修复失败: {e}")
                return page_num, raw_text, False
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_page = {
                executor.submit(repair_single_page, item): item[0] 
                for item in page_texts.items()
            }
            
            # 收集结果
            for future in as_completed(future_to_page):
                page_num, cleaned_text, success = future.result()
                cleaned_texts[page_num] = cleaned_text
                if success:
                    self.stats["pages_repaired"] += 1
        
        print(f"✅ 并行修复完成: {self.stats['pages_repaired']}/{len(page_texts)}页成功")
        return cleaned_texts
    
    def _process_step_2_2_toc_extraction(self, final_schema: FinalMetadataSchema):
        """
        Step 2.2: 全局结构识别 (Document-Level)
        基于修复后的文本提取TOC结构
        """
        print("🗺️ 开始全局结构识别...")
        
        if not TOC_EXTRACTOR_AVAILABLE:
            print("⚠️ TOC提取器不可用，跳过结构识别")
            return
        
        # 1. 拼接完整的清理后文本
        full_cleaned_text = self._stitch_cleaned_full_text(final_schema)
        if not full_cleaned_text:
            print("⚠️ 无法获取清理后的完整文本，跳过TOC提取")
            return
        
        # 2. 使用TOC提取器
        try:
            toc_extractor = TOCExtractor(model="qwen-plus")
            toc_items, reasoning_content = toc_extractor.extract_toc_with_reasoning(full_cleaned_text)
            
            if toc_items:
                # 3. 直接存储到document_summary.toc
                # 转换TOCItem为字典格式
                toc_dict = []
                for item in toc_items:
                    toc_dict.append({
                        "title": item.title,
                        "level": item.level,
                        "start_text": item.start_text,
                        "chapter_id": f"chapter_{item.id}",
                        "id": item.id,
                        "parent_id": item.parent_id
                    })
                
                # 直接存储TOC到document_summary.toc
                if final_schema.document_summary:
                    final_schema.document_summary.toc = toc_dict
                self.stats["toc_extracted"] = True
                
                print(f"✅ TOC提取成功，共识别 {len(toc_items)} 个章节")
                
                # 显示提取结果
                for item in toc_items:
                    indent = "  " * (item.level - 1)
                    print(f"{indent}{item.level}. {item.title}")
                    
            else:
                print("⚠️ TOC提取失败，未识别到章节结构")
                
        except Exception as e:
            print(f"❌ TOC提取过程失败: {e}")
    
    def _process_step_2_3_content_chunking(self, final_schema: FinalMetadataSchema):
        """
        Step 2.3: 内容提取与切分 (Chapter-Level)
        """
        print("\n" + "="*50)
        print("🔀 开始 Step 2.3: 内容提取与切分")
        print("="*50)
        
        try:
            # 获取TOC数据
            if not final_schema.document_summary or not final_schema.document_summary.toc:
                print("⚠️ 没有TOC数据，跳过章节切分")
                return
            
            toc_data = final_schema.document_summary.toc
            
            # 1. 生成完整的清理文本
            cleaned_full_text = self._generate_cleaned_full_text(final_schema)
            if not cleaned_full_text:
                print("⚠️ 无法获取清理后的完整文本，跳过章节切分")
                return
                
            print(f"📄 生成完整文本: {len(cleaned_full_text)} 字符")
            
            # 2. 基于TOC切分主要章节
            chapters = self._cut_chapters_by_toc_simple(cleaned_full_text, toc_data)
            
            if not chapters:
                print("⚠️ 章节切分失败，没有生成有效章节")
                return
                
            print(f"✅ 章节切分完成: {len(chapters)}个章节")
            
            # 3. 创建ChapterSummary对象（暂时只有原始内容）
            chapter_summaries = self._create_chapter_summaries(chapters, final_schema.document_id)
            final_schema.chapter_summaries = chapter_summaries
            
            # 4. 使用 AI Chunker 进行细粒度分块
            if TOC_EXTRACTOR_AVAILABLE:  # AI chunker 和 TOC extractor 在同一个模块中
                print("🤖 开始使用 AI Chunker 进行细粒度分块...")
                text_chunks = self._perform_ai_chunking(chapters, final_schema.document_id)
                final_schema.text_chunks = text_chunks
                print(f"🔤 AI Chunking 完成: {len(text_chunks)}个细粒度分块")
            else:
                print("⚠️ AI Chunker 不可用，创建简化文本块")
                text_chunks = self._create_text_chunks_for_embedding(chapters, final_schema.document_id)
                final_schema.text_chunks = text_chunks
            
            # 5. 更新 table 和 image 的 chapter_id 信息
            print("🔗 更新图片和表格的章节关联...")
            self._update_multimodal_chapter_mapping(final_schema, chapters)
            
            # 6. 生成章节总结
            print("📝 生成章节总结...")
            self._generate_chapter_summaries(final_schema)
            
            print(f"📊 最终结果:")
            print(f"   📖 章节摘要: {len(chapter_summaries)}个")
            print(f"   🔤 文本块: {len(text_chunks)}个")
            
            # 显示切分结果
            for i, chapter in enumerate(chapters):
                print(f"   📖 章节{i+1}: {chapter['title']} ({chapter['word_count']}字符)")
            
        except Exception as e:
            print(f"❌ 章节切分过程失败: {e}")
            import traceback
            traceback.print_exc()
            
    def _generate_cleaned_full_text(self, final_schema: FinalMetadataSchema) -> str:
        """
        从cleaned_page_texts生成完整的清理文本
        """
        if not final_schema.document_summary or not final_schema.document_summary.cleaned_page_texts:
            print("⚠️ 没有cleaned_page_texts数据")
            return ""
            
        cleaned_page_texts = final_schema.document_summary.cleaned_page_texts
        
        # 按页码排序并连接
        page_numbers = sorted([int(k) for k in cleaned_page_texts.keys() if k.isdigit()])
        pages = []
        
        for page_num in page_numbers:
            page_text = cleaned_page_texts.get(str(page_num), "")
            if page_text and page_text.strip():
                pages.append(page_text.strip())
        
        # 用双换行连接各页
        cleaned_full_text = "\n\n".join(pages)
        print(f"📖 缝合完成: {len(pages)}页 → {len(cleaned_full_text)}字符")
        
        return cleaned_full_text
        
    def _cut_chapters_by_toc_simple(self, full_text: str, toc_data: List[Dict]) -> List[Dict]:
        """
        基于TOC简单切分章节 - 只处理level=1的主要章节
        """
        import re
        
        chapters = []
        
        # 只处理第一级章节
        first_level_toc = [item for item in toc_data if item.get('level') == 1]
        
        # 过滤出主要章节（包含"篇章"关键词的）
        major_chapters = []
        for item in first_level_toc:
            title = item.get('title', '')
            # 只保留包含"篇章"的真正主章节
            if '篇章' in title:
                major_chapters.append(item)
        
        print(f"🔍 找到主要章节: {[item.get('title') for item in major_chapters]}")
        
        for i, toc_item in enumerate(major_chapters):
            chapter_id = toc_item.get('chapter_id', f"chapter_{i+1}")
            title = toc_item.get('title', f"第{i+1}章")
            start_text = toc_item.get('start_text', '')
            
            # 查找章节开始位置
            start_pos = self._find_chapter_position(full_text, start_text, title)
            if start_pos == -1:
                print(f"⚠️ 无法找到章节 '{title}' 的开始位置")
                continue
                
            # 确定章节结束位置
            if i + 1 < len(major_chapters):
                next_start_text = major_chapters[i + 1].get('start_text', '')
                next_title = major_chapters[i + 1].get('title', '')
                end_pos = self._find_chapter_position(full_text, next_start_text, next_title)
                if end_pos == -1:
                    end_pos = len(full_text)
            else:
                end_pos = len(full_text)
            
            # 提取章节内容
            content = full_text[start_pos:end_pos].strip()
            
            chapter = {
                "chapter_id": chapter_id,
                "title": title,
                "content": content,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "word_count": len(content),
                "order": i + 1
            }
            
            chapters.append(chapter)
            print(f"✅ 章节切分: {title} ({len(content)} 字符)")
        
        return chapters
    
    def _find_chapter_position(self, full_text: str, start_text: str, title: str = "") -> int:
        """
        在全文中查找章节位置 - 必须使用start_text避免匹配到目录
        """
        import re
        
        # 1. 必须优先使用start_text，因为title会在目录中重复出现
        if start_text:
            # 去除多余空格，但保持基本结构
            cleaned_start = re.sub(r'\s+', ' ', start_text.strip())
            
            # 精确匹配
            pos = full_text.find(cleaned_start)
            if pos != -1:
                print(f"✅ 精确匹配start_text: {cleaned_start[:30]}...")
                return pos
            
            # 模糊匹配：允许空格和换行的变化
            if len(cleaned_start) > 10:
                # 将空格替换为正则模式，允许多个空格/换行
                pattern = re.escape(cleaned_start).replace(r'\ ', r'\s+')
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    print(f"✅ 模糊匹配start_text: {pattern[:30]}...")
                    return match.start()
            
            # 如果start_text太长，尝试用前半部分匹配
            if len(cleaned_start) > 20:
                first_half = cleaned_start[:len(cleaned_start)//2]
                pattern = re.escape(first_half).replace(r'\ ', r'\s+')
                matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
                if matches:
                    # 如果有多个匹配，选择不在文档开头的（避免目录）
                    for match in matches:
                        if match.start() > 1000:  # 假设目录在前1000字符内
                            print(f"✅ 部分匹配start_text (跳过目录): {first_half[:20]}...")
                            return match.start()
                    # 如果都在开头，取最后一个
                    print(f"✅ 部分匹配start_text (最后一个): {first_half[:20]}...")
                    return matches[-1].start()
        
        # 2. 回退到标题匹配（但要避免目录）
        if title:
            clean_title = title.strip()
            matches = []
            start = 0
            while True:
                pos = full_text.find(clean_title, start)
                if pos == -1:
                    break
                matches.append(pos)
                start = pos + 1
            
            if matches:
                # 如果有多个匹配，选择不在文档开头的（避免目录）
                for pos in matches:
                    if pos > 1000:  # 假设目录在前1000字符内
                        print(f"✅ 标题匹配 (跳过目录): {clean_title}")
                        return pos
                # 如果都在开头，取最后一个
                print(f"✅ 标题匹配 (最后一个): {clean_title}")
                return matches[-1]
        
        print(f"❌ 无法定位章节: title='{title}', start_text='{start_text[:50]}...'")
        return -1
        
    def _create_text_chunks_for_embedding(self, chapters: List[Dict], document_id: str) -> List:
        """
        基于章节创建轻量级TextChunk对象用于embedding
        """
        from .final_schema import TextChunk
        
        text_chunks = []
        
        for i, chapter in enumerate(chapters):
            # 创建章节摘要而不是完整内容
            content_summary = f"章节: {chapter['title']}\n内容摘要: {chapter['content'][:200]}..." if len(chapter['content']) > 200 else f"章节: {chapter['title']}\n内容: {chapter['content']}"
            
            chunk = TextChunk(
                content_id=f"{chapter['chapter_id']}_summary",
                document_id=document_id,
                content=content_summary,
                chapter_id=chapter['chapter_id'],
                chunk_index=i + 1,
                word_count=len(content_summary)
            )
            text_chunks.append(chunk)
        
        return text_chunks
    
    def _create_chapter_summaries(self, chapters: List[Dict], document_id: str) -> List:
        """
        将章节数据转换为ChapterSummary对象
        """
        from .final_schema import ChapterSummary
        
        chapter_summaries = []
        
        for chapter in chapters:
            chapter_summary = ChapterSummary(
                content_id=f"{document_id}_{chapter['chapter_id']}",
                document_id=document_id,
                chapter_id=chapter['chapter_id'],
                chapter_title=chapter['title'],
                raw_content=chapter['content'],  # 存储完整章节内容
                word_count=chapter['word_count']
            )
            chapter_summaries.append(chapter_summary)
        
        return chapter_summaries
    
    def _create_chapter_text_chunks(self, chapters: List[Dict], document_id: str) -> List:
        """
        基于章节创建简化的TextChunk对象用于embedding
        注意：不存储完整内容，只存储摘要信息
        """
        from .final_schema import TextChunk
        
        text_chunks = []
        
        for chapter in chapters:
            # 创建章节摘要而不是完整内容
            content_summary = self._create_chapter_summary(chapter)
            
            chunk = TextChunk(
                content_id=f"{chapter['chapter_id']}_summary",
                document_id=document_id,
                content=content_summary,  # 存储摘要而不是完整内容
                chapter_id=chapter['chapter_id'],
                chunk_index=1,
                word_count=len(content_summary)
            )
            text_chunks.append(chunk)
        
        return text_chunks
    
    def _create_chapter_summary(self, chapter: Dict) -> str:
        """
        为章节创建简短摘要用于embedding
        """
        title = chapter.get('title', '未知章节')
        content = chapter.get('content', '')
        
        # 创建章节摘要（前200字符 + 标题）
        if len(content) > 200:
            summary = f"章节: {title}\n内容摘要: {content[:200]}..."
        else:
            summary = f"章节: {title}\n内容: {content}"
        
        return summary
    
    def _perform_ai_chunking(self, chapters: List[Dict], document_id: str) -> List:
        """
        使用 AI Chunker 对章节进行细粒度分块
        """
        from ..pdf_processing.ai_chunker import chunk_chapters_with_ai
        from .final_schema import TextChunk
        
        try:
            # 准备章节数据，格式化为 AI Chunker 需要的格式
            chunker_chapters = []
            for chapter in chapters:
                chunker_chapters.append({
                    'chapter_id': chapter['chapter_id'],
                    'title': chapter['title'],
                    'content': chapter['content']
                })
            
            # 调用 AI Chunker 进行批量分块（使用同步便捷函数）
            print(f"🚀 调用 AI Chunker 处理 {len(chunker_chapters)} 个章节...")
            minimal_chunks = chunk_chapters_with_ai(
                chunker_chapters, 
                model="qwen-turbo",
                max_workers=3
            )
            
            # 转换为 TextChunk 对象
            text_chunks = []
            for i, minimal_chunk in enumerate(minimal_chunks):
                text_chunk = TextChunk(
                    content_id=minimal_chunk.chunk_id,
                    document_id=document_id,
                    content=minimal_chunk.content,
                    chapter_id=minimal_chunk.belongs_to_chapter,
                    page_number=None,  # AI chunker 没有页码信息
                    chunk_index=i + 1,
                    word_count=minimal_chunk.word_count
                )
                text_chunks.append(text_chunk)
            
            print(f"✅ AI Chunking 成功，生成 {len(text_chunks)} 个智能分块")
            return text_chunks
            
        except Exception as e:
            print(f"❌ AI Chunking 失败: {e}")
            print("🔄 回退到简单分块策略...")
            # 回退到简单策略
            return self._create_text_chunks_for_embedding(chapters, document_id)
    
    def _update_multimodal_chapter_mapping(self, final_schema: FinalMetadataSchema, chapters: List[Dict]):
        """
        更新图片和表格的章节关联信息
        基于页码范围或内容匹配来确定图片/表格属于哪个章节
        """
        print("🔗 开始更新多模态内容的章节映射...")
        
        # 1. 更新图片的 chapter_id
        updated_images = 0
        for img_chunk in final_schema.image_chunks:
            if not img_chunk.chapter_id:  # 只更新未分配章节的图片
                chapter_id = self._find_matching_chapter_for_content(
                    img_chunk.page_number, 
                    img_chunk.page_context, 
                    chapters
                )
                if chapter_id:
                    img_chunk.chapter_id = chapter_id
                    updated_images += 1
        
        # 2. 更新表格的 chapter_id
        updated_tables = 0
        for table_chunk in final_schema.table_chunks:
            if not table_chunk.chapter_id:  # 只更新未分配章节的表格
                chapter_id = self._find_matching_chapter_for_content(
                    table_chunk.page_number,
                    table_chunk.page_context,
                    chapters
                )
                if chapter_id:
                    table_chunk.chapter_id = chapter_id
                    updated_tables += 1
        
        print(f"✅ 章节映射更新完成: {updated_images}张图片, {updated_tables}个表格")
    
    def _find_matching_chapter_for_content(self, page_number: int, page_context: str, chapters: List[Dict]) -> Optional[str]:
        """
        为多模态内容找到匹配的章节
        """
        if not chapters:
            return None
        
        # 策略1: 如果page_context中包含章节关键词，直接匹配
        if page_context:
            for chapter in chapters:
                chapter_title = chapter.get('title', '')
                # 检查章节标题的关键词是否出现在上下文中
                if chapter_title and len(chapter_title) > 3:
                    title_keywords = chapter_title.replace('篇章', '').strip()
                    if title_keywords and title_keywords in page_context:
                        print(f"📍 通过上下文匹配: {title_keywords} -> {chapter['chapter_id']}")
                        return chapter['chapter_id']
        
        # 策略2: 基于页码范围（简单启发式）
        # 假设章节按顺序分布在文档中
        if page_number > 0:
            # 根据页码比例分配章节
            total_pages = max(page_number, 10)  # 保守估计
            chapter_index = min(int((page_number - 1) / total_pages * len(chapters)), len(chapters) - 1)
            matched_chapter = chapters[chapter_index]
            print(f"📍 通过页码匹配: 第{page_number}页 -> {matched_chapter['chapter_id']}")
            return matched_chapter['chapter_id']
        
        # 策略3: 默认分配给第一个章节
        if chapters:
            return chapters[0]['chapter_id']
        
        return None
    
    def _generate_chapter_summaries(self, final_schema: FinalMetadataSchema):
        """
        生成章节总结，更新 ChapterSummary 的 ai_summary 字段
        """
        if not self.ai_clients.get('qwen'):
            print("⚠️ 无可用 Qwen 客户端，跳过章节总结生成")
            return
        
        print("📝 开始生成章节总结...")
        
        chapter_summary_prompt = """请为以下章节内容生成一个简洁的总结，突出关键信息和重点内容。

要求：
1. 总结应该是200-300字
2. 突出章节的核心内容和关键信息
3. 保持专业性，适合用于文档检索
4. 包含章节中的重要技术细节、数据或结论

章节标题：{chapter_title}

章节内容：
{chapter_content}

请生成简洁准确的章节总结："""
        
        qwen_client = self.ai_clients['qwen']
        updated_summaries = 0
        
        for chapter_summary in final_schema.chapter_summaries:
            if not chapter_summary.ai_summary and chapter_summary.raw_content:
                try:
                    print(f"📝 生成章节总结: {chapter_summary.chapter_title}")
                    
                    prompt = chapter_summary_prompt.format(
                        chapter_title=chapter_summary.chapter_title,
                        chapter_content=chapter_summary.raw_content[:2000]  # 限制长度避免超出token限制
                    )
                    
                    ai_summary = qwen_client.generate_response(prompt)
                    if ai_summary and ai_summary.strip():
                        chapter_summary.ai_summary = ai_summary.strip()
                        updated_summaries += 1
                        print(f"✅ 章节总结生成完成: {chapter_summary.chapter_title}")
                    
                except Exception as e:
                    print(f"⚠️ 章节总结生成失败 ({chapter_summary.chapter_title}): {e}")
        
        print(f"✅ 章节总结生成完成: {updated_summaries}/{len(final_schema.chapter_summaries)} 个成功")
    
    def _stitch_cleaned_full_text(self, final_schema: FinalMetadataSchema) -> str:
        """
        拼接清理后的完整文本，优先使用cleaned_page_texts，回退到原始page_texts
        """
        if not final_schema.document_summary:
            return ""
        
        # 优先使用清理后的文本
        if (final_schema.document_summary.cleaned_page_texts):
            page_texts = final_schema.document_summary.cleaned_page_texts
            print("✅ 使用清理后的页面文本")
        elif final_schema.document_summary.page_texts:
            page_texts = final_schema.document_summary.page_texts
            print("⚠️ 使用原始页面文本（清理版本不可用）")
        else:
            print("❌ 没有可用的页面文本")
            return ""
        
        # 按页码顺序拼接
        page_numbers = sorted([int(k) for k in page_texts.keys() if k.isdigit()])
        text_parts = []
        
        for page_num in page_numbers:
            page_text = page_texts.get(str(page_num), "")
            if page_text and page_text.strip():
                text_parts.append(page_text.strip())
        
        full_text = "\n\n".join(text_parts)
        print(f"📖 拼接完成，总长度: {len(full_text)} 字符，包含 {len(page_numbers)} 页")
        
        return full_text
    
    def _cut_chapters_by_toc(self, full_text: str, toc_data: List[Dict]) -> List[Dict]:
        """
        基于TOC数据切分章节内容（只处理主要篇章）
        """
        chapters = []
        
        # 只处理第一级章节，并过滤掉非主要章节
        first_level_toc = [item for item in toc_data if item.get('level') == 1]
        
        # 过滤出真正的主要章节（篇章一、篇章二、篇章三等）
        major_chapters = []
        for item in first_level_toc:
            title = item.get('title', '')
            if any(keyword in title for keyword in ['篇章', '章节', '第一章', '第二章', '第三章']):
                major_chapters.append(item)
        
        print(f"🔍 找到主要章节: {[item.get('title') for item in major_chapters]}")
        print(f"📏 全文总长度: {len(full_text)} 字符")
        
        for i, toc_item in enumerate(major_chapters):
            chapter_id = toc_item.get('chapter_id', f"chapter_{toc_item.get('id', i+1)}")
            title = toc_item.get('title', f"第{i+1}章")
            start_text = toc_item.get('start_text', '')
            
            # 查找章节开始位置
            start_pos = self._find_chapter_start_in_full_text(full_text, start_text, title)
            if start_pos == -1:
                print(f"⚠️ 无法找到章节 '{title}' 的开始位置")
                continue
                
            # 确定章节结束位置
            if i + 1 < len(major_chapters):
                next_start_text = major_chapters[i + 1].get('start_text', '')
                next_title = major_chapters[i + 1].get('title', '')
                end_pos = self._find_chapter_start_in_full_text(full_text, next_start_text, next_title)
                if end_pos == -1:
                    end_pos = len(full_text)
            else:
                end_pos = len(full_text)
            
            print(f"📍 章节 '{title}': 位置 {start_pos} -> {end_pos}")
            
            # 提取章节内容
            content = full_text[start_pos:end_pos].strip()
            
            # 显示内容预览
            preview = content[:100].replace('\n', ' ') if content else "(空内容)"
            print(f"📖 内容预览: {preview}...")
            
            chapter = {
                "chapter_id": chapter_id,
                "title": title,
                "content": content,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "word_count": len(content),
                "order": i + 1
            }
            
            chapters.append(chapter)
            print(f"✅ 章节切分: {title} ({len(content)} 字符)")
        
        return chapters
    
    def _find_chapter_start_in_full_text(self, full_text: str, start_text: str, title: str = "") -> int:
        """
        在完整文本中查找章节开始位置，优先使用start_text，回退到标题搜索
        """
        import re
        
        # 特殊处理主要篇章标题
        if title:
            # 直接搜索篇章标题关键词
            if "篇章一" in title or "项目资料" in title:
                # 搜索"项目背景"作为篇章一的开始
                patterns = [
                    r"项目背景[:：]",
                    r"## 项目背景",
                    r"项目背景及区位",
                    r"该项目位于广州市白云区"
                ]
                for pattern in patterns:
                    match = re.search(pattern, full_text)
                    if match:
                        print(f"✅ 找到篇章一开始位置，使用模式: {pattern}")
                        return match.start()
            
            elif "篇章二" in title or "方案" in title:
                # 搜索"篇章二"或相关方案内容
                patterns = [
                    r"篇章二",
                    r"工程名称[:：]",
                    r"鹤边一社社文体活动中心",
                    r"工程概况及依据"
                ]
                for pattern in patterns:
                    match = re.search(pattern, full_text)
                    if match:
                        print(f"✅ 找到篇章二开始位置，使用模式: {pattern}")
                        return match.start()
            
            elif "篇章三" in title or "总结" in title:
                # 搜索"总结"相关内容
                patterns = [
                    r"篇章三",
                    r"社会价值[:：]",
                    r"环境价值[:：]",
                    r"社区文体活动中心建筑已严重残损"
                ]
                for pattern in patterns:
                    match = re.search(pattern, full_text)
                    if match:
                        print(f"✅ 找到篇章三开始位置，使用模式: {pattern}")
                        return match.start()
        
        # 原有的start_text匹配逻辑
        if start_text:
            # 1. 尝试精确匹配start_text
            pos = full_text.find(start_text)
            if pos != -1:
                print(f"✅ 使用精确匹配找到章节: {start_text[:30]}...")
                return pos
            
            # 2. 尝试模糊匹配（去除空格和标点）
            cleaned_start = re.sub(r'[^\w\u4e00-\u9fff]', '', start_text)
            if len(cleaned_start) > 5:  # 至少5个有效字符
                pattern = '.*?'.join(re.escape(char) for char in cleaned_start[:10])  # 前10个字符
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    print(f"✅ 使用模糊匹配找到章节: {pattern}")
                    return match.start()
        
        # 3. 回退到标题搜索
        if title:
            # 清理标题，去除序号
            clean_title = re.sub(r'^[\d\.\s]*', '', title).strip()
            if len(clean_title) > 2:
                pos = full_text.find(clean_title)
                if pos != -1:
                    print(f"✅ 使用标题匹配找到章节: {clean_title}")
                    return pos
                    
                # 尝试部分匹配
                if len(clean_title) > 6:
                    partial_title = clean_title[:6]
                    pos = full_text.find(partial_title)
                    if pos != -1:
                        print(f"✅ 使用部分标题匹配找到章节: {partial_title}")
                        return pos
        
        print(f"❌ 无法找到章节位置: title='{title}', start_text='{start_text[:50]}...'")
        return -1


    def _process_step_2_4_multimodal(self, final_schema: FinalMetadataSchema):
        """
        Step 2.4: 多模态描述生成（并行处理）
        更新原有image_chunks和table_chunks的结构化描述字段
        """
        print("🖼️  开始多模态描述生成...")
        
        # 收集需要处理的图片和表格
        image_tasks = []
        table_tasks = []
        
        for img_chunk in final_schema.image_chunks:
            if not img_chunk.search_summary:  # 只处理还没有结构化描述的
                image_tasks.append(img_chunk)
        
        for table_chunk in final_schema.table_chunks:
            if not table_chunk.search_summary:  # 只处理还没有结构化描述的
                table_tasks.append(table_chunk)
        
        print(f"📊 待处理: {len(image_tasks)}张图片, {len(table_tasks)}个表格")
        
        if not image_tasks and not table_tasks:
            print("ℹ️  所有多模态内容已有结构化描述，跳过处理")
            return
        
        # 并行处理图片
        if image_tasks and self.ai_clients.get('openrouter'):
            print(f"🔄 并行处理{len(image_tasks)}张图片...")
            self._parallel_process_images(image_tasks)
        
        # 并行处理表格 (如果需要的话)
        if table_tasks and self.ai_clients.get('openrouter'):
            print(f"🔄 并行处理{len(table_tasks)}个表格...")
            self._parallel_process_tables(table_tasks)
        
        print("✅ 多模态描述生成完成")
    
    def _parallel_process_images(self, image_tasks: List):
        """并行处理图片描述生成"""
        import concurrent.futures
        
        def process_single_image(img_chunk):
            try:
                # 调用AI生成结构化描述
                result = self._generate_structured_image_description(img_chunk)
                return img_chunk, result, None
            except Exception as e:
                return img_chunk, None, str(e)
        
        # 使用线程池并行处理（AI调用是IO密集型）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_single_image, img) for img in image_tasks]
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                img_chunk, result, error = future.result()
                
                if error:
                    print(f"⚠️  图片 {img_chunk.content_id} 处理失败: {error}")
                elif result:
                    # 更新结构化描述字段
                    img_chunk.search_summary = result.get('search_summary')
                    img_chunk.detailed_description = result.get('detailed_description') 
                    img_chunk.engineering_details = result.get('engineering_details')
                    print(f"✅ 图片 {i+1}/{len(image_tasks)} 处理完成")
    
    def _generate_structured_image_description(self, img_chunk) -> Optional[Dict[str, Any]]:
        """为单张图片生成结构化描述"""
        if not self.ai_clients.get('openrouter'):
            return None
        
        try:
            # 构建prompt
            prompt = self.image_description_prompt.format(
                page_context=img_chunk.page_context or "无上下文信息"
            )
            
            # 调用AI生成描述（包含图片）
            client = self.ai_clients['openrouter']
            
            # 构建图片路径
            image_path = Path(img_chunk.image_path)
            if not image_path.is_absolute():
                # 相对路径，需要从项目根目录解析
                project_root = Path(__file__).parent.parent.parent
                image_path = project_root / image_path
            
            if not image_path.exists():
                print(f"⚠️  图片文件不存在: {image_path}")
                return None
            
            # 调用OpenRouter客户端生成描述
            response = client.get_image_description_gemini(str(image_path), prompt)
            
            if not response:
                return None
            
            # 尝试解析JSON响应（处理markdown包装的情况）
            try:
                import json
                import re
                
                # 先尝试直接解析
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试从markdown中提取JSON
                # 查找 ```json ... ``` 或 ``` ... ``` 格式
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                    try:
                        result = json.loads(json_str)
                        return result
                    except json.JSONDecodeError:
                        pass
                
                # 如果仍然失败，查找第一个 { 到最后一个 } 之间的内容
                brace_match = re.search(r'\{.*\}', response, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group(0)
                    try:
                        result = json.loads(json_str)
                        return result
                    except json.JSONDecodeError:
                        pass
                
                # 最后的fallback：把整个响应作为detailed_description
                print(f"⚠️  AI返回非JSON格式，使用fallback处理: {response[:100]}...")
                return {
                    "search_summary": "AI生成的图片描述",
                    "detailed_description": response,
                    "engineering_details": None
                }
        
        except Exception as e:
            print(f"⚠️  图片描述生成失败: {str(e)}")
            return None
    
    def _parallel_process_tables(self, table_tasks: List):
        """并行处理表格描述生成（类似图片处理）"""
        if not table_tasks:
            print("📋 无表格需要处理")
            return
        
        print(f"📋 开始处理 {len(table_tasks)} 个表格...")
        
        def process_single_table(table_chunk):
            """处理单个表格的描述生成"""
            try:
                # 调用AI生成结构化描述
                result = self._generate_structured_table_description(table_chunk)
                return table_chunk, result, None
            except Exception as e:
                return table_chunk, None, str(e)
        
        # 使用线程池并行处理（AI调用是IO密集型）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_single_table, table) for table in table_tasks]
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                table_chunk, result, error = future.result()
                
                if error:
                    print(f"⚠️  表格 {table_chunk.content_id} 处理失败: {error}")
                elif result:
                    # 更新结构化描述字段
                    table_chunk.search_summary = result.get('search_summary')
                    table_chunk.detailed_description = result.get('detailed_description') 
                    table_chunk.engineering_details = result.get('engineering_details')
                    print(f"✅ 表格 {i+1}/{len(table_tasks)} 处理完成")

    def _generate_structured_table_description(self, table_chunk) -> Optional[Dict[str, Any]]:
        """为单个表格生成结构化描述"""
        if not self.ai_clients.get('openrouter'):
            return None
        
        try:
            # 构建prompt
            prompt = self.table_description_prompt.format(
                page_context=table_chunk.page_context or "无上下文信息"
            )
            
            # 调用AI生成描述（包含表格图片）
            client = self.ai_clients['openrouter']
            
            # 构建表格图片路径
            table_path = Path(table_chunk.table_path)
            if not table_path.is_absolute():
                # 相对路径，需要从项目根目录解析
                project_root = Path(__file__).parent.parent.parent
                table_path = project_root / table_path
            
            if not table_path.exists():
                print(f"⚠️  表格文件不存在: {table_path}")
                return None
            
            # 调用OpenRouter客户端生成描述
            response = client.get_image_description_gemini(str(table_path), prompt)
            
            if not response:
                return None
            
            # 尝试解析JSON响应（处理markdown包装的情况）
            try:
                import json
                import re
                
                # 先尝试直接解析
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试从markdown中提取JSON
                # 查找 ```json ... ``` 或 ``` ... ``` 格式
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                    try:
                        result = json.loads(json_str)
                        return result
                    except json.JSONDecodeError:
                        pass
                
                # 如果仍然失败，查找第一个 { 到最后一个 } 之间的内容
                brace_match = re.search(r'\{.*\}', response, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group(0)
                    try:
                        result = json.loads(json_str)
                        return result
                    except json.JSONDecodeError:
                        pass
                
                # 最后的fallback：把整个响应作为detailed_description
                print(f"⚠️  AI返回非JSON格式，使用fallback处理: {response[:100]}...")
                return {
                    "search_summary": "AI生成的表格描述",
                    "detailed_description": response,
                    "engineering_details": None
                }
        
        except Exception as e:
            print(f"⚠️  表格描述生成失败: {str(e)}")
            return None

    def _load_stage1_data(self, input_path: str) -> FinalMetadataSchema:
        """加载Stage1处理的数据"""
        input_path_obj = Path(input_path)
        
        if input_path_obj.is_file() and input_path_obj.name.endswith('.json'):
            # 输入是json文件，直接加载
            metadata_path = input_path_obj
        else:
            # 输入是目录，查找其中的final_metadata.json
            metadata_path = input_path_obj / "final_metadata.json"
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"找不到metadata文件: {metadata_path}")
        
        print(f"📖 从{metadata_path}加载Stage1数据...")
        final_schema = FinalMetadataSchema.load(str(metadata_path))
        
        # 检查必要数据
        if not final_schema.document_summary:
            raise ValueError("缺少document_summary数据，无法继续Stage2处理")
            
        if not final_schema.document_summary.page_texts:
            raise ValueError("缺少page_texts数据，无法继续Stage2处理")
            
        print(f"📊 待处理数据: {len(final_schema.document_summary.page_texts)}页文本")
        return final_schema
    
    def _clean_page_text(self, raw_text: str) -> str:
        """清理单页文本"""
        if not raw_text or not raw_text.strip():
            return raw_text
            
        try:
            qwen_client = self.ai_clients['qwen']
            prompt = self.text_cleaning_prompt.format(original_text=raw_text)
            
            # 调用Qwen进行文本清洗
            cleaned_text = qwen_client.generate_response(prompt)
            return cleaned_text.strip() if cleaned_text else raw_text
            
        except Exception as e:
            print(f"❌ 文本清洗失败: {e}")
            return raw_text
    
    def _print_processing_report(self, final_schema: FinalMetadataSchema, processing_time: float):
        """打印处理报告"""
        print(f"\n📊 Stage2处理报告:")
        print(f"   ⏱️  处理时间: {processing_time:.2f}秒")
        print(f"   📄 页面修复: {self.stats.get('pages_repaired', 0)}页")
        print(f"   🖼️  图片描述: {self.stats.get('images_described', 0)}张")  
        print(f"   📊 表格描述: {self.stats.get('tables_described', 0)}个")
        
        if final_schema.image_chunks:
            structured_images = sum(1 for img in final_schema.image_chunks if img.search_summary)
            print(f"   🎯 结构化图片描述: {structured_images}/{len(final_schema.image_chunks)}")
        
        if final_schema.table_chunks:
            structured_tables = sum(1 for table in final_schema.table_chunks if table.search_summary)
            print(f"   🎯 结构化表格描述: {structured_tables}/{len(final_schema.table_chunks)}")
            
    def process_demo(self, final_metadata_path: str) -> Tuple[FinalMetadataSchema, str]:
        """
        演示版本的处理方法，保持原有的返回类型用于测试
        """
        print(f"🚀 开始Stage2演示处理...")
        
        # 加载数据并处理
        final_schema = self._load_stage1_data(final_metadata_path)
        self._process_step_2_1_text_repair(final_schema)
        self._process_step_2_4_multimodal(final_schema)
        
        # 保存演示结果（创建新文件）
        output_path = final_metadata_path.replace('.json', '_stage2_demo.json')
        final_schema.save(output_path)
        
        return final_schema, output_path


def create_stage2_processor() -> Stage2IntelligentProcessor:
    """创建Stage2处理器实例"""
    return Stage2IntelligentProcessor()


def process_stage2_from_file(final_metadata_path: str) -> Tuple[FinalMetadataSchema, str]:
    """
    从final_metadata.json文件开始Stage2处理
    
    Args:
        final_metadata_path: Stage1输出的final_metadata.json路径
        
    Returns:
        Tuple[FinalMetadataSchema, str]: (更新后的schema, 保存路径)
    """
    processor = create_stage2_processor()
    output_path = processor.process(final_metadata_path)
    
    # 重新加载更新后的schema
    final_schema = FinalMetadataSchema.load(output_path)
    
    return final_schema, output_path 


def main():
    """主函数，支持命令行参数"""
    import sys
    import os
    
    if len(sys.argv) != 2:
        print("Usage: python -m src.pdf_processing_2.stage2_intelligent_processor <output_dir>")
        print("Example: python -m src.pdf_processing_2.stage2_intelligent_processor parser_output_v2/test_stage1_20250716_154105/")
        sys.exit(1)
    
    output_dir = sys.argv[1]
    final_metadata_path = os.path.join(output_dir, "final_metadata.json")
    
    if not os.path.exists(final_metadata_path):
        print(f"❌ 找不到文件: {final_metadata_path}")
        sys.exit(1)
    
    try:
        print(f"🚀 开始Stage2智能处理: {final_metadata_path}")
        processor = create_stage2_processor()
        output_path = processor.process(final_metadata_path)
        print(f"✅ Stage2处理完成，结果保存到: {output_path}")
        
    except Exception as e:
        print(f"❌ Stage2处理失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 