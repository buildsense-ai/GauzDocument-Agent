#!/usr/bin/env python3
"""
MinIO客户端配置和文件上传功能
用于将用户上传的PDF文件自动上传到MinIO存储
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from minio import Minio
from minio.error import S3Error
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinIOUploader:
    """MinIO文件上传器"""
    
    def __init__(self, endpoint: str = "43.139.19.144:9000", 
                 access_key: str = "minioadmin", 
                 secret_key: str = "minioadmin",
                 secure: bool = False):
        """
        初始化MinIO客户端
        
        Args:
            endpoint: MinIO服务器地址
            access_key: 访问密钥
            secret_key: 秘密密钥
            secure: 是否使用HTTPS
        """
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.bucket_name = "useruploadedtobeparsed"
        
        # 初始化MinIO客户端
        try:
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            logger.info(f"✅ MinIO客户端初始化成功: {self.endpoint}")
            
            # 确保bucket存在
            self._ensure_bucket_exists()
            
        except Exception as e:
            logger.error(f"❌ MinIO客户端初始化失败: {e}")
            self.client = None
    
    def _ensure_bucket_exists(self):
        """确保bucket存在，如果不存在则创建"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"✅ 创建bucket: {self.bucket_name}")
            else:
                logger.info(f"✅ Bucket已存在: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"❌ Bucket操作失败: {e}")
    
    def upload_pdf(self, file_path: str, original_filename: str, 
                   project_id: str = None) -> Optional[str]:
        """
        上传PDF文件到MinIO
        
        Args:
            file_path: 本地文件路径
            original_filename: 原始文件名
            project_id: 项目ID（可选）
            
        Returns:
            MinIO路径 (格式: minio://bucket/object_name) 或 None
        """
        if not self.client:
            logger.error("❌ MinIO客户端未初始化")
            return None
            
        try:
            # 验证文件存在
            if not os.path.exists(file_path):
                logger.error(f"❌ 文件不存在: {file_path}")
                return None
            
            # 验证是PDF文件
            if not original_filename.lower().endswith('.pdf'):
                logger.error(f"❌ 不是PDF文件: {original_filename}")
                return None
            
            # 生成唯一的对象名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            
            # 构建对象名: 项目ID/时间戳_唯一ID_原始文件名
            if project_id:
                object_name = f"{project_id}/{timestamp}_{unique_id}_{original_filename}"
            else:
                object_name = f"default/{timestamp}_{unique_id}_{original_filename}"
            
            # 上传文件
            logger.info(f"🚀 开始上传: {original_filename} -> {object_name}")
            
            with open(file_path, 'rb') as file_data:
                file_stat = os.stat(file_path)
                self.client.put_object(
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    data=file_data,
                    length=file_stat.st_size,
                    content_type='application/pdf'
                )
            
            # 构建MinIO路径
            minio_path = f"minio://{self.bucket_name}/{object_name}"
            logger.info(f"✅ 上传成功: {minio_path}")
            
            return minio_path
            
        except S3Error as e:
            logger.error(f"❌ MinIO上传失败: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 上传过程中出错: {e}")
            return None
    
    
    
    def get_file_info(self, minio_path: str) -> Optional[Dict[str, Any]]:
        """
        获取MinIO中文件的信息
        
        Args:
            minio_path: MinIO路径
            
        Returns:
            文件信息字典或None
        """
        if not self.client:
            return None
            
        try:
            # 解析路径
            if not minio_path.startswith("minio://"):
                return None
                
            path_parts = minio_path.replace("minio://", "").split("/", 1)
            if len(path_parts) != 2:
                return None
                
            bucket_name, object_name = path_parts
            
            # 获取对象信息
            stat = self.client.stat_object(bucket_name, object_name)
            
            return {
                "size": stat.size,
                "last_modified": stat.last_modified,
                "content_type": stat.content_type,
                "etag": stat.etag,
                "object_name": object_name
            }
            
        except Exception as e:
            logger.error(f"❌ 获取文件信息失败: {e}")
            return None
    
    def test_connection(self) -> bool:
        """测试MinIO连接"""
        if not self.client:
            return False
            
        try:
            # 列出buckets来测试连接
            buckets = self.client.list_buckets()
            logger.info(f"✅ MinIO连接测试成功，发现 {len(buckets)} 个buckets")
            return True
        except Exception as e:
            logger.error(f"❌ MinIO连接测试失败: {e}")
            return False


# 全局MinIO上传器实例
minio_uploader = None

def get_minio_uploader() -> Optional[MinIOUploader]:
    """获取全局MinIO上传器实例"""
    global minio_uploader
    if minio_uploader is None:
        minio_uploader = MinIOUploader()
    return minio_uploader

def upload_pdf_to_minio(file_path: str, original_filename: str, 
                       project_id: str = None) -> Optional[str]:
    """
    便捷函数：上传PDF到MinIO
    
    Args:
        file_path: 本地文件路径
        original_filename: 原始文件名
        project_id: 项目ID
        
    Returns:
        MinIO路径或None
    """
    uploader = get_minio_uploader()
    if uploader:
        return uploader.upload_pdf(file_path, original_filename, project_id)
    return None

if __name__ == "__main__":
    # 测试代码
    uploader = MinIOUploader()
    if uploader.test_connection():
        print("🎉 MinIO连接测试成功！")
    else:
        print("❌ MinIO连接测试失败！") 