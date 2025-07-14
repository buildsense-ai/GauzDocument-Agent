"""
Media Extractor

专门负责从PDF中提取图片和表格，并关联页面上下文的组件
"""

import os
import re
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .data_models import PageData, ImageWithContext, TableWithContext

# 导入docling相关组件
try:
    from docling_core.types.doc.document import PictureItem, TableItem, RefItem
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    DOCLING_AVAILABLE = True
    print("✅ Docling组件可用")
except ImportError as e:
    DOCLING_AVAILABLE = False
    print(f"❌ Docling组件不可用: {e}")
    
    # 创建占位符类型，避免类型错误
    class PictureItem:
        pass
    
    class TableItem:
        pass
    
    class RefItem:
        pass


class MediaExtractor:
    """
    媒体提取器 - 专门负责从PDF中提取图片和表格
    
    核心功能：
    1. 按页提取图片和表格
    2. 关联每个图片/表格与其所在页面的文字上下文
    3. 支持并行处理
    4. 生成标准化的数据结构
    """
    
    def __init__(self, parallel_processing: bool = True, max_workers: int = 4):
        """
        初始化媒体提取器
        
        Args:
            parallel_processing: 是否启用并行处理
            max_workers: 并行处理的最大工作线程数
        """
        self.parallel_processing = parallel_processing
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._global_image_counter = 0  # 全局图片计数器
        self._global_table_counter = 0  # 全局表格计数器
        self._processed_elements = set()  # 已处理元素的ID集合，用于去重
        
        if not DOCLING_AVAILABLE:
            print("⚠️ Docling不可用，MediaExtractor功能受限")
    
    def extract_media_from_pages(self, 
                                raw_result: Any, 
                                page_texts: Dict[int, str],
                                output_dir: str) -> List[PageData]:
        """
        从PDF解析结果中按页提取图片和表格
        
        Args:
            raw_result: Docling解析结果
            page_texts: 页码到页面文本的映射 {page_number: page_text}
            output_dir: 输出目录
            
        Returns:
            List[PageData]: 包含图片和表格的页面数据列表
        """
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling不可用，无法提取媒体")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 初始化页面数据
        pages = []
        for page_num, page_text in page_texts.items():
            pages.append(PageData(
                page_number=page_num,
                raw_text=page_text,
                images=[],
                tables=[]
            ))
        
        # 保存raw_result的引用
        self.raw_result = raw_result
        
        # 使用新的提取方法，直接从document的集合中获取
        self._extract_media_from_collections(pages, output_dir)
        
        return pages
    
    def _extract_media_from_collections(self, pages: List[PageData], output_dir: str):
        """
        直接从document的集合中提取媒体，避免RefItem问题
        """
        print("🔄 使用直接集合访问方式提取媒体...")
        
        # 提取图片
        image_counter = 0
        for picture in self.raw_result.document.pictures:
            image_counter += 1
            try:
                # 获取图片
                picture_image = picture.get_image(self.raw_result.document)
                if picture_image is None:
                    print(f"⚠️ 图片 {image_counter} 对象为空")
                    continue
                
                # 保存图片
                image_filename = f"picture-{image_counter}.png"
                image_path = os.path.join(output_dir, image_filename)
                with open(image_path, "wb") as fp:
                    picture_image.save(fp, "PNG")
                
                # 获取图片信息
                from PIL import Image
                image_img = Image.open(image_path)
                caption = picture.caption_text(self.raw_result.document) if hasattr(picture, 'caption_text') else ""
                
                # 找到图片所在的页面
                page_number = self._get_element_page_number(picture, pages)
                if page_number is None:
                    print(f"⚠️ 无法确定图片 {image_counter} 所在页面")
                    continue
                
                # 找到对应的页面数据
                page_data = None
                for page in pages:
                    if page.page_number == page_number:
                        page_data = page
                        break
                
                if page_data is None:
                    print(f"⚠️ 找不到页面 {page_number} 的数据")
                    continue
                
                # 创建ImageWithContext对象
                image_with_context = ImageWithContext(
                    image_path=image_path,
                    page_number=page_number,
                    page_context=page_data.raw_text[:1000],  # 获取页面上下文
                    caption=caption or f"图片 {image_counter}",
                    metadata={
                        'width': image_img.width,
                        'height': image_img.height,
                        'size': image_img.width * image_img.height,
                        'aspect_ratio': image_img.width / image_img.height
                    }
                )
                
                # 添加到页面数据
                page_data.images.append(image_with_context)
                print(f"✅ 保存图片 {image_counter}: {image_path}")
                
            except Exception as e:
                print(f"❌ 保存图片 {image_counter} 失败: {e}")
        
        # 提取表格
        table_counter = 0
        for table in self.raw_result.document.tables:
            table_counter += 1
            try:
                # 获取表格图片
                table_image = table.get_image(self.raw_result.document)
                if table_image is None:
                    print(f"⚠️ 表格 {table_counter} 对象为空")
                    continue
                
                # 保存表格图片
                table_filename = f"table-{table_counter}.png"
                table_path = os.path.join(output_dir, table_filename)
                with open(table_path, "wb") as fp:
                    table_image.save(fp, "PNG")
                
                # 获取表格信息
                from PIL import Image
                table_img = Image.open(table_path)
                caption = table.caption_text(self.raw_result.document) if hasattr(table, 'caption_text') else ""
                
                # 找到表格所在的页面
                page_number = self._get_element_page_number(table, pages)
                if page_number is None:
                    print(f"⚠️ 无法确定表格 {table_counter} 所在页面")
                    continue
                
                # 找到对应的页面数据
                page_data = None
                for page in pages:
                    if page.page_number == page_number:
                        page_data = page
                        break
                
                if page_data is None:
                    print(f"⚠️ 找不到页面 {page_number} 的数据")
                    continue
                
                # 创建TableWithContext对象
                table_with_context = TableWithContext(
                    table_path=table_path,
                    page_number=page_number,
                    page_context=page_data.raw_text[:1000],  # 获取页面上下文
                    caption=caption or f"表格 {table_counter}",
                    metadata={
                        'width': table_img.width,
                        'height': table_img.height,
                        'size': table_img.width * table_img.height,
                        'aspect_ratio': table_img.width / table_img.height
                    }
                )
                
                # 添加到页面数据
                page_data.tables.append(table_with_context)
                print(f"✅ 保存表格 {table_counter}: {table_path}")
                
            except Exception as e:
                print(f"❌ 保存表格 {table_counter} 失败: {e}")
        
        print(f"📊 集合提取完成: {image_counter} 个图片, {table_counter} 个表格")
    
    def _extract_media_parallel(self, 
                               all_elements: List[Tuple[Any, int]], 
                               pages: List[PageData],
                               output_dir: str):
        """并行提取媒体"""
        # 分离图片和表格元素，同时进行去重
        image_elements = []
        table_elements = []
        
        for idx, (element, level) in enumerate(all_elements):
            # 创建元素唯一标识符，用于去重
            element_id = self._get_element_id(element, idx)
            
            if element_id in self._processed_elements:
                print(f"⚠️ 跳过重复元素: {element_id}")
                continue
            
            # 调试：打印元素类型
            element_type = type(element).__name__
            if idx < 5 or element_type in ['TableItem', 'RefItem'] or 'Table' in element_type or 'Ref' in element_type:
                print(f"🔍 调试元素类型: {element_type} (idx={idx})")
            
            # 先检查RefItem（避免被TableItem误匹配）
            if isinstance(element, RefItem):
                # RefItem是对其他地方定义的表格/图片的引用，跳过处理
                print(f"⚠️ 跳过RefItem引用: {element_id}")
                continue
            elif isinstance(element, PictureItem):
                with self._lock:
                    self._global_image_counter += 1
                    counter = self._global_image_counter
                image_elements.append((idx, element, level, counter, element_id))
            elif isinstance(element, TableItem):
                print(f"🔍 发现TableItem: {element_type} (idx={idx})")
                with self._lock:
                    self._global_table_counter += 1
                    counter = self._global_table_counter
                table_elements.append((idx, element, level, counter, element_id))
            else:
                # 跳过其他类型的元素，包括任何未知的引用类型
                element_type = type(element).__name__
                if 'ref' in element_type.lower() or 'Ref' in element_type:
                    print(f"⚠️ 跳过引用类型元素: {element_type} - {element_id}")
                elif idx < 10:  # 只打印前10个未知类型
                    print(f"⚠️ 跳过未知类型元素: {element_type} - {element_id}")
        
        # 并行处理图片
        if image_elements:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                image_futures = {
                    executor.submit(
                        self._extract_single_image, 
                        idx, element, level, pages, output_dir, counter
                    ): (idx, element_id)
                    for idx, element, level, counter, element_id in image_elements
                }
                
                for future in as_completed(image_futures):
                    try:
                        result = future.result()
                        if result:
                            page_data, image_with_context = result
                            with self._lock:
                                page_data.images.append(image_with_context)
                                # 标记元素为已处理
                                _, element_id = image_futures[future]
                                self._processed_elements.add(element_id)
                    except Exception as e:
                        print(f"❌ 并行提取图片失败: {e}")
        
        # 并行处理表格
        if table_elements:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                table_futures = {
                    executor.submit(
                        self._extract_single_table, 
                        idx, element, level, pages, output_dir, counter
                    ): (idx, element_id)
                    for idx, element, level, counter, element_id in table_elements
                }
                
                for future in as_completed(table_futures):
                    try:
                        result = future.result()
                        if result:
                            page_data, table_with_context = result
                            with self._lock:
                                page_data.tables.append(table_with_context)
                                # 标记元素为已处理
                                _, element_id = table_futures[future]
                                self._processed_elements.add(element_id)
                    except Exception as e:
                        print(f"❌ 并行提取表格失败: {e}")
        
        print(f"📊 并行提取完成: {len(image_elements)} 个图片, {len(table_elements)} 个表格")
    
    def _extract_media_sequential(self, 
                                all_elements: List[Tuple[Any, int]], 
                                pages: List[PageData],
                                output_dir: str):
        """顺序提取媒体"""
        image_counter = 0
        table_counter = 0
        
        for idx, (element, level) in enumerate(all_elements):
            # 创建元素唯一标识符，用于去重
            element_id = self._get_element_id(element, idx)
            
            if element_id in self._processed_elements:
                print(f"⚠️ 跳过重复元素: {element_id}")
                continue
            
            # 先检查RefItem（避免被TableItem误匹配）
            if isinstance(element, RefItem):
                # RefItem是对其他地方定义的表格/图片的引用，跳过处理
                print(f"⚠️ 跳过RefItem引用: {element_id}")
                continue
            elif isinstance(element, PictureItem):
                image_counter += 1
                self._global_image_counter += 1
                result = self._extract_single_image(idx, element, level, pages, output_dir, self._global_image_counter)
                if result:
                    page_data, image_with_context = result
                    page_data.images.append(image_with_context)
                    self._processed_elements.add(element_id)
            elif isinstance(element, TableItem):
                table_counter += 1
                self._global_table_counter += 1
                result = self._extract_single_table(idx, element, level, pages, output_dir, self._global_table_counter)
                if result:
                    page_data, table_with_context = result
                    page_data.tables.append(table_with_context)
                    self._processed_elements.add(element_id)
        
        print(f"📊 顺序提取完成: {image_counter} 个图片, {table_counter} 个表格")
    
    def _extract_single_image(self, 
                            idx: int, 
                            element: PictureItem, 
                            level: int,
                            pages: List[PageData], 
                            output_dir: str,
                            counter: Optional[int] = None) -> Optional[Tuple[PageData, ImageWithContext]]:
        """提取单个图片"""
        try:
            # 获取图片所在页面
            page_number = self._get_element_page_number(element, pages)
            if page_number is None:
                print(f"⚠️ 无法确定图片所在页面，跳过处理")
                return None
            
            # 找到对应的页面数据
            page_data = None
            for page in pages:
                if page.page_number == page_number:
                    page_data = page
                    break
            
            if page_data is None:
                print(f"⚠️ 找不到页面 {page_number} 的数据")
                return None
            
            # 使用传入的计数器，确保文件名唯一
            if counter is None:
                with self._lock:
                    self._global_image_counter += 1
                    counter = self._global_image_counter
            
            image_filename = f"picture-{counter}.png"
            image_path = os.path.join(output_dir, image_filename)
            
            # 获取图片对象
            picture_image = element.get_image(element.parent)
            if picture_image is None:
                print(f"⚠️ 图片 {counter} 对象为空")
                return None
            
            # 保存图片
            with open(image_path, "wb") as fp:
                picture_image.save(fp, "PNG")
            
            # 获取图片元数据
            image_pil = Image.open(image_path)
            metadata = {
                'width': image_pil.width,
                'height': image_pil.height,
                'figure_size': image_pil.width * image_pil.height,
                'figure_aspect': image_pil.width / image_pil.height,
                'element_index': idx,
                'level': level
            }
            
            # 获取caption - 只保留有意义的caption
            caption = None
            if hasattr(element, 'caption_text'):
                try:
                    raw_caption = element.caption_text(element.parent)
                    # 只保留非空且非自动生成格式的caption
                    if raw_caption and not raw_caption.startswith(('图片', 'Figure', 'Fig.')):
                        caption = raw_caption.strip()
                except:
                    pass
            
            # 创建ImageWithContext对象
            image_with_context = ImageWithContext(
                image_path=image_path,
                page_number=page_number,
                page_context=page_data.raw_text,
                caption=caption,  # None或有意义的caption
                metadata=metadata
            )
            
            print(f"✅ 提取图片 {counter}: {image_path} (页面 {page_number}, {image_pil.width}×{image_pil.height})")
            return page_data, image_with_context
            
        except Exception as e:
            print(f"❌ 提取图片 {counter if counter else 'unknown'} 失败: {e}")
            return None
    
    def _extract_single_table(self, 
                            idx: int, 
                            element: TableItem, 
                            level: int,
                            pages: List[PageData], 
                            output_dir: str,
                            counter: Optional[int] = None) -> Optional[Tuple[PageData, TableWithContext]]:
        """提取单个表格"""
        try:
            # 安全检查：确保element不是RefItem
            element_type = type(element).__name__
            if isinstance(element, RefItem) or 'RefItem' in element_type:
                print(f"⚠️ 跳过RefItem对象 (表格 {counter}): {element_type}")
                return None
            
            # 防御性检查：确保element有必要的属性
            if not hasattr(element, 'get_image'):
                print(f"⚠️ 表格元素缺少get_image方法 (表格 {counter}): {element_type}")
                return None
            
            # 获取表格所在页面
            page_number = self._get_element_page_number(element, pages)
            if page_number is None:
                print(f"⚠️ 无法确定表格所在页面")
                return None
            
            # 找到对应的页面数据
            page_data = None
            for page in pages:
                if page.page_number == page_number:
                    page_data = page
                    break
            
            if page_data is None:
                print(f"⚠️ 找不到页面 {page_number} 的数据")
                return None
            
            # 生成表格文件名
            if counter is None:
                counter = len([p for p in pages for tbl in p.tables]) + 1
            
            table_filename = f"table-{counter}.png"
            table_path = os.path.join(output_dir, table_filename)
            
            # 获取表格图片
            table_image = element.get_image(element.parent)
            if table_image is None:
                print(f"⚠️ 表格 {counter} 图像为空")
                return None
            
            # 保存表格图片
            with open(table_path, "wb") as fp:
                table_image.save(fp, "PNG")
            
            # 获取表格元数据
            table_pil = Image.open(table_path)
            metadata = {
                'width': table_pil.width,
                'height': table_pil.height,
                'figure_size': table_pil.width * table_pil.height,
                'figure_aspect': table_pil.width / table_pil.height,
                'element_index': idx,
                'level': level
            }
            
            # 获取caption - 只保留有意义的caption
            caption = None
            if hasattr(element, 'caption_text'):
                try:
                    raw_caption = element.caption_text(element.parent)
                    # 只保留非空且非自动生成格式的caption
                    if raw_caption and not raw_caption.startswith(('表格', 'Table', 'Tab.')):
                        caption = raw_caption.strip()
                except:
                    pass
            
            # 创建TableWithContext对象
            table_with_context = TableWithContext(
                table_path=table_path,
                page_number=page_number,
                page_context=page_data.raw_text,
                caption=caption,  # None或有意义的caption
                metadata=metadata
            )
            
            print(f"✅ 提取表格 {counter}: {table_path} (页面 {page_number})")
            return page_data, table_with_context
            
        except Exception as e:
            print(f"❌ 提取表格 {counter if counter else 'unknown'} 失败: {e}")
            return None
    
    def _get_element_id(self, element: Any, idx: int) -> str:
        """
        生成元素的唯一标识符，用于去重
        
        Args:
            element: 元素对象
            idx: 元素索引
            
        Returns:
            str: 唯一标识符
        """
        # 尝试获取元素的唯一属性组合
        element_info = []
        
        # 添加元素类型
        element_info.append(type(element).__name__)
        
        # 添加位置信息（如果有的话）
        if hasattr(element, 'bbox') and element.bbox:
            element_info.append(f"bbox_{element.bbox}")
        elif hasattr(element, 'coordinates') and element.coordinates:
            element_info.append(f"coords_{element.coordinates}")
        
        # 添加页面信息
        if hasattr(element, 'page'):
            element_info.append(f"page_{element.page}")
        
        # 添加索引
        element_info.append(f"idx_{idx}")
        
        return "_".join(str(info) for info in element_info)

    def _get_element_page_number(self, element: Any, pages: List[PageData]) -> Optional[int]:
        """
        获取元素所在的页面编号
        
        Args:
            element: 图片或表格元素
            pages: 页面数据列表
            
        Returns:
            Optional[int]: 页面编号（从1开始），如果无法确定则返回None
        """
        try:
            # 安全检查：如果element是RefItem，直接返回None
            if isinstance(element, RefItem):
                print(f"⚠️ _get_element_page_number 收到RefItem对象: {type(element).__name__}")
                return None
            
            # 只对前3个元素进行详细调试
            debug_detail = self._global_image_counter <= 3
            
            if debug_detail:
                # 调试：打印元素的所有属性
                element_attrs = [attr for attr in dir(element) if not attr.startswith('_')]
                print(f"🔍 调试元素属性: {element_attrs}")
                
                # 调试：打印元素的关键属性值
                if hasattr(element, 'page'):
                    print(f"🔍 element.page = {element.page}")
                if hasattr(element, 'parent'):
                    print(f"🔍 element.parent = {element.parent}")
                    if element.parent and hasattr(element.parent, 'page'):
                        print(f"🔍 element.parent.page = {element.parent.page}")
                if hasattr(element, 'bbox'):
                    print(f"🔍 element.bbox = {element.bbox}")
                if hasattr(element, 'prov'):
                    print(f"🔍 element.prov = {element.prov}")
            
            # 方法1：直接从元素获取页面信息
            if hasattr(element, 'page') and element.page is not None:
                page_num = element.page + 1
                if debug_detail:
                    print(f"🔍 从元素获取页面信息: {page_num}")
                return page_num
            
            # 方法2：从prov属性获取页面信息（这是Docling常用的方式）
            if hasattr(element, 'prov') and element.prov:
                # prov通常是一个列表，取第一个元素
                if isinstance(element.prov, (list, tuple)) and len(element.prov) > 0:
                    prov_item = element.prov[0]
                    if hasattr(prov_item, 'page_no') and prov_item.page_no is not None:
                        page_num = prov_item.page_no
                        if debug_detail:
                            print(f"🔍 从prov[0].page_no获取页面信息: {page_num}")
                        return page_num
                
                # 如果prov不是列表，直接检查
                if hasattr(element.prov, 'page_no') and element.prov.page_no is not None:
                    page_num = element.prov.page_no
                    if debug_detail:
                        print(f"🔍 从prov.page_no获取页面信息: {page_num}")
                    return page_num
                    
                # 检查其他可能的page属性
                if hasattr(element.prov, 'page') and element.prov.page is not None:
                    page_num = element.prov.page + 1
                    if debug_detail:
                        print(f"🔍 从prov.page获取页面信息: {page_num}")
                    return page_num
                    
                # 检查prov的其他可能属性
                for attr in ['page_num', 'page_number']:
                    if hasattr(element.prov, attr):
                        page_val = getattr(element.prov, attr)
                        if page_val is not None:
                            page_num = page_val + 1 if page_val >= 0 else page_val
                            if debug_detail:
                                print(f"🔍 从prov.{attr}获取页面信息: {page_num}")
                            return page_num
            
            # 方法3：从父元素获取页面信息
            if hasattr(element, 'parent') and element.parent:
                parent = element.parent
                if hasattr(parent, 'page') and parent.page is not None:
                    page_num = parent.page + 1
                    if debug_detail:
                        print(f"🔍 从父元素获取页面信息: {page_num}")
                    return page_num
                
                # 检查父元素的prov属性
                if hasattr(parent, 'prov') and parent.prov:
                    if hasattr(parent.prov, 'page') and parent.prov.page is not None:
                        page_num = parent.prov.page + 1
                        if debug_detail:
                            print(f"🔍 从父元素prov获取页面信息: {page_num}")
                        return page_num
            
            # 方法4：简化的启发式方法 - 假设图片按顺序分布在前面的页面
            if len(pages) > 0:
                # 根据当前处理的图片数量估算页面
                # 假设每页平均有2-3个图片
                estimated_page = min(len(pages), max(1, (self._global_image_counter - 1) // 3 + 1))
                if debug_detail:
                    print(f"🔍 使用启发式方法估算页面: {estimated_page} (图片#{self._global_image_counter})")
                return estimated_page
            
            # 如果所有方法都失败，返回第1页作为默认值
            print(f"⚠️ 无法确定元素页面，使用默认页面1")
            return 1
            
        except Exception as e:
            print(f"❌ 获取元素页面信息失败: {e}")
            # 出错时也返回第1页
            return 1
    
    def save_media_info(self, pages: List[PageData], output_dir: str):
        """
        保存媒体信息到JSON文件
        
        Args:
            pages: 页面数据列表
            output_dir: 输出目录
        """
        import json
        
        # 收集所有图片信息
        all_images = {}
        image_counter = 0
        
        for page in pages:
            for img in page.images:
                image_counter += 1
                all_images[str(image_counter)] = {
                    'caption': img.caption,
                    'image_path': img.image_path,
                    'page_number': img.page_number,
                    'page_context': img.page_context,
                    'ai_description': img.ai_description,
                    'metadata': img.metadata
                }
        
        # 收集所有表格信息
        all_tables = {}
        table_counter = 0
        
        for page in pages:
            for tbl in page.tables:
                table_counter += 1
                all_tables[str(table_counter)] = {
                    'caption': tbl.caption,
                    'table_path': tbl.table_path,
                    'page_number': tbl.page_number,
                    'page_context': tbl.page_context,
                    'ai_description': tbl.ai_description,
                    'metadata': tbl.metadata
                }
        
        # 保存图片信息
        if all_images:
            images_path = os.path.join(output_dir, "images.json")
            with open(images_path, 'w', encoding='utf-8') as f:
                json.dump(all_images, f, indent=4, ensure_ascii=False)
            print(f"🖼️ 图片信息已保存到: {images_path}")
        
        # 保存表格信息
        if all_tables:
            tables_path = os.path.join(output_dir, "tables.json")
            with open(tables_path, 'w', encoding='utf-8') as f:
                json.dump(all_tables, f, indent=4, ensure_ascii=False)
            print(f"📊 表格信息已保存到: {tables_path}")
        
        print(f"📋 媒体信息保存完成: {len(all_images)} 个图片, {len(all_tables)} 个表格") 
    
    def extract_media(self, pdf_path: str, output_dir: str) -> List[PageData]:
        """
        完整的媒体提取流程 - 从PDF文件直接提取媒体
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            List[PageData]: 包含图片和表格的页面数据列表
        """
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling不可用，无法提取媒体")
        
        try:
            # 导入需要的类
            from docling.document_converter import DocumentConverter
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            
            # 创建文档转换器
            converter = DocumentConverter()
            
            # 解析PDF文档
            print(f"🔄 开始解析PDF: {pdf_path}")
            conv_result = converter.convert(pdf_path)
            
            # 提取页面文本
            print(f"📄 提取页面文本")
            page_texts = {}
            doc = conv_result.document
            
            # 获取所有页面的文本
            for page_num in range(len(doc.pages)):
                page = doc.pages[page_num]
                try:
                    # 尝试不同的方法来获取页面文本
                    if hasattr(page, 'export_to_text'):
                        page_text = page.export_to_text()
                    elif hasattr(page, 'text'):
                        page_text = page.text
                    else:
                        # 如果都没有，使用空字符串
                        page_text = ""
                    page_texts[page_num + 1] = page_text  # 页码从1开始
                except Exception as e:
                    print(f"⚠️ 获取页面 {page_num + 1} 文本失败: {e}")
                    page_texts[page_num + 1] = ""
            
            print(f"📄 提取到 {len(page_texts)} 页文本")
            
            # 调用现有的媒体提取方法
            pages = self.extract_media_from_pages(
                raw_result=conv_result,
                page_texts=page_texts,
                output_dir=output_dir
            )
            
            # 保存媒体信息
            self.save_media_info(pages, output_dir)
            
            return pages
            
        except Exception as e:
            print(f"❌ 媒体提取失败: {e}")
            raise 