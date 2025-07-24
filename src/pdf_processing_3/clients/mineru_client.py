"""
Mineru API Client for PDF Processing V3

Mineru外部服务客户端，负责：
- PDF文件上传
- 处理状态查询  
- 结果获取和解析
- 配额管理和限制检查
- 错误处理和重试机制
"""

import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import hashlib
import time

from ..models.final_schema_v3 import FinalMetadataSchemaV3, DocumentSummaryV3, TextChunkV3, ImageChunkV3, TableChunkV3, generate_content_id

logger = logging.getLogger(__name__)


class MineruQuotaManager:
    """Mineru配额管理器"""
    
    def __init__(self):
        self.daily_quota_limit = 2000  # 每日高优先级配额
        self.file_size_limit = 200 * 1024 * 1024  # 200MB文件大小限制
        self.page_limit = 600  # 600页限制
        
        # 当日使用统计
        self.today = datetime.now().date()
        self.daily_quota_used = 0
        self.total_pages_processed = 0
        
    def reset_daily_stats_if_needed(self):
        """如果需要，重置每日统计"""
        today = datetime.now().date()
        if today != self.today:
            self.today = today
            self.daily_quota_used = 0
            self.total_pages_processed = 0
            logger.info("每日配额统计已重置")
    
    def check_file_limits(self, file_path: str) -> Tuple[bool, str]:
        """
        检查文件是否满足Mineru限制
        
        Returns:
            (是否通过检查, 错误信息)
        """
        file_path_obj = Path(file_path)
        
        # 检查文件是否存在
        if not file_path_obj.exists():
            return False, f"文件不存在: {file_path}"
        
        # 检查文件大小
        file_size = file_path_obj.stat().st_size
        if file_size > self.file_size_limit:
            size_mb = file_size / (1024 * 1024)
            return False, f"文件大小超限: {size_mb:.1f}MB > 200MB"
        
        # TODO: 检查PDF页数（需要实际读取PDF）
        # 这里可以添加页数检查逻辑
        
        return True, ""
    
    def check_quota_available(self, estimated_pages: int = 0) -> Tuple[bool, str]:
        """
        检查配额是否可用
        
        Args:
            estimated_pages: 预估页数
            
        Returns:
            (是否有可用配额, 状态信息)
        """
        self.reset_daily_stats_if_needed()
        
        if self.daily_quota_used >= self.daily_quota_limit:
            return False, f"已超出每日高优先级配额: {self.daily_quota_used}/{self.daily_quota_limit}"
        
        remaining = self.daily_quota_limit - self.daily_quota_used
        if estimated_pages > remaining:
            return False, f"预估页数超过剩余配额: {estimated_pages} > {remaining}"
        
        return True, f"配额可用，剩余: {remaining}"
    
    def record_usage(self, pages_processed: int):
        """记录使用量"""
        self.daily_quota_used += pages_processed
        self.total_pages_processed += pages_processed
        logger.info(f"配额使用记录: +{pages_processed}页，当日总计: {self.daily_quota_used}/{self.daily_quota_limit}")


class MineruClient:
    """
    Mineru API客户端
    
    基于用户提供的API信息：
    - API地址: https://mineru.net/apiManage
    - 认证: Access Key + Secret Key  
    - 限制: 200MB文件，600页，每日2000页高优先级配额
    """
    
    def __init__(self, access_key: str, secret_key: str, base_url: str = "https://api.mineru.net"):
        """
        初始化Mineru客户端
        
        Args:
            access_key: Mineru访问密钥
            secret_key: Mineru密钥
            base_url: API基础URL（待确认实际地址）
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip('/')
        
        # 配额管理器
        self.quota_manager = MineruQuotaManager()
        
        # HTTP会话
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 2  # 秒
        
        logger.info(f"MineruClient初始化完成，API地址: {self.base_url}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """关闭客户端和HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _generate_auth_headers(self) -> Dict[str, str]:
        """
        生成认证头
        
        注意：这里的认证方式需要根据Mineru实际API文档调整
        """
        timestamp = str(int(time.time()))
        
        # 创建签名（具体格式待确认）
        sign_string = f"{self.access_key}{timestamp}{self.secret_key}"
        signature = hashlib.md5(sign_string.encode()).hexdigest()
        
        return {
            "Authorization": f"Bearer {self.access_key}",
            "X-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
    
    async def upload_pdf(self, file_path: str, project_id: str, **kwargs) -> str:
        """
        上传PDF文件到Mineru
        
        Args:
            file_path: PDF文件路径
            project_id: 项目ID（用于本地追踪）
            **kwargs: 其他上传参数
            
        Returns:
            Mineru任务ID
            
        Raises:
            ValueError: 文件检查失败
            Exception: 上传失败
        """
        await self._ensure_session()
        
        # 检查文件限制
        valid, error_msg = self.quota_manager.check_file_limits(file_path)
        if not valid:
            raise ValueError(f"文件检查失败: {error_msg}")
        
        # 检查配额
        valid, quota_msg = self.quota_manager.check_quota_available()
        if not valid:
            raise ValueError(f"配额检查失败: {quota_msg}")
        
        logger.info(f"开始上传PDF: {file_path}")
        
        # 准备上传数据
        headers = self._generate_auth_headers()
        upload_url = f"{self.base_url}/upload"  # 实际endpoint待确认
        
        # 读取文件
        async with aiofiles.open(file_path, 'rb') as f:
            file_data = await f.read()
        
        # 构建multipart/form-data
        form_data = aiohttp.FormData()
        form_data.add_field('file', file_data, 
                           filename=Path(file_path).name,
                           content_type='application/pdf')
        form_data.add_field('project_id', project_id)
        
        # 移除Content-Type，让aiohttp自动设置multipart边界
        headers.pop('Content-Type', None)
        
        # 发送请求
        try:
            async with self.session.post(upload_url, data=form_data, headers=headers) as response:
                response.raise_for_status()
                result = await response.json()
                
                # 提取任务ID（格式待确认）
                task_id = result.get('task_id') or result.get('id')
                if not task_id:
                    raise Exception(f"响应中未找到任务ID: {result}")
                
                logger.info(f"PDF上传成功，任务ID: {task_id}")
                return task_id
                
        except Exception as e:
            logger.error(f"PDF上传失败: {e}")
            raise
    
    async def get_processing_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询处理状态
        
        Args:
            task_id: Mineru任务ID
            
        Returns:
            状态信息字典
        """
        await self._ensure_session()
        
        headers = self._generate_auth_headers()
        status_url = f"{self.base_url}/status/{task_id}"  # 实际endpoint待确认
        
        try:
            async with self.session.get(status_url, headers=headers) as response:
                response.raise_for_status()
                result = await response.json()
                
                # 标准化状态格式
                status = {
                    'task_id': task_id,
                    'state': result.get('status', 'unknown'),  # 'pending', 'processing', 'completed', 'failed'
                    'progress': result.get('progress', 0),
                    'message': result.get('message', ''),
                    'error': result.get('error'),
                    'estimated_time': result.get('estimated_time'),
                    'pages_processed': result.get('pages_processed', 0)
                }
                
                return status
                
        except Exception as e:
            logger.error(f"状态查询失败: {e}")
            return {
                'task_id': task_id,
                'state': 'error',
                'error': str(e)
            }
    
    async def get_result(self, task_id: str) -> Dict[str, Any]:
        """
        获取处理结果
        
        Args:
            task_id: Mineru任务ID
            
        Returns:
            完整的处理结果
        """
        await self._ensure_session()
        
        headers = self._generate_auth_headers()
        result_url = f"{self.base_url}/result/{task_id}"  # 实际endpoint待确认
        
        try:
            async with self.session.get(result_url, headers=headers) as response:
                response.raise_for_status()
                result = await response.json()
                
                # 记录配额使用
                pages_processed = result.get('document_info', {}).get('total_pages', 0)
                if pages_processed > 0:
                    self.quota_manager.record_usage(pages_processed)
                
                logger.info(f"获取处理结果成功，任务ID: {task_id}")
                return result
                
        except Exception as e:
            logger.error(f"获取处理结果失败: {e}")
            raise
    
    async def wait_for_completion(self, task_id: str, max_wait_time: int = 600, poll_interval: int = 10) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            task_id: 任务ID
            max_wait_time: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）
            
        Returns:
            最终状态信息
        """
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait_time:
            status = await self.get_processing_status(task_id)
            
            if status['state'] in ['completed', 'failed', 'error']:
                return status
            
            logger.info(f"任务进行中: {task_id}, 状态: {status['state']}, 进度: {status.get('progress', 0)}%")
            await asyncio.sleep(poll_interval)
        
        # 超时
        return {
            'task_id': task_id,
            'state': 'timeout',
            'error': f'等待超时（{max_wait_time}秒）'
        }
    
    def parse_mineru_output(self, raw_output: Dict[str, Any], project_id: str) -> FinalMetadataSchemaV3:
        """
        解析Mineru输出，转换为V3 Schema
        
        Args:
            raw_output: Mineru返回的原始JSON数据
            project_id: 项目ID
            
        Returns:
            填充的V3 Schema对象
            
        注意：此方法需要根据Mineru实际返回格式调整
        """
        logger.info("开始解析Mineru输出数据")
        
        # 提取文档基础信息
        doc_info = raw_output.get('document_info', {})
        task_id = raw_output.get('task_id')
        
        # 创建DocumentSummary
        doc_summary = DocumentSummaryV3(
            rtr_project_id=project_id,
            rtr_source_path=doc_info.get('source_file', ''),
            rtr_file_name=doc_info.get('file_name', ''),
            prc_mineru_raw_output=raw_output,
            ana_total_pages=doc_info.get('total_pages', 0),
            ana_file_size=doc_info.get('file_size', 0),
            sys_mineru_task_id=task_id
        )
        
        document_id = doc_summary.rtr_document_id
        
        # 解析chunks（格式待确认）
        chunks = raw_output.get('chunks', [])
        text_chunks = []
        image_chunks = []
        table_chunks = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = chunk.get('chunk_id', f"chunk_{i}")
            chunk_type = chunk.get('type', 'unknown')
            
            base_fields = {
                'rtr_document_id': document_id,
                'rtr_project_id': project_id,
                'rtr_mineru_chunk_id': chunk_id,
                'rtr_sequence_index': i
            }
            
            if chunk_type == 'text':
                text_chunk = TextChunkV3(
                    content_id=generate_content_id(),
                    emb_content=chunk.get('content', ''),
                    ana_word_count=len(chunk.get('content', '')),
                    **base_fields
                )
                text_chunks.append(text_chunk)
                
            elif chunk_type == 'image':
                image_chunk = ImageChunkV3(
                    content_id=generate_content_id(),
                    rtr_media_path=chunk.get('image_path', ''),
                    rtr_caption=chunk.get('caption', ''),
                    prc_mineru_metadata=chunk.get('metadata', {}),
                    ana_width=chunk.get('width', 0),
                    ana_height=chunk.get('height', 0),
                    **base_fields
                )
                image_chunks.append(image_chunk)
                
            elif chunk_type == 'table':
                table_chunk = TableChunkV3(
                    content_id=generate_content_id(),
                    rtr_media_path=chunk.get('table_image_path', ''),
                    rtr_caption=chunk.get('caption', ''),
                    prc_mineru_metadata=chunk.get('metadata', {}),
                    prc_raw_table_data=chunk.get('table_data', []),
                    ana_rows=len(chunk.get('table_data', [])),
                    ana_columns=len(chunk.get('table_data', [[]])[0]) if chunk.get('table_data') else 0,
                    **base_fields
                )
                table_chunks.append(table_chunk)
        
        # 更新DocumentSummary统计
        doc_summary.ana_image_count = len(image_chunks)
        doc_summary.ana_table_count = len(table_chunks)
        doc_summary.ana_word_count = sum(chunk.ana_word_count for chunk in text_chunks)
        
        # 构建完整Schema
        schema = FinalMetadataSchemaV3(
            document_id=document_id,
            project_id=project_id,
            document_summary=doc_summary,
            text_chunks=text_chunks,
            image_chunks=image_chunks,
            table_chunks=table_chunks
        )
        
        logger.info(f"Mineru输出解析完成: {len(text_chunks)}文本块, {len(image_chunks)}图片, {len(table_chunks)}表格")
        return schema
    
    def get_quota_status(self) -> Dict[str, Any]:
        """获取配额状态信息"""
        self.quota_manager.reset_daily_stats_if_needed()
        
        return {
            "daily_limit": self.quota_manager.daily_quota_limit,
            "daily_used": self.quota_manager.daily_quota_used,
            "daily_remaining": self.quota_manager.daily_quota_limit - self.quota_manager.daily_quota_used,
            "file_size_limit_mb": self.quota_manager.file_size_limit / (1024 * 1024),
            "page_limit": self.quota_manager.page_limit,
            "total_pages_processed": self.quota_manager.total_pages_processed,
            "date": self.quota_manager.today.isoformat()
        } 