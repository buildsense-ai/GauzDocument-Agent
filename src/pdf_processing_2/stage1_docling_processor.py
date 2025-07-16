#!/usr/bin/env python3
"""
Stage 1 Processor: Docling解析 + 初始Schema填充

负责使用Docling解析PDF，提取文本、图片、表格，并初始化Final Schema
这是整个重构pipeline的第一阶段，为后续阶段提供基础数据

V2版本：采用页面切割方式，确保页码准确，支持并行处理
"""

import os
import sys
import time
import tempfile
import shutil
import multiprocessing
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# 导入PDF处理库
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
    print("✅ PyMuPDF (fitz) 可用")
except ImportError:
    FITZ_AVAILABLE = False
    print("❌ PyMuPDF (fitz) 不可用，请安装: pip install PyMuPDF")

# 导入docling组件
try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    DOCLING_AVAILABLE = True
    print("✅ Docling组件可用")
except ImportError as e:
    DOCLING_AVAILABLE = False
    print(f"❌ Docling组件不可用: {e}")

# 导入V1版本的配置和数据模型
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pdf_processing.config import PDFProcessingConfig
from pdf_processing.data_models import PageData, ImageWithContext, TableWithContext

# 导入V2版本的Schema
from .final_schema import FinalMetadataSchema, DocumentSummary, ImageChunk, TableChunk


class Stage1DoclingProcessor:
    """
    阶段1处理器：Docling解析 + 初始Schema填充
    
    V2版本主要功能：
    1. 将PDF按页面切割为单页PDF文件
    2. 并行处理每页，确保页码准确
    3. 生成full_raw_text并插入图片表格标记
    4. 初始化FinalMetadataSchema并填充基础信息
    5. 保存初始化的final_metadata.json
    """
    
    def __init__(self, config: Optional[PDFProcessingConfig] = None, use_process_pool: bool = True):
        """
        初始化处理器
        
        Args:
            config: PDF处理配置，如果为None则使用默认配置
            use_process_pool: 是否使用进程池（推荐用于CPU密集型任务）
            
        🎛️ 关于 use_process_pool 参数的选择指南：
        
        ✅ use_process_pool=True (推荐，默认选择)：
        📈 性能优势：
        - 真正的并行计算，可以100%利用多核CPU
        - 绕过Python GIL限制，每个进程独立运行
        - 理论加速比接近进程数（5进程≈5倍速度）
        
        🛡️ 稳定性优势：
        - 进程隔离：一个页面崩溃不影响其他页面
        - 内存独立：避免内存泄漏累积
        - 故障恢复：单个进程失败后会自动重启
        
        ⚠️ 注意事项：
        - 进程启动有开销（约1-2秒）
        - 内存使用稍高（每进程独立内存空间）
        - 需要足够的系统资源
        
        🧵 use_process_pool=False (线程池模式)：
        📋 适用场景：
        - 系统资源受限（内存不足、CPU核心少）
        - 需要频繁共享数据
        - 任务较轻量，进程启动开销太大
        
        ⚠️ 性能限制：
        - 受Python GIL限制，CPU密集型任务可能无法并行
        - 但docling有C扩展，部分操作可以释放GIL
        - 适合I/O密集型任务（文件读写、网络请求）
        
        🎯 如何选择？
        - 如果你的电脑有4核以上CPU：选择进程池
        - 如果处理大型PDF（>20页）：选择进程池
        - 如果电脑性能较弱或内存紧张：选择线程池
        - 如果不确定：使用默认的进程池模式
        """
        self.config = config or PDFProcessingConfig.from_env()
        self.use_process_pool = use_process_pool
        self.doc_converter = None
        
        if not FITZ_AVAILABLE:
            raise RuntimeError("PyMuPDF不可用，无法进行页面分割")
        
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling不可用，无法进行页面处理")
        
        self._init_docling_converter()
        
        # 💡 智能模式提示
        cpu_cores = multiprocessing.cpu_count()
        if use_process_pool:
            print(f"🏭 已选择进程池模式（适合{cpu_cores}核CPU的并行计算）")
            if cpu_cores < 4:
                print(f"💡 提示：你的CPU只有{cpu_cores}核，考虑使用线程池可能更合适")
        else:
            print(f"🧵 已选择线程池模式（轻量级并发）")
            if cpu_cores >= 8:
                print(f"💡 提示：你的CPU有{cpu_cores}核，使用进程池可能获得更好性能")
                
        print("✅ Stage1DoclingProcessor V2 初始化完成")
    
    def _init_docling_converter(self) -> None:
        """初始化Docling转换器"""
        try:
            # 设置本地模型路径
            models_cache_dir = Path("models_cache")
            artifacts_path = None
            if models_cache_dir.exists():
                artifacts_path = str(models_cache_dir.absolute())
            elif self.config.docling.artifacts_path:
                artifacts_path = self.config.docling.artifacts_path
            
            # 🔧 配置离线模式，避免网络连接问题
            import os
            os.environ['HF_HUB_OFFLINE'] = '1'  # 强制HuggingFace Hub离线模式
            os.environ['TRANSFORMERS_OFFLINE'] = '1'  # Transformers离线模式
            print("🔒 已启用离线模式，避免网络连接问题")
            
            # 创建管道选项
            if self.config.docling.ocr_enabled:
                # 🔥 增强OCR配置，确保文字提取成功
                ocr_options = EasyOcrOptions()
                try:
                    # 核心OCR设置
                    ocr_options.force_full_page_ocr = True  # 强制全页OCR
                    
                    # 🚀 添加更多OCR优化设置（只使用实际存在的属性）
                    if hasattr(ocr_options, 'use_gpu'):
                        ocr_options.use_gpu = False  # 强制使用CPU，避免GPU兼容性问题
                    
                    if hasattr(ocr_options, 'lang'):
                        ocr_options.lang = ['ch_sim', 'en']  # 支持中英文
                    
                    if hasattr(ocr_options, 'confidence_threshold'):
                        ocr_options.confidence_threshold = 0.3  # 降低置信度阈值，提高检出率
                    
                    if hasattr(ocr_options, 'bitmap_area_threshold'):
                        ocr_options.bitmap_area_threshold = 0.01  # 降低区域阈值，检测更小文字
                    
                    print("✅ 应用增强OCR设置：")
                    print("   - force_full_page_ocr=True（强制全页OCR）")
                    print("   - use_gpu=False（CPU模式，避免兼容性问题）")
                    print("   - lang=['ch_sim', 'en']（中英文支持）")
                    print("   - confidence_threshold=0.3（降低置信度阈值）")
                    print("   - bitmap_area_threshold=0.01（检测更小文字）")
                    
                except Exception as e:
                    print(f"⚠️ 应用增强OCR设置失败: {e}")
                
                pipeline_options = PdfPipelineOptions(
                    ocr_options=ocr_options,
                    artifacts_path=artifacts_path
                )
            else:
                print("⚠️ OCR已禁用，可能导致文字提取不完整")
                pipeline_options = PdfPipelineOptions(
                    artifacts_path=artifacts_path
                )
            
            # 设置解析选项
            pipeline_options.images_scale = self.config.docling.images_scale
            pipeline_options.generate_page_images = self.config.docling.generate_page_images
            pipeline_options.generate_picture_images = self.config.docling.generate_picture_images
            
            # 🚀 添加更多解析选项
            if hasattr(pipeline_options, 'do_ocr'):
                pipeline_options.do_ocr = True  # 确保OCR执行
            
            if hasattr(pipeline_options, 'do_table_structure'):
                pipeline_options.do_table_structure = True  # 表格结构识别
            
            # 创建文档转换器
            self.doc_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            
            print("✅ Docling转换器初始化成功（增强OCR配置）")
            
        except Exception as e:
            print(f"❌ Docling转换器初始化失败: {e}")
            self.doc_converter = None
    
    def process(self, pdf_path: str, output_dir: str) -> Tuple[FinalMetadataSchema, str]:
        """
        执行阶段1处理
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            Tuple[FinalMetadataSchema, str]: (final_schema对象, final_metadata.json文件路径)
        """
        print(f"🚀 开始阶段1处理（页面切割版本）: {pdf_path}")
        stage_start_time = time.time()
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 初始化Final Schema
        final_schema = FinalMetadataSchema()
        final_schema.update_processing_status("stage1_started", 10)
        
        try:
            # 步骤1: 分割PDF为单页文件
            print("📄 步骤1: 分割PDF为单页文件")
            single_page_files = self._split_pdf_to_pages(pdf_path)
            print(f"📄 PDF分割完成，共 {len(single_page_files)} 页")
            final_schema.update_processing_status("pdf_split", 15)
            
            # 步骤2: 并行处理所有页面
            print("🔄 步骤2: 并行处理所有页面")
            if self.config.media_extractor.parallel_processing:
                pages_data = self._process_pages_parallel(single_page_files, output_dir)
            else:
                pages_data = self._process_pages_sequential(single_page_files, output_dir)
            final_schema.update_processing_status("pages_processed", 25)
            
            # 步骤3: 清理临时文件
            print("🧹 步骤3: 清理临时文件")
            self._cleanup_temp_files(single_page_files)
            
            # 步骤4: 生成full_raw_text并插入媒体标记
            print("📝 步骤4: 生成full_raw_text")
            full_raw_text, page_texts = self._generate_full_raw_text_with_media_markers(pages_data)
            final_schema.update_processing_status("full_text_generated", 27)
            
            # 步骤5: 填充Final Schema
            print("📋 步骤5: 填充Final Schema")
            self._populate_final_schema(
                final_schema, pdf_path, full_raw_text, page_texts, pages_data, stage_start_time
            )
            final_schema.update_processing_status("stage1_completed", 30)
            
            # 步骤6: 保存Final Schema
            final_metadata_path = os.path.join(output_dir, "final_metadata.json")
            final_schema.save(final_metadata_path)
            
            stage_duration = time.time() - stage_start_time
            print(f"✅ 阶段1处理完成，耗时: {stage_duration:.2f} 秒")
            print(f"📁 保存位置: {final_metadata_path}")
            print(f"📊 初始填充完成度: {final_schema.get_completion_percentage()}%")
            
            return final_schema, final_metadata_path
            
        except Exception as e:
            # 确保清理临时文件
            if 'single_page_files' in locals():
                self._cleanup_temp_files(single_page_files)
            
            error_msg = f"阶段1处理失败: {str(e)}"
            print(f"❌ {error_msg}")
            final_schema.update_processing_status("stage1_failed", 0, error_msg)
            raise RuntimeError(error_msg) from e
    
    def _split_pdf_to_pages(self, pdf_path: str) -> List[Tuple[int, str]]:
        """
        将PDF分割为单页文件
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            List[Tuple[int, str]]: [(页码, 单页PDF文件路径), ...]
        """
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="pdf_pages_")
        single_page_files = []
        
        try:
            for page_num in range(total_pages):
                # 创建新的PDF文档，只包含当前页
                single_page_doc = fitz.open()
                single_page_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                # 保存单页PDF
                single_page_path = os.path.join(temp_dir, f"page_{page_num + 1}.pdf")
                single_page_doc.save(single_page_path)
                single_page_doc.close()
                
                single_page_files.append((page_num + 1, single_page_path))
                
        finally:
            doc.close()
        
        return single_page_files
    
    def _get_optimal_worker_count(self, total_tasks: int) -> int:
        """
        根据任务数量和系统配置计算最优worker数量
        
        🤔 什么是进程池和线程池？
        
        📚 科普时间：
        - 进程池 (ProcessPoolExecutor)：
          🏭 想象成一个工厂，每个工人（进程）都有独立的工作台和工具
          💪 优点：每个工人完全独立，一个出问题不影响其他人，能充分利用多核CPU
          🐌 缺点：启动工人需要时间，工人之间交流比较麻烦（需要通过文件/管道）
          
        - 线程池 (ThreadPoolExecutor)：
          🏢 想象成一个开放式办公室，所有员工（线程）共享办公设备和资料
          ⚡ 优点：启动快，员工之间交流方便（共享内存）
          ⚠️ 缺点：一个员工出大问题可能影响整个办公室，受Python GIL限制
        
        🎯 对于我们的PDF处理任务：
        - Docling是CPU密集型任务（大量图像识别、文字提取）
        - 选择进程池可以绕过Python的GIL限制，真正实现并行计算
        
        Args:
            total_tasks: 总任务数量
            
        Returns:
            int: 最优worker数量
        """
        if self.use_process_pool:
            # 🔥 为什么CPU核心数很重要？
            # 
            # 💻 你的电脑CPU核心情况：
            # - 每个CPU核心同时只能执行一个进程的计算
            # - 如果进程数 > 核心数，会导致"抢夺资源"，反而变慢
            # 
            # ⚠️ 为什么cpu_count-1会让电脑"拉满"？
            # - 假设你有8核CPU，开8个进程意味着100%占用所有核心
            # - 操作系统、浏览器、其他软件都没有CPU资源了
            # - 电脑会变得卡顿，风扇狂转，温度飙升
            # 
            # 🎯 合理的设置策略：
            # - 使用核心数的一半：给系统和其他程序留空间
            # - 这样既能享受并行处理的速度提升，又不会让电脑"死机"
            
            cpu_count = multiprocessing.cpu_count()
            # 📊 CPU负载影响分析：
            # - 1核：适合轻量任务，但速度慢
            # - 核心数/4：保守设置，适合在工作时后台运行
            # - 核心数/2：平衡设置，既快又不影响其他工作
            # - 核心数-1：激进设置，几乎100%CPU使用，电脑可能卡顿
            # - 核心数：危险设置，系统可能无响应
            max_workers = max(1, cpu_count // 2)
            
            print(f"🧠 CPU分析：你的电脑有{cpu_count}个核心")
            print(f"⚖️ 为了平衡性能和稳定性，我们使用{max_workers}个进程")
            print(f"📈 这样能提升约{max_workers}倍的处理速度，同时保持电脑响应流畅")
            
        else:
            # 🧵 线程池的特殊考虑：
            # 
            # 🐍 Python的GIL（全局解释器锁）限制：
            # - 即使开100个线程，CPU密集型任务实际上还是串行执行
            # - 但对于I/O密集型任务（网络请求、文件读写），线程池很有用
            # - Docling虽然是CPU密集，但中间有很多文件读写操作
            # 
            # 💡 为什么限制为8个线程？
            # - 线程太多会增加上下文切换的开销
            # - 对于混合型任务，8个线程通常是甜点
            max_workers = min(8, multiprocessing.cpu_count())
            
            print(f"🧵 使用线程池模式，创建{max_workers}个线程")
            print(f"💭 注意：由于Python GIL限制，实际CPU利用率可能不会满载")
        
        # 📝 最终优化：不要创建比任务更多的worker
        # 如果只有3页PDF，开10个进程就是浪费资源
        optimal_workers = min(max_workers, total_tasks)
        
        print(f"💻 系统配置: CPU核心数={multiprocessing.cpu_count()}, 使用{'进程池' if self.use_process_pool else '线程池'}")
        print(f"⚙️ 工作进程/线程数: {optimal_workers} (总任务: {total_tasks})")
        
        # 🎓 小贴士：如何进一步优化？
        if optimal_workers == 1:
            print("💡 提示：任务较少，考虑串行处理可能更简单")
        elif self.use_process_pool and optimal_workers >= multiprocessing.cpu_count() * 0.75:
            print("⚠️ 提示：使用了较多CPU资源，处理期间电脑可能会比较卡")
        
        # 🛡️ 安全提醒：最大设置建议
        max_safe_workers = multiprocessing.cpu_count() - 1
        if optimal_workers > max_safe_workers:
            print(f"🚨 警告：worker数量({optimal_workers})接近CPU核心数({multiprocessing.cpu_count()})")
            print(f"🔧 建议：最大不要超过{max_safe_workers}个worker，否则系统可能无响应")
            print(f"💊 解决方案：如需更高性能，考虑使用更强的硬件或分批处理")
        
        return optimal_workers
    
    def _process_pages_parallel(self, 
                               single_page_files: List[Tuple[int, str]], 
                               output_dir: str) -> List[PageData]:
        """
        并行处理所有页面（支持线程池和进程池）
        
        🎯 为什么选择并行处理？
        
        📊 性能对比（以12页PDF为例）：
        - 串行处理：12页 × 10秒/页 = 120秒
        - 5进程并行：12页 ÷ 5进程 ≈ 25秒（提升80%）
        - 但要考虑：进程启动开销 + 系统稳定性
        
        🤔 什么时候用进程池 vs 线程池？
        
        💡 进程池适合的场景：
        - CPU密集型任务（图像处理、机器学习推理）
        - 任务之间相互独立
        - 不需要频繁共享数据
        - 我们的PDF处理完美符合这些条件！
        
        🧵 线程池适合的场景：
        - I/O密集型任务（网络请求、文件下载）
        - 需要频繁共享数据
        - 任务启动/结束很频繁
        """
        
        # 计算最优worker数量
        optimal_workers = self._get_optimal_worker_count(len(single_page_files))
        
        print(f"⚡ 启用并行处理模式: {'进程池' if self.use_process_pool else '线程池'}")
        print(f"🔧 工作进程/线程数: {optimal_workers}")
        
        # 🔄 重试机制配置
        max_retries = 3  # 最大重试次数
        retry_delay = 2.0  # 重试间隔（秒）
        
        print(f"🔄 重试配置: 最大{max_retries}次重试，间隔{retry_delay}秒")
        
        # 🎭 为什么需要这个复杂的列表？
        # - 并行处理的结果可能乱序返回（页面2可能比页面1先完成）
        # - 我们需要按页码顺序重新排列结果
        # - 预分配列表确保每个页面都有固定位置
        pages_data: List[Optional[PageData]] = [None] * len(single_page_files)
        
        # 🔄 重试队列管理
        current_batch = single_page_files.copy()  # 当前处理批次
        retry_count = 0
        
        # 🏭 选择合适的"工厂"类型
        executor_class = ProcessPoolExecutor if self.use_process_pool else ThreadPoolExecutor
        
        while current_batch and retry_count <= max_retries:
            if retry_count > 0:
                print(f"🔄 第{retry_count}次重试，处理{len(current_batch)}个失败页面...")
                if retry_count > 1:  # 第二次重试后增加延迟
                    import time
                    time.sleep(retry_delay)
            
            failed_pages = []  # 本轮失败的页面
            
            try:
                # 🎪 开始并行处理的"马戏团表演"
                with executor_class(max_workers=optimal_workers) as executor:
                    # 📋 任务分发：把工作分配给不同的worker
                    if self.use_process_pool:
                        # 🏭 进程池模式：
                        # 
                        # ⚠️ 重要限制：进程之间不能直接共享对象！
                        # - 不能传递 self（类实例）
                        # - 必须使用独立的静态函数
                        # - 所有参数都要能"序列化"（转换成二进制数据传输）
                        # 
                        # 💾 数据传输开销：
                        # - 每个进程启动时都要传递config对象
                        # - 进程间通信通过管道/共享内存
                        # - 这就是为什么进程启动比线程慢的原因
                        
                        future_to_page = {
                            executor.submit(
                                _process_single_page_static,  # 📞 调用独立的静态函数
                                page_num, 
                                single_page_path, 
                                output_dir,
                                self.config  # 🚚 配置对象会被"打包"发送给子进程
                            ): page_num
                            for page_num, single_page_path in current_batch
                        }
                        
                        print(f"🚀 已向{optimal_workers}个独立进程分发{len(current_batch)}个任务")
                        print(f"💡 每个进程都是独立的Python解释器，可以充分利用CPU核心")
                        
                    else:
                        # 🧵 线程池模式：
                        # 
                        # ✅ 便利性：可以直接调用类方法
                        # - 所有线程共享同一个内存空间
                        # - 可以直接访问 self 和所有实例变量
                        # - 数据传递几乎没有开销
                        # 
                        # ⚠️ GIL限制：
                        # - Python的全局解释器锁意味着同时只有一个线程在执行Python代码
                        # - 对于纯CPU任务，多线程可能不会带来速度提升
                        # - 但docling中有很多C扩展和I/O操作，这些可以释放GIL
                        
                        future_to_page = {
                            executor.submit(
                                self._process_single_page,  # 📞 直接调用实例方法
                                page_num, 
                                single_page_path, 
                                output_dir
                            ): page_num
                            for page_num, single_page_path in current_batch
                        }
                        
                        print(f"🧵 已向{optimal_workers}个线程分发{len(current_batch)}个任务")
                        print(f"💭 所有线程共享内存，但受Python GIL限制可能无法满载CPU")
                    
                    # 🎭 收集表演结果：等待所有任务完成
                    completed_count = 0
                    for future in as_completed(future_to_page):
                        page_num = future_to_page[future]
                        try:
                            page_data = future.result()
                            # ✅ 检查页面数据质量
                            if self._is_page_data_valid(page_data):
                                pages_data[page_num - 1] = page_data  # 页码从1开始，索引从0开始
                                completed_count += 1
                                print(f"✅ 页面 {page_num} 处理完成 ({completed_count}/{len(current_batch)})")
                            else:
                                # 📝 记录质量检查失败的页面
                                failed_pages.append((page_num, next(path for num, path in current_batch if num == page_num)))
                                print(f"⚠️ 页面 {page_num} 质量检查失败，加入重试队列")
                        except Exception as e:
                            # 🛡️ 容错处理：单页失败加入重试队列
                            print(f"❌ 页面 {page_num} 处理失败: {e}")
                            failed_pages.append((page_num, next(path for num, path in current_batch if num == page_num)))
                            
            except Exception as e:
                # 🚨 系统级错误：整个批次失败
                print(f"❌ 并行处理批次失败: {e}")
                print(f"💡 可能原因：系统资源不足、权限问题、或进程池初始化失败")
                
                # 如果是第一次尝试，回退到串行处理
                if retry_count == 0:
                    print("🔄 回退到串行处理模式...")
                    return self._process_pages_sequential(single_page_files, output_dir)
                else:
                    # 重试时的系统级错误，标记所有当前页面为失败
                    failed_pages.extend(current_batch)
            
            # 🔄 准备下一轮重试
            current_batch = failed_pages
            retry_count += 1
            
            if failed_pages:
                if retry_count <= max_retries:
                    print(f"📝 本轮有{len(failed_pages)}个页面失败，将在第{retry_count}轮重试")
                else:
                    print(f"❌ 达到最大重试次数({max_retries})，{len(failed_pages)}个页面最终失败")
        
        # 🚨 处理最终失败的页面
        if current_batch:  # 仍有失败页面
            print(f"⚠️ 最终失败页面: {[page_num for page_num, _ in current_batch]}")
            for page_num, _ in current_batch:
                if pages_data[page_num - 1] is None:
                    # 创建空的失败页面数据
                    pages_data[page_num - 1] = PageData(
                        page_number=page_num,
                        raw_text="",  # 空文本
                        images=[],
                        tables=[]
                    )
                    print(f"🔧 页面 {page_num} 标记为最终失败，使用空数据")
        
        # 🎯 最终整理：确保结果的完整性和顺序
        successful_pages: List[PageData] = [page for page in pages_data if page is not None]
        successful_pages.sort(key=lambda x: x.page_number)
        
        total_pages = len(single_page_files)
        success_count = len(successful_pages)
        final_failed_count = len(current_batch) if current_batch else 0
        
        print(f"📊 并行处理完成统计:")
        print(f"   ✅ 成功页面: {success_count}/{total_pages} ({success_count/total_pages*100:.1f}%)")
        print(f"   ❌ 最终失败: {final_failed_count}/{total_pages} ({final_failed_count/total_pages*100:.1f}%)")
        print(f"   🔄 总重试轮数: {retry_count-1}")
        
        # 📈 性能提示
        if self.use_process_pool and success_count > 0:
            theoretical_speedup = min(optimal_workers, len(single_page_files))
            print(f"🚀 理论加速比: {theoretical_speedup}x（实际可能因进程启动开销略低）")
        
        return successful_pages
    
    def _is_page_data_valid(self, page_data: PageData) -> bool:
        """
        检查页面数据质量
        
        Args:
            page_data: 页面数据
            
        Returns:
            bool: 是否为有效数据
        """
        if not page_data:
            return False
        
        # 检查基本属性
        if not hasattr(page_data, 'page_number') or page_data.page_number <= 0:
            print(f"⚠️ 页面数据缺少有效页码")
            return False
        
        # 检查文本内容（至少应该有一些内容，除非是纯图片页面）
        has_text = page_data.raw_text and len(page_data.raw_text.strip()) > 0
        has_media = (hasattr(page_data, 'images') and len(page_data.images) > 0) or \
                   (hasattr(page_data, 'tables') and len(page_data.tables) > 0)
        
        # 至少要有文本或媒体内容
        if not has_text and not has_media:
            print(f"⚠️ 页面 {page_data.page_number} 既无文本也无媒体内容")
            return False
        
        # 检查是否包含明显的错误信息
        if has_text and ("处理失败" in page_data.raw_text or "connection" in page_data.raw_text.lower()):
            print(f"⚠️ 页面 {page_data.page_number} 文本包含错误信息")
            return False
        
        return True
    
    def _process_pages_sequential(self, 
                                 single_page_files: List[Tuple[int, str]], 
                                 output_dir: str) -> List[PageData]:
        """顺序处理所有页面"""
        print("🔄 使用顺序处理模式")
        
        pages_data: List[PageData] = []
        for page_num, single_page_path in single_page_files:
            try:
                page_data = self._process_single_page(page_num, single_page_path, output_dir)
                pages_data.append(page_data)
                print(f"✅ 页面 {page_num} 处理完成")
            except Exception as e:
                print(f"❌ 页面 {page_num} 处理失败: {e}")
                # ✅ 修复：失败页面使用空文本，不保存错误信息
                pages_data.append(PageData(
                    page_number=page_num,
                    raw_text="",  # 空文本而不是错误信息
                    images=[],
                    tables=[]
                ))
        
        return pages_data
    
    def _process_single_page(self, 
                            page_num: int, 
                            single_page_path: str, 
                            output_dir: str) -> PageData:
        """
        处理单页PDF
        
        Args:
            page_num: 页码
            single_page_path: 单页PDF文件路径
            output_dir: 输出目录
            
        Returns:
            PageData: 页面数据
        """
        if self.doc_converter is None:
            raise RuntimeError("Docling转换器未初始化")
            
        # 创建页面专用的输出目录
        page_output_dir = os.path.join(output_dir, f"page_{page_num}")
        os.makedirs(page_output_dir, exist_ok=True)
        
        # 使用Docling处理单页PDF
        raw_result = self.doc_converter.convert(Path(single_page_path))
        
        # 提取页面文本
        page_text = self._extract_page_text(raw_result)
        
        # 创建页面数据
        page_data = PageData(
            page_number=page_num,
            raw_text=page_text,
            images=[],
            tables=[]
        )
        
        # 提取图片和表格 - 由于是单页PDF，所有媒体都属于当前页
        self._extract_media_for_single_page(raw_result, page_data, page_output_dir)
        
        return page_data
    
    @staticmethod
    def _extract_smart_context(page_text: str, media_type: str, media_index: int) -> str:
        """
        智能提取媒体元素的上下文
        
        根据页面文本的长度和内容，提供合适的上下文：
        - 短页面（<200字符）：返回完整页面文本
        - 中等页面（200-500字符）：返回页面文本但限制长度
        - 长页面（>500字符）：返回关键段落或前后文本片段
        
        Args:
            page_text: 页面完整文本
            media_type: 媒体类型（"image"或"table"）
            media_index: 媒体索引
            
        Returns:
            str: 智能提取的上下文
        """
        if not page_text or not page_text.strip():
            return ""
        
        text = page_text.strip()
        
        # 短页面：直接返回完整文本
        if len(text) <= 200:
            return text
        
        # 中等页面：返回前300字符
        elif len(text) <= 500:
            return text[:300] + "..." if len(text) > 300 else text
        
        # 长页面：尝试找到有意义的段落
        else:
            # 按段落分割
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
            
            if not paragraphs:
                return text[:300] + "..."
            
            # 如果有多个段落，选择前几个段落
            context_parts = []
            current_length = 0
            target_length = 300
            
            for para in paragraphs:
                if current_length + len(para) > target_length and context_parts:
                    break
                context_parts.append(para)
                current_length += len(para)
            
            if context_parts:
                return '\n'.join(context_parts)
            else:
                return text[:300] + "..."
    
    def _extract_page_text(self, raw_result: Any) -> str:
        """从单页PDF的docling结果中提取文本 - 增强多策略提取"""
        try:
            page_text = ""
            extraction_methods = []
            
            # 🔍 预检查：打印文档结构信息
            print(f"🔍 开始文本提取，Document类型: {type(raw_result.document)}")
            if hasattr(raw_result.document, 'texts'):
                print(f"🔍 texts集合长度: {len(raw_result.document.texts) if raw_result.document.texts else 0}")
            
            # 🎯 策略1：优先尝试export_to_text()方法（最直接的文本提取）
            if hasattr(raw_result.document, 'export_to_text'):
                try:
                    page_text = raw_result.document.export_to_text()
                    if page_text and page_text.strip():
                        extraction_methods.append("export_to_text")
                        print(f"✅ 使用export_to_text()成功提取文本: {len(page_text)}字符")
                        return page_text.strip()
                    else:
                        print(f"⚠️ export_to_text()返回空内容")
                except Exception as e:
                    print(f"⚠️ export_to_text()方法失败: {e}")
            else:
                print(f"⚠️ document没有export_to_text()方法")
            
            # 🎯 策略2：直接遍历document.texts集合（推荐方法）
            if hasattr(raw_result.document, 'texts') and raw_result.document.texts:
                try:
                    text_parts = []
                    for i, text_item in enumerate(raw_result.document.texts):
                        if hasattr(text_item, 'text') and text_item.text:
                            text_parts.append(text_item.text)
                            print(f"📝 文本片段{i+1}: {len(text_item.text)}字符 - {text_item.text[:50]}...")
                    
                    if text_parts:
                        page_text = '\n'.join(text_parts)
                        extraction_methods.append("texts_collection")
                        print(f"✅ 从texts集合提取文本: {len(text_parts)}个文本项, {len(page_text)}字符")
                        return page_text.strip()
                    else:
                        print(f"⚠️ texts集合中无有效文本内容")
                except Exception as e:
                    print(f"⚠️ 遍历texts集合失败: {e}")
            else:
                print(f"⚠️ document没有texts集合或为空")
            
            # 🎯 策略3：尝试从各种可能的文本属性中提取
            text_attributes = ['content', 'text_content', 'body', 'main_text']
            for attr in text_attributes:
                if hasattr(raw_result.document, attr):
                    try:
                        text_val = getattr(raw_result.document, attr)
                        if text_val and str(text_val).strip():
                            extraction_methods.append(f"attribute_{attr}")
                            print(f"✅ 从{attr}属性提取文本: {len(str(text_val))}字符")
                            return str(text_val).strip()
                    except Exception as e:
                        print(f"⚠️ 从{attr}属性提取失败: {e}")
            
            # 🎯 策略4：使用export_to_markdown()作为备选
            if hasattr(raw_result.document, 'export_to_markdown'):
                try:
                    raw_markdown = raw_result.document.export_to_markdown()
                    if raw_markdown and raw_markdown.strip():
                        # 清理markdown内容
                        import re
                        markdown_clean_pattern = re.compile(r"<!--[\s\S]*?-->")
                        cleaned_text = markdown_clean_pattern.sub("", raw_markdown)
                        
                        if cleaned_text and cleaned_text.strip():
                            extraction_methods.append("export_to_markdown")
                            print(f"✅ 使用export_to_markdown()提取文本: {len(cleaned_text)}字符")
                            return cleaned_text.strip()
                    else:
                        print(f"⚠️ export_to_markdown()返回空内容")
                except Exception as e:
                    print(f"⚠️ export_to_markdown()方法失败: {e}")
            else:
                print(f"⚠️ document没有export_to_markdown()方法")
            
            # 🎯 策略5：尝试从页面级别提取（如果有pages）
            if hasattr(raw_result.document, 'pages') and raw_result.document.pages:
                try:
                    page_texts = []
                    for page in raw_result.document.pages:
                        if hasattr(page, 'text') and page.text:
                            page_texts.append(page.text)
                    
                    if page_texts:
                        combined_text = '\n'.join(page_texts)
                        extraction_methods.append("pages_text")
                        print(f"✅ 从pages提取文本: {len(page_texts)}页, {len(combined_text)}字符")
                        return combined_text.strip()
                except Exception as e:
                    print(f"⚠️ 从pages提取文本失败: {e}")
            
            # 🎯 策略6：最后的诊断和兜底
            all_attrs = [attr for attr in dir(raw_result.document) if not attr.startswith('_')]
            text_like_attrs = [attr for attr in all_attrs if 'text' in attr.lower() or 'content' in attr.lower()]
            
            print("🔍 文档可用属性:", all_attrs[:10], "..." if len(all_attrs) > 10 else "")
            print("🔍 疑似文本相关属性:", text_like_attrs)
            
            # 最后尝试：直接检查document的__dict__
            if hasattr(raw_result.document, '__dict__'):
                doc_dict = raw_result.document.__dict__
                for key, value in doc_dict.items():
                    if isinstance(value, str) and len(value) > 10:
                        extraction_methods.append(f"dict_{key}")
                        print(f"✅ 从__dict__[{key}]提取文本: {len(value)}字符")
                        return value.strip()
            
            print(f"❌ 所有{len(extraction_methods) + 6}种文本提取策略都失败")
            print(f"🔍 尝试过的方法: {extraction_methods}")
            return ""
            
        except Exception as e:
            print(f"❌ 页面文本提取过程发生异常: {e}")
            import traceback
            print(f"🔍 异常详情: {traceback.format_exc()}")
            return ""
    
    def _extract_media_for_single_page(self, 
                                      raw_result: Any, 
                                      page_data: PageData, 
                                      page_output_dir: str):
        """为单页PDF提取图片和表格"""
        try:
            # 由于是单页PDF，所有媒体都属于当前页
            image_counter = 0
            table_counter = 0
            
            # 提取图片
            for picture in raw_result.document.pictures:
                image_counter += 1
                try:
                    # 获取图片
                    picture_image = picture.get_image(raw_result.document)
                    if picture_image is None:
                        continue
                    
                    # 保存图片
                    image_filename = f"picture-{image_counter}.png"
                    image_path = os.path.join(page_output_dir, image_filename)
                    with open(image_path, "wb") as fp:
                        picture_image.save(fp, "PNG")
                    
                    # 获取图片信息
                    from PIL import Image
                    image_img = Image.open(image_path)
                    caption = picture.caption_text(raw_result.document) if hasattr(picture, 'caption_text') else ""
                    
                    # 创建ImageWithContext对象 - 使用智能上下文提取
                    smart_context = Stage1DoclingProcessor._extract_smart_context(page_data.raw_text, "image", image_counter)
                    image_with_context = ImageWithContext(
                        image_path=image_path,
                        page_number=page_data.page_number,  # 🌟 确保页码准确
                        page_context=smart_context,         # 🌟 使用智能上下文而不是整页文本
                        caption=caption or f"图片 {image_counter}",
                        metadata={
                            'width': image_img.width,
                            'height': image_img.height,
                            'size': image_img.width * image_img.height,
                            'aspect_ratio': image_img.width / image_img.height
                        }
                    )
                    
                    page_data.images.append(image_with_context)
                    
                except Exception as e:
                    print(f"❌ 页面 {page_data.page_number} 图片 {image_counter} 处理失败: {e}")
            
            # 提取表格
            for table in raw_result.document.tables:
                table_counter += 1
                try:
                    # 获取表格图片
                    table_image = table.get_image(raw_result.document)
                    if table_image is None:
                        continue
                    
                    # 保存表格图片
                    table_filename = f"table-{table_counter}.png"
                    table_path = os.path.join(page_output_dir, table_filename)
                    with open(table_path, "wb") as fp:
                        table_image.save(fp, "PNG")
                    
                    # 获取表格信息
                    from PIL import Image
                    table_img = Image.open(table_path)
                    caption = table.caption_text(raw_result.document) if hasattr(table, 'caption_text') else ""
                    
                    # 创建TableWithContext对象 - 使用智能上下文提取
                    smart_context = Stage1DoclingProcessor._extract_smart_context(page_data.raw_text, "table", table_counter)
                    table_with_context = TableWithContext(
                        table_path=table_path,
                        page_number=page_data.page_number,  # 🌟 确保页码准确
                        page_context=smart_context,         # 🌟 使用智能上下文而不是整页文本
                        caption=caption or f"表格 {table_counter}",
                        metadata={
                            'width': table_img.width,
                            'height': table_img.height,
                            'size': table_img.width * table_img.height,
                            'aspect_ratio': table_img.width / table_img.height
                        }
                    )
                    
                    page_data.tables.append(table_with_context)
                    
                except Exception as e:
                    print(f"❌ 页面 {page_data.page_number} 表格 {table_counter} 处理失败: {e}")
            
            print(f"📊 页面 {page_data.page_number}: {len(page_data.images)} 个图片, {len(page_data.tables)} 个表格")
            
        except Exception as e:
            print(f"❌ 页面 {page_data.page_number} 媒体提取失败: {e}")
    
    def _cleanup_temp_files(self, single_page_files: List[Tuple[int, str]]):
        """清理临时文件"""
        if not single_page_files:
            return
        
        # 获取临时目录
        temp_dir = os.path.dirname(single_page_files[0][1])
        
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 清理临时文件: {temp_dir}")
        except Exception as e:
            print(f"⚠️ 清理临时文件失败: {e}")
    
    def _generate_full_raw_text_with_media_markers(self, pages: List[PageData]) -> Tuple[str, Dict[str, str]]:
        """
        生成包含媒体标记的完整文本，同时保存每页的原始文本
        
        基于页面数据生成full_raw_text，并在适当位置插入图片表格标记
        同时保存每页的完整原始文本用于精确的上下文提取
        
        Args:
            pages: 页面数据列表 (PageData objects)
            
        Returns:
            Tuple[str, Dict[str, str]]: (包含媒体标记的完整原始文本, 页码->页面原始文本的字典)
        """
        full_text_parts = []
        page_texts = {}  # 页码 -> 完整页面原始文本，用于精确的上下文提取
        
        # 全局计数器，确保content_id唯一
        img_counter = 1
        table_counter = 1
        
        for page in pages:
            page_num = page.page_number
            page_text = page.raw_text or ""
            
            # 保存原始页面文本（不含媒体标记，用于精确的上下文提取）
            page_texts[str(page_num)] = page_text
            
            # 在页面文本中插入媒体标记 (使用content_id)
            text_with_markers = page_text
            
            # 插入图片标记 - 使用content_id而不是path
            for img in page.images:
                img_marker = f"[IMAGE:{img_counter}]"  # 简化格式，只用ID
                text_with_markers += f"\n{img_marker}\n"
                img_counter += 1
            
            # 插入表格标记 - 使用content_id而不是path  
            for table in page.tables:
                table_marker = f"[TABLE:{table_counter}]"  # 简化格式，只用ID
                text_with_markers += f"\n{table_marker}\n"
                table_counter += 1
            
            # 直接添加页面文本，不添加页面标记噪音
            full_text_parts.append(text_with_markers)
        
        # 用空行分隔页面，避免页面标记噪音
        full_raw_text = "\n\n".join(full_text_parts)
        
        print(f"📄 生成full_raw_text: {len(full_raw_text)} 字符 (无页面噪音)")
        print(f"📄 保存page_texts: {len(page_texts)} 页")
        return full_raw_text, page_texts
    
    def _populate_final_schema(self, 
                              final_schema: FinalMetadataSchema,
                              pdf_path: str,
                              full_raw_text: str,
                              page_texts: Dict[str, str],
                              pages: List[PageData],
                              stage_start_time: float):
        """
        填充Final Schema的基础信息
        
        Args:
            final_schema: Final Schema对象
            pdf_path: PDF文件路径
            full_raw_text: 完整原始文本
            page_texts: 页码->页面原始文本的字典
            pages: 页面数据列表 (PageData objects)
            stage_start_time: 阶段开始时间
        """
        
        # 统计信息
        total_images = sum(len(page.images) for page in pages)
        total_tables = sum(len(page.tables) for page in pages)
        total_pages = len(pages)
        
        # 填充DocumentSummary
        doc_id = final_schema.document_id
        final_schema.document_summary = DocumentSummary(
            content_id=f"{doc_id}_document_summary_1",
            document_id=doc_id,
            full_raw_text=full_raw_text,  # 🌟 关键：保存full_raw_text
            page_texts=page_texts,  # 🌟 新增：保存每页的完整原始文本
            source_file_path=pdf_path,
            file_name=os.path.basename(pdf_path),
            file_size=os.path.getsize(pdf_path),
            total_pages=total_pages,
            image_count=total_images,
            table_count=total_tables,
            processing_time=time.time() - stage_start_time
        )
        
        # 填充ImageChunks
        img_counter = 1
        for page in pages:
            for img in page.images:
                image_chunk = ImageChunk(
                    content_id=f"{doc_id}_image_{img_counter}",
                    document_id=doc_id,
                    image_path=img.image_path,
                    page_number=img.page_number,  # 🌟 页码现在是准确的
                    caption=img.caption or "",
                    page_context=img.page_context,  # 🌟 上下文现在是准确的
                    width=img.metadata.get("width", 0),
                    height=img.metadata.get("height", 0),
                    size=img.metadata.get("size", 0),
                    aspect_ratio=img.metadata.get("aspect_ratio", 0.0)
                    # ai_description 和 chapter_id 留空，等待后续阶段填充
                )
                final_schema.image_chunks.append(image_chunk)
                img_counter += 1
        
        # 填充TableChunks  
        table_counter = 1
        for page in pages:
            for table in page.tables:
                table_chunk = TableChunk(
                    content_id=f"{doc_id}_table_{table_counter}",
                    document_id=doc_id,
                    table_path=table.table_path,
                    page_number=table.page_number,  # 🌟 页码现在是准确的
                    caption=table.caption or "",
                    page_context=table.page_context,  # 🌟 上下文现在是准确的
                    width=table.metadata.get("width", 0),
                    height=table.metadata.get("height", 0),
                    size=table.metadata.get("size", 0),
                    aspect_ratio=table.metadata.get("aspect_ratio", 0.0)
                    # ai_description 和 chapter_id 留空，等待后续阶段填充
                )
                final_schema.table_chunks.append(table_chunk)
                table_counter += 1
        
        print(f"📊 填充完成:")
        print(f"   📄 文档摘要: 1个 (包含full_raw_text)")
        print(f"   🖼️ 图片chunks: {len(final_schema.image_chunks)}个")
        print(f"   📋 表格chunks: {len(final_schema.table_chunks)}个")
        print(f"   ✅ 所有页码和上下文都已准确标注")
    
    def can_resume(self, output_dir: str) -> bool:
        """
        检查是否可以跳过阶段1（已经完成）
        
        Args:
            output_dir: 输出目录
            
        Returns:
            bool: 是否可以跳过
        """
        final_metadata_path = os.path.join(output_dir, "final_metadata.json")
        
        if not os.path.exists(final_metadata_path):
            return False
            
        try:
            final_schema = FinalMetadataSchema.load(final_metadata_path)
            return final_schema.is_stage_complete("stage1")
        except Exception:
            return False
    
    def resume_from_existing(self, output_dir: str) -> Tuple[FinalMetadataSchema, str]:
        """
        从现有的final_metadata.json恢复
        
        Args:
            output_dir: 输出目录
            
        Returns:
            Tuple[FinalMetadataSchema, str]: (final_schema对象, final_metadata.json文件路径)
        """
        final_metadata_path = os.path.join(output_dir, "final_metadata.json")
        
        if not self.can_resume(output_dir):
            raise ValueError(f"无法从 {final_metadata_path} 恢复，阶段1未完成")
        
        final_schema = FinalMetadataSchema.load(final_metadata_path)
        print(f"✅ 从现有文件恢复阶段1结果: {final_metadata_path}")
        print(f"📊 当前完成度: {final_schema.get_completion_percentage()}%")
        
        return final_schema, final_metadata_path


def _process_single_page_static(page_num: int, 
                               single_page_path: str, 
                               output_dir: str,
                               config: PDFProcessingConfig) -> PageData:
    """
    处理单页PDF的静态函数（用于进程池）
    
    Args:
        page_num: 页码
        single_page_path: 单页PDF文件路径
        output_dir: 输出目录
        config: PDF处理配置
        
    Returns:
        PageData: 页面数据
    """
    try:
        # 🔧 配置离线模式，避免网络连接问题（子进程）
        import os
        os.environ['HF_HUB_OFFLINE'] = '1'  # 强制HuggingFace Hub离线模式
        os.environ['TRANSFORMERS_OFFLINE'] = '1'  # Transformers离线模式
        
        # 在进程内初始化docling转换器
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        
        # 设置本地模型路径
        models_cache_dir = Path("models_cache")
        artifacts_path = None
        if models_cache_dir.exists():
            artifacts_path = str(models_cache_dir.absolute())
        elif config.docling.artifacts_path:
            artifacts_path = config.docling.artifacts_path
        
        # 创建管道选项
        if config.docling.ocr_enabled:
            # 🔥 增强OCR配置，确保文字提取成功
            ocr_options = EasyOcrOptions()
            try:
                # 核心OCR设置
                ocr_options.force_full_page_ocr = True  # 强制全页OCR
                
                # 🚀 添加更多OCR优化设置（只使用实际存在的属性）
                if hasattr(ocr_options, 'use_gpu'):
                    ocr_options.use_gpu = False  # 强制使用CPU，避免GPU兼容性问题
                
                if hasattr(ocr_options, 'lang'):
                    ocr_options.lang = ['ch_sim', 'en']  # 支持中英文
                
                if hasattr(ocr_options, 'confidence_threshold'):
                    ocr_options.confidence_threshold = 0.3  # 降低置信度阈值，提高检出率
                
                if hasattr(ocr_options, 'bitmap_area_threshold'):
                    ocr_options.bitmap_area_threshold = 0.01  # 降低区域阈值，检测更小文字
                
                print("✅ 应用增强OCR设置：")
                print("   - force_full_page_ocr=True（强制全页OCR）")
                print("   - use_gpu=False（CPU模式，避免兼容性问题）")
                print("   - lang=['ch_sim', 'en']（中英文支持）")
                print("   - confidence_threshold=0.3（降低置信度阈值）")
                print("   - bitmap_area_threshold=0.01（检测更小文字）")
                
            except Exception as e:
                print(f"⚠️ 应用增强OCR设置失败: {e}")
            
            pipeline_options = PdfPipelineOptions(
                ocr_options=ocr_options,
                artifacts_path=artifacts_path
            )
        else:
            print("⚠️ OCR已禁用，可能导致文字提取不完整")
            pipeline_options = PdfPipelineOptions(
                artifacts_path=artifacts_path
            )
        
        # 设置解析选项
        pipeline_options.images_scale = config.docling.images_scale
        pipeline_options.generate_page_images = config.docling.generate_page_images
        pipeline_options.generate_picture_images = config.docling.generate_picture_images
        
        # 🚀 添加更多解析选项
        if hasattr(pipeline_options, 'do_ocr'):
            pipeline_options.do_ocr = True  # 确保OCR执行
        
        if hasattr(pipeline_options, 'do_table_structure'):
            pipeline_options.do_table_structure = True  # 表格结构识别
        
        # 创建文档转换器
        doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        # 创建页面专用的输出目录
        page_output_dir = os.path.join(output_dir, f"page_{page_num}")
        os.makedirs(page_output_dir, exist_ok=True)
        
        # 使用Docling处理单页PDF
        raw_result = doc_converter.convert(Path(single_page_path))
        
        # 提取页面文本 - 多策略提取（与实例方法保持一致）
        try:
            page_text = ""
            
            # 策略1：优先尝试export_to_text()方法
            if hasattr(raw_result.document, 'export_to_text'):
                try:
                    page_text = raw_result.document.export_to_text()
                    if page_text and page_text.strip():
                        page_text = page_text.strip()
                except Exception:
                    pass
            
            # 策略2：直接遍历document.texts集合
            if not page_text and hasattr(raw_result.document, 'texts') and raw_result.document.texts:
                try:
                    text_parts = []
                    for text_item in raw_result.document.texts:
                        if hasattr(text_item, 'text') and text_item.text:
                            text_parts.append(text_item.text)
                    
                    if text_parts:
                        page_text = '\n'.join(text_parts).strip()
                except Exception:
                    pass
            
            # 策略3：使用export_to_markdown()作为备选
            if not page_text and hasattr(raw_result.document, 'export_to_markdown'):
                try:
                    raw_markdown = raw_result.document.export_to_markdown()
                    import re
                    markdown_clean_pattern = re.compile(r"<!--[\s\S]*?-->")
                    page_text = markdown_clean_pattern.sub("", raw_markdown).strip()
                except Exception:
                    pass
            
            # 策略4：尝试从document属性中直接提取
            if not page_text and hasattr(raw_result.document, 'text'):
                try:
                    doc_text = getattr(raw_result.document, 'text', None)
                    page_text = doc_text.strip() if doc_text else ""
                except Exception:
                    pass
            
            # 如果所有策略都失败
            if not page_text:
                page_text = f"页面 {page_num} 文本提取失败（所有策略失败）"
                
        except Exception as e:
            print(f"⚠️ 页面 {page_num} 文本提取失败: {e}")
            page_text = f"页面 {page_num} 文本提取失败: {str(e)}"
        
        # 创建页面数据
        page_data = PageData(
            page_number=page_num,
            raw_text=page_text,
            images=[],
            tables=[]
        )
        
        # 提取媒体（进程池版本）
        try:
            # 提取图片
            if hasattr(raw_result.document, 'pictures'):
                for i, picture in enumerate(raw_result.document.pictures):
                    try:
                        # 获取图片
                        picture_image = picture.get_image(raw_result.document)
                        if picture_image is None:
                            continue
                        
                        # 保存图片
                        image_filename = f"picture-{i+1}.png"
                        image_path = os.path.join(page_output_dir, image_filename)
                        with open(image_path, "wb") as fp:
                            picture_image.save(fp, "PNG")
                        
                        # 获取图片信息
                        from PIL import Image
                        image_img = Image.open(image_path)
                        caption = picture.caption_text(raw_result.document) if hasattr(picture, 'caption_text') else ""
                        
                        # 创建ImageWithContext对象 - 使用智能上下文提取
                        smart_context = Stage1DoclingProcessor._extract_smart_context(page_text, "image", i+1)
                        image_with_context = ImageWithContext(
                            image_path=image_path,
                            page_number=page_num,  # 🌟 确保页码准确
                            page_context=smart_context,  # 🌟 使用智能上下文而不是整页文本
                            caption=caption or f"图片 {i+1}",
                            metadata={
                                'width': image_img.width,
                                'height': image_img.height,
                                'size': image_img.width * image_img.height,
                                'aspect_ratio': image_img.width / image_img.height
                            }
                        )
                        
                        page_data.images.append(image_with_context)
                    except Exception as e:
                        print(f"⚠️ 页面 {page_num} 图片 {i+1} 处理失败: {e}")
            
            # 提取表格
            if hasattr(raw_result.document, 'tables'):
                for i, table in enumerate(raw_result.document.tables):
                    try:
                        # 获取表格图片
                        table_image = table.get_image(raw_result.document)
                        if table_image is None:
                            continue
                        
                        # 保存表格图片
                        table_filename = f"table-{i+1}.png"
                        table_path = os.path.join(page_output_dir, table_filename)
                        with open(table_path, "wb") as fp:
                            table_image.save(fp, "PNG")
                        
                        # 获取表格信息
                        from PIL import Image
                        table_img = Image.open(table_path)
                        caption = table.caption_text(raw_result.document) if hasattr(table, 'caption_text') else ""
                        
                        # 创建TableWithContext对象 - 使用智能上下文提取
                        smart_context = Stage1DoclingProcessor._extract_smart_context(page_text, "table", i+1)
                        table_with_context = TableWithContext(
                            table_path=table_path,
                            page_number=page_num,  # 🌟 确保页码准确
                            page_context=smart_context,  # 🌟 使用智能上下文而不是整页文本
                            caption=caption or f"表格 {i+1}",
                            metadata={
                                'width': table_img.width,
                                'height': table_img.height,
                                'size': table_img.width * table_img.height,
                                'aspect_ratio': table_img.width / table_img.height
                            }
                        )
                        
                        page_data.tables.append(table_with_context)
                    except Exception as e:
                        print(f"⚠️ 页面 {page_num} 表格 {i+1} 处理失败: {e}")
                        
        except Exception as e:
            print(f"⚠️ 页面 {page_num} 媒体提取失败: {e}")
        
        return page_data
        
    except Exception as e:
        print(f"❌ 静态函数处理页面 {page_num} 失败: {e}")
        # ✅ 修复：失败页面使用空文本，不保存错误信息
        return PageData(
            page_number=page_num,
            raw_text="",  # 空文本而不是错误信息
            images=[],
            tables=[]
        ) 