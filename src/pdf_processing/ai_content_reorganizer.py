"""
AI Content Reorganizer

负责使用AI模型对PDF解析内容进行重组和增强处理
"""

import os
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import base64
from pathlib import Path
import time

from .config import PDFProcessingConfig
from .data_models import PageData, ImageWithContext, TableWithContext

# 尝试导入AI客户端
try:
    # 导入项目中的AI客户端
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.deepseek_client import DeepSeekClient
    from src.openrouter_client import OpenRouterClient
    from src.qwen_client import QwenClient
    
    AI_CLIENTS_AVAILABLE = True
    print("✅ AI客户端可用")
except ImportError as e:
    AI_CLIENTS_AVAILABLE = False
    print(f"⚠️ AI客户端不可用: {e}")
    
    # 创建占位符类型
    class DeepSeekClient:
        pass
    
    class OpenRouterClient:
        pass
    
    class QwenClient:
        pass


class AIContentReorganizer:
    """
    AI内容重组器
    
    负责使用AI模型对PDF解析的内容进行清洗、重组和增强：
    1. 逐页文本清洗和重组
    2. 图片描述生成
    3. 表格描述生成
    4. 支持多种AI模型和并行处理
    """
    
    def __init__(self, config: Optional[PDFProcessingConfig] = None):
        """
        初始化AI内容重组器
        
        Args:
            config: PDF处理配置
        """
        self.config = config or PDFProcessingConfig()
        self.ai_clients = {}
        self.supported_models = {}
        
        # 初始化AI客户端
        self._init_ai_clients()
        
        # 文本清洗提示词模板 - 专注于OCR错误修复和格式整理
        self.text_cleaning_prompt = """
# 任务
修复OCR识别错误和格式问题，还原干净可读的原文。

# 输入文本
{raw_text}

# 修复规则
1. **修正OCR识别错误**：修复字符识别错误、乱码、错误的字符组合
2. **整理格式问题**：
   - 删除多余的空行和换行符
   - 修正不当的空格分布
   - 整理段落间距
   - 修正标点符号的位置和格式
3. **保持原文完整性**：
   - 不删除任何内容
   - 不改变原文表达
   - 不进行意思解释或重组
   - 保持所有数字、引用、公式等原样
4. **输出要求**：
   - 纯文本格式，无markdown标记
   - 保持原文的完整结构和层次
   - 确保文本连贯可读

# 修复后的文本
"""
        
        # 图片描述提示词模板 - 基于image_analysis.yaml优化
        self.image_description_prompt = """
# 角色
你是一个精炼的图像分析引擎。

# 任务
为给定的图片生成一段极其精简的核心描述，该描述将用于语义搜索。你的目标是"索引"图片内容，而不是"解说"图片。

# 页面上下文（参考文字）
{page_context}

# 核心规则
1. **专注于关键元素**：只识别和描述图片中最核心的1-3个主体、状态或概念。
2. **提取关键词，而非完整叙述**：生成能够代表图片内容的关键词组合或短语，而不是一个故事性的段落。多使用名词和关键动词。
3. **结构建议**：尽量使用"主体 + 状态/行为 + 关键对象"的结构。例如，"一张关于[主题]的[图表类型]"或"[主体]的[某种状态]特写"。
4. **绝对简洁**：描述通常应在15到30字之间。剔除所有不必要的修饰词和引导语（例如不要用"这张图片显示了…"）。
5. **忽略无关上下文**：如果图片附带的参考文字与图片内容不符，必须完全忽略该文字。

# 示例
- **输入图片**: 一张管道接口处严重生锈的照片。
- **合格输出**: "管道接口处的严重腐蚀与金属锈迹特写。"
- **不合格输出**: "这张图片向我们展示了一个看起来很旧的金属管道，它连接着另一个部分，连接处有很多棕色的锈迹，可能是因为长时间暴露在潮湿环境中导致的。"

# 图片描述
"""
        
        # 表格描述提示词模板 - 专注于表格数据和结构
        self.table_description_prompt = """
# 角色
你是一个专业的表格数据分析引擎。

# 任务
为给定的表格生成一段精简的核心描述，该描述将用于语义搜索。你的目标是"索引"表格的数据结构和关键信息，而不是详细解读每个数据点。

# 页面上下文（参考文字）
{page_context}

# 核心规则
1. **专注于表格结构**：识别表格的主要维度（行列标题、数据类型、主要分类）。
2. **提取关键数据特征**：关注数据范围、趋势、关键数值，而不是列举所有数据。
3. **结构建议**：使用"[主题]的[数据类型]表格"或"[维度1] vs [维度2]的[数据特征]对比"的结构。
4. **绝对简洁**：描述通常应在20到40字之间。剔除所有不必要的修饰词。
5. **忽略无关上下文**：如果表格附带的参考文字与表格内容不符，必须完全忽略该文字。

# 示例
- **输入表格**: 一个显示不同年份销售数据的表格，包含产品类别和销售额。
- **合格输出**: "2020-2023年各产品类别销售额统计表格。"
- **不合格输出**: "这个表格详细展示了从2020年到2023年期间，公司各个产品类别的销售额数据，可以看出电子产品的销售额最高，而服装类产品的销售额相对较低。"

# 表格描述
"""
    
    def _init_ai_clients(self) -> None:
        """初始化AI客户端"""
        if not AI_CLIENTS_AVAILABLE:
            print("⚠️ AI客户端不可用，跳过初始化")
            return
        
        try:
            # 初始化Qwen客户端（专用于文本处理，高rate limit）
            self.ai_clients['qwen'] = QwenClient(
                model=self.config.ai_content.default_llm_model,
                max_tokens=self.config.ai_content.max_context_length // 10,  # 合理的token限制
                max_retries=self.config.ai_content.max_retries,
                enable_batch_mode=True  # 启用批处理模式
            )
            self.supported_models['qwen'] = ['qwen-turbo-latest', 'qwen-plus-latest', 'qwen-max-latest']
            print("✅ Qwen客户端初始化成功（用于文本清洗，高rate limit）")
        except Exception as e:
            print(f"⚠️ Qwen客户端初始化失败: {e}")
        

        try:
            # 初始化DeepSeek客户端（备用文本处理）
            self.ai_clients['deepseek'] = DeepSeekClient()
            self.supported_models['deepseek'] = ['deepseek-chat', 'deepseek-reasoner']
            print("✅ DeepSeek客户端初始化成功（备用文本清洗）")
        except Exception as e:
            print(f"⚠️ DeepSeek客户端初始化失败: {e}")
        
        try:
            # 初始化OpenRouter客户端（专用于多模态处理）
            self.ai_clients['openrouter'] = OpenRouterClient()
            self.supported_models['openrouter'] = [
                'google/gemini-2.5-flash',  # 主要用于图片和表格描述
                'google/gemini-pro'         # 备用多模态模型
            ]
            print("✅ OpenRouter客户端初始化成功（用于多模态处理）")
        except Exception as e:
            print(f"⚠️ OpenRouter客户端初始化失败: {e}")
    
    def process_pages(self, pages: List[PageData], 
                     parallel_processing: bool = True) -> List[PageData]:
        """
        处理页面数据，进行文本清洗和媒体描述生成
        
        Args:
            pages: 页面数据列表
            parallel_processing: 是否使用并行处理
            
        Returns:
            List[PageData]: 处理后的页面数据列表
        """
        if not pages:
            print("⚠️ 没有页面数据需要处理")
            return []
        
        print(f"🚀 开始AI内容重组处理...")
        print(f"📄 总页数: {len(pages)}")
        print(f"⚡ 并行处理: {'启用' if parallel_processing else '禁用'}")
        
        start_time = time.time()
        
        if parallel_processing and len(pages) > 1:
            processed_pages = self._process_pages_parallel(pages)
        else:
            processed_pages = self._process_pages_sequential(pages)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"✅ AI处理完成，耗时: {processing_time:.2f} 秒")
        return processed_pages
    
    def _process_pages_parallel(self, pages: List[PageData]) -> List[PageData]:
        """并行处理页面 - 使用伪批量处理（ThreadPoolExecutor）"""
        print("⚡ 使用并行处理模式...")
        
        # 直接使用伪批量处理，不使用真正的Batch API
        if 'qwen' in self.ai_clients and len(pages) > 1:
            print("🚀 使用Qwen伪批量处理文本清洗...")
            return self._process_pages_batch(pages)
        
        # 否则使用传统的并行处理
        max_workers = min(self.config.ai_content.max_workers if hasattr(self.config.ai_content, 'max_workers') else 4, len(pages))
        processed_pages = [None] * len(pages)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_index = {
                executor.submit(self._process_single_page, page): i 
                for i, page in enumerate(pages)
            }
            
            # 收集结果
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    processed_page = future.result()
                    processed_pages[index] = processed_page
                    print(f"✅ 页面 {processed_page.page_number} 处理完成")
                except Exception as e:
                    print(f"❌ 页面 {pages[index].page_number} 处理失败: {e}")
                    # 保留原始页面数据
                    processed_pages[index] = pages[index]
        
        # 过滤None值
        return [page for page in processed_pages if page is not None]
    
    def _process_pages_batch(self, pages: List[PageData]) -> List[PageData]:
        """批量处理页面 - 利用Qwen的批量处理能力"""
        print(f"🚀 批量处理 {len(pages)} 个页面...")
        
        # 创建页面副本
        processed_pages = []
        for page in pages:
            processed_page = PageData(
                page_number=page.page_number,
                raw_text=page.raw_text,
                cleaned_text=page.cleaned_text,
                images=page.images.copy() if page.images else [],
                tables=page.tables.copy() if page.tables else []
            )
            processed_pages.append(processed_page)
        
        # 1. 批量文本清洗
        if 'qwen' in self.ai_clients:
            self._batch_clean_texts(processed_pages)
        
        # 2. 并行处理图片和表格描述（这部分仍然需要VLM模型）
        if 'openrouter' in self.ai_clients:
            self._batch_process_media(processed_pages)
        
        return processed_pages
    

    
    def _batch_clean_texts(self, pages: List[PageData]):
        """批量清洗文本（使用ThreadPoolExecutor伪批处理）"""
        print("🧹 批量清洗文本...")
        
        # 收集需要清洗的文本
        text_prompts = []
        page_indices = []
        
        for i, page in enumerate(pages):
            if page.raw_text and not page.cleaned_text:
                prompt = self.text_cleaning_prompt.format(raw_text=page.raw_text)
                text_prompts.append(prompt)
                page_indices.append(i)
        
        if not text_prompts:
            print("⚠️ 没有需要清洗的文本")
            return
        
        print(f"📝 批量清洗 {len(text_prompts)} 个文本...")
        
        try:
            # 使用Qwen客户端批量处理
            client = self.ai_clients['qwen']
            max_workers = min(self.config.ai_content.max_workers, len(text_prompts))
            
            responses = client.batch_generate_responses(
                text_prompts, 
                max_workers=max_workers
            )
            
            # 将响应分配回页面
            for i, response in enumerate(responses):
                page_index = page_indices[i]
                pages[page_index].cleaned_text = response.strip() if response else pages[page_index].raw_text
                print(f"✅ 页面 {pages[page_index].page_number} 文本清洗完成")
        
        except Exception as e:
            print(f"❌ 批量文本清洗失败: {e}")
            # 降级到逐个处理
            for i, page_index in enumerate(page_indices):
                try:
                    pages[page_index].cleaned_text = self._clean_page_text(pages[page_index].raw_text)
                except Exception as e2:
                    print(f"⚠️ 页面 {pages[page_index].page_number} 文本清洗失败: {e2}")
                    pages[page_index].cleaned_text = pages[page_index].raw_text
    
    def _batch_process_media(self, pages: List[PageData]):
        """批量处理图片和表格描述"""
        print("🖼️ 批量处理媒体描述...")
        
        # 收集所有需要处理的图片和表格
        all_tasks = []
        
        for page in pages:
            # 图片任务
            for img in page.images:
                if not img.ai_description:
                    all_tasks.append(('image', img, page))
            
            # 表格任务
            for table in page.tables:
                if not table.ai_description:
                    all_tasks.append(('table', table, page))
        
        if not all_tasks:
            print("⚠️ 没有需要处理的媒体")
            return
        
        print(f"📊 批量处理 {len(all_tasks)} 个媒体项...")
        
        # 使用线程池并行处理媒体
        max_workers = min(self.config.ai_content.max_workers, len(all_tasks))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(self._process_single_media_item, task_type, item, page): (task_type, item, page)
                for task_type, item, page in all_tasks
            }
            
            for future in as_completed(future_to_task):
                task_type, item, page = future_to_task[future]
                try:
                    description = future.result()
                    if description:
                        item.ai_description = description
                        print(f"✅ {task_type} 描述生成完成 (页面 {page.page_number})")
                except Exception as e:
                    print(f"❌ {task_type} 描述生成失败 (页面 {page.page_number}): {e}")
    
    def _process_single_media_item(self, task_type: str, item, page: PageData) -> Optional[str]:
        """处理单个媒体项"""
        try:
            page_context = page.raw_text or ""
            
            if task_type == 'image':
                return self._generate_image_description(item.image_path, page_context)
            elif task_type == 'table':
                return self._generate_table_description(item.table_path, page_context)
            else:
                return None
        except Exception as e:
            print(f"⚠️ 处理 {task_type} 失败: {e}")
            return None
    
    def _process_pages_sequential(self, pages: List[PageData]) -> List[PageData]:
        """顺序处理页面"""
        print("🔄 使用顺序处理模式...")
        
        processed_pages = []
        for page in pages:
            try:
                processed_page = self._process_single_page(page)
                processed_pages.append(processed_page)
                print(f"✅ 页面 {processed_page.page_number} 处理完成")
            except Exception as e:
                print(f"❌ 页面 {page.page_number} 处理失败: {e}")
                # 保留原始页面数据
                processed_pages.append(page)
        
        return processed_pages
    
    def _process_single_page(self, page: PageData) -> PageData:
        """
        处理单个页面
        
        Args:
            page: 页面数据
            
        Returns:
            PageData: 处理后的页面数据
        """
        # 创建页面副本，避免修改原始数据
        processed_page = PageData(
            page_number=page.page_number,
            raw_text=page.raw_text,
            cleaned_text=page.cleaned_text,
            images=page.images.copy() if page.images else [],
            tables=page.tables.copy() if page.tables else []
        )
        
        try:
            # 1. 文本清洗
            if processed_page.raw_text and not processed_page.cleaned_text:
                processed_page.cleaned_text = self._clean_page_text(processed_page.raw_text)
            
            # 2. 图片描述生成
            for img in processed_page.images:
                if not img.ai_description:
                    img.ai_description = self._generate_image_description(
                        img.image_path, 
                        img.page_context or processed_page.raw_text
                    )
            
            # 3. 表格描述生成
            for table in processed_page.tables:
                if not table.ai_description:
                    table.ai_description = self._generate_table_description(
                        table.table_path, 
                        table.page_context or processed_page.raw_text
                    )
        
        except Exception as e:
            print(f"⚠️ 页面 {page.page_number} 部分处理失败: {e}")
        
        return processed_page
    
    def _clean_page_text(self, raw_text: str) -> str:
        """
        清洗页面文本
        
        Args:
            raw_text: 原始文本
            
        Returns:
            str: 清洗后的文本
        """
        if not raw_text.strip():
            return raw_text
        
        try:
            # 检查文本长度，避免超过模型限制
            if len(raw_text) > self.config.ai_content.max_context_length:
                print(f"⚠️ 文本长度超限 ({len(raw_text)} > {self.config.ai_content.max_context_length})，截断处理")
                raw_text = raw_text[:self.config.ai_content.max_context_length]
            
            # 优先使用Qwen进行文本清洗（高rate limit）
            if 'qwen' in self.ai_clients:
                print("🧠 使用Qwen进行文本清洗（高rate limit）...")
                return self._call_qwen_for_text(raw_text)
            # 备用DeepSeek进行文本清洗
            elif 'deepseek' in self.ai_clients:
                print("🧠 使用DeepSeek进行文本清洗（备用）...")
                return self._call_deepseek_for_text(raw_text)
            else:
                print("⚠️ 文本清洗客户端不可用，跳过文本清洗")
                return raw_text
                
        except Exception as e:
            print(f"❌ 文本清洗失败: {e}")
            return raw_text
    
    def _generate_image_description(self, image_path: str, page_context: str) -> str:
        """
        生成图片描述
        
        Args:
            image_path: 图片路径
            page_context: 页面上下文
            
        Returns:
            str: 图片描述
        """
        if not os.path.exists(image_path):
            return f"图片文件不存在: {image_path}"
        
        try:
            # 使用Gemini 2.5 Flash进行多模态图片描述
            if 'openrouter' in self.ai_clients:
                print(f"🖼️ 使用Gemini 2.5 Flash生成图片描述: {os.path.basename(image_path)}")
                vlm_model = self.config.ai_content.default_vlm_model  # google/gemini-2.5-flash
                return self._call_openrouter_for_vision(image_path, page_context, vlm_model)
            else:
                print("⚠️ OpenRouter客户端不可用，跳过图片描述生成")
                return f"图片: {os.path.basename(image_path)}"
                
        except Exception as e:
            print(f"❌ 图片描述生成失败: {e}")
            return f"图片: {os.path.basename(image_path)} (处理失败)"
    
    def _generate_table_description(self, table_path: str, page_context: str) -> str:
        """
        生成表格描述
        
        Args:
            table_path: 表格路径
            page_context: 页面上下文
            
        Returns:
            str: 表格描述
        """
        if not os.path.exists(table_path):
            return f"表格文件不存在: {table_path}"
        
        try:
            # 使用Gemini 2.5 Flash进行多模态表格描述
            if 'openrouter' in self.ai_clients:
                print(f"📊 使用Gemini 2.5 Flash生成表格描述: {os.path.basename(table_path)}")
                vlm_model = self.config.ai_content.default_vlm_model  # google/gemini-2.5-flash
                return self._call_openrouter_for_vision(
                    table_path, page_context, vlm_model, is_table=True
                )
            else:
                print("⚠️ OpenRouter客户端不可用，跳过表格描述生成")
                return f"表格: {os.path.basename(table_path)}"
                
        except Exception as e:
            print(f"❌ 表格描述生成失败: {e}")
            return f"表格: {os.path.basename(table_path)} (处理失败)"
    
    def _call_qwen_for_text(self, text: str) -> str:
        """调用Qwen进行文本清洗"""
        try:
            client = self.ai_clients['qwen']
            prompt = self.text_cleaning_prompt.format(raw_text=text)
            
            # 调用Qwen API
            response = client.generate_response(prompt)
            return response.strip() if response else text
            
        except Exception as e:
            print(f"❌ Qwen调用失败: {e}")
            # 如果Qwen失败，尝试降级到DeepSeek
            if 'deepseek' in self.ai_clients:
                print("🔄 降级到DeepSeek...")
                return self._call_deepseek_for_text(text)
            return text
    
    def _call_deepseek_for_text(self, text: str) -> str:
        """调用DeepSeek进行文本清洗"""
        try:
            client = self.ai_clients['deepseek']
            prompt = self.text_cleaning_prompt.format(raw_text=text)
            
            # 调用DeepSeek API
            response = client.generate_response(prompt)
            return response.strip() if response else text
            
        except Exception as e:
            print(f"❌ DeepSeek调用失败: {e}")
            return text
    
    def _call_openrouter_for_vision(self, image_path: str, page_context: str, 
                                  model: str, is_table: bool = False) -> str:
        """调用OpenRouter进行视觉处理"""
        try:
            client = self.ai_clients['openrouter']
            
            # 选择合适的提示词
            if is_table:
                prompt = self.table_description_prompt.format(page_context=page_context)
            else:
                prompt = self.image_description_prompt.format(page_context=page_context)
            
            # 调用OpenRouter Vision API（使用现有的get_image_description_gemini方法）
            response = client.get_image_description_gemini(image_path, prompt)
            
            return response.strip() if response else f"{'表格' if is_table else '图片'}处理失败"
            
        except Exception as e:
            print(f"❌ OpenRouter视觉调用失败: {e}")
            return f"{'表格' if is_table else '图片'}: {os.path.basename(image_path)} (处理失败)"
    
    def get_processing_stats(self, pages: List[PageData]) -> Dict[str, Any]:
        """
        获取处理统计信息
        
        Args:
            pages: 处理后的页面数据
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {
            "total_pages": len(pages),
            "pages_with_cleaned_text": 0,
            "total_images": 0,
            "images_with_ai_description": 0,
            "total_tables": 0,
            "tables_with_ai_description": 0,
            "average_text_length": 0,
            "average_cleaned_text_length": 0
        }
        
        total_text_length = 0
        total_cleaned_text_length = 0
        
        for page in pages:
            # 文本统计
            if page.raw_text:
                total_text_length += len(page.raw_text)
            if page.cleaned_text:
                stats["pages_with_cleaned_text"] += 1
                total_cleaned_text_length += len(page.cleaned_text)
            
            # 图片统计
            stats["total_images"] += len(page.images)
            for img in page.images:
                if img.ai_description:
                    stats["images_with_ai_description"] += 1
            
            # 表格统计
            stats["total_tables"] += len(page.tables)
            for table in page.tables:
                if table.ai_description:
                    stats["tables_with_ai_description"] += 1
        
        # 计算平均值
        if stats["total_pages"] > 0:
            stats["average_text_length"] = total_text_length / stats["total_pages"]
            
        if stats["pages_with_cleaned_text"] > 0:
            stats["average_cleaned_text_length"] = total_cleaned_text_length / stats["pages_with_cleaned_text"]
        
        return stats 