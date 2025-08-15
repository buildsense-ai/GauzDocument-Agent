#!/usr/bin/env python3
"""
MinIO客户端配置和文件上传功能
用于将用户上传的PDF文件自动上传到MinIO存储
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
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
                   project_id: str = None, verify_checksum: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """
        上传PDF文件到MinIO (增强版验证)
        
        Args:
            file_path: 本地文件路径
            original_filename: 原始文件名
            project_id: 项目ID（可选）
            verify_checksum: 是否验证文件校验和
            
        Returns:
            Tuple[MinIO路径或None, 错误信息或None]
        """
        if not self.client:
            error_msg = "MinIO客户端未初始化"
            logger.error(f"❌ {error_msg}")
            return None, error_msg
            
        try:
            # 验证文件存在
            if not os.path.exists(file_path):
                error_msg = f"文件不存在: {file_path}"
                logger.error(f"❌ {error_msg}")
                return None, error_msg
            
            # 验证是PDF文件
            if not original_filename.lower().endswith('.pdf'):
                error_msg = f"不是PDF文件: {original_filename}"
                logger.error(f"❌ {error_msg}")
                return None, error_msg
            
            # 获取原始文件大小和校验和
            file_stat = os.stat(file_path)
            original_size = file_stat.st_size
            logger.info(f"📄 原始文件大小: {original_size} 字节")
            
            # 可选：计算文件MD5校验和
            original_md5 = None
            if verify_checksum:
                logger.info(f"🔢 计算文件MD5校验和...")
                original_md5 = self._calculate_md5(file_path)
                logger.info(f"🔢 原始文件MD5: {original_md5}")
            
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
                self.client.put_object(
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    data=file_data,
                    length=original_size,
                    content_type='application/pdf'
                )
            
            logger.info(f"📤 put_object 调用完成，开始验证上传结果...")
            
            # 🆕 重要：验证上传是否真正完成
            upload_verified, verify_error = self._verify_upload(object_name, original_size, original_filename, original_md5)
            if not upload_verified:
                error_msg = f"上传验证失败: {verify_error}"
                logger.error(f"❌ {error_msg}")
                return None, error_msg
            
            # 构建MinIO路径
            minio_path = f"minio://{self.bucket_name}/{object_name}"
            logger.info(f"✅ 上传并验证成功: {minio_path}")
            
            return minio_path, None
            
        except S3Error as e:
            error_msg = f"MinIO操作失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"上传过程中出错: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return None, error_msg
    
    def _calculate_md5(self, file_path: str) -> str:
        """计算文件的MD5校验和"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _verify_upload(self, object_name: str, expected_size: int, original_filename: str, expected_md5: str = None) -> Tuple[bool, Optional[str]]:
        """
        验证文件是否真正上传完成
        
        Args:
            object_name: MinIO中的对象名
            expected_size: 期望的文件大小
            original_filename: 原始文件名（用于日志）
            expected_md5: 期望的MD5校验和（可选）
            
        Returns:
            Tuple[验证是否通过, 错误信息]
        """
        try:
            logger.info(f"🔍 开始验证上传: {original_filename}")
            
            # 1. 检查文件是否存在
            try:
                stat_result = self.client.stat_object(self.bucket_name, object_name)
                logger.info(f"📊 MinIO中文件状态: 大小={stat_result.size}, ETag={stat_result.etag}")
            except Exception as e:
                error_msg = f"文件不存在于MinIO中: {object_name}, 错误: {e}"
                logger.error(f"❌ {error_msg}")
                return False, error_msg
            
            # 2. 验证文件大小
            actual_size = stat_result.size
            if actual_size != expected_size:
                error_msg = f"文件大小不匹配: 期望={expected_size}, 实际={actual_size}"
                logger.error(f"❌ {error_msg}")
                return False, error_msg
            
            logger.info(f"✅ 文件大小验证通过: {actual_size} 字节")
            
            # 3. 验证内容类型
            if stat_result.content_type != 'application/pdf':
                logger.warning(f"⚠️ 内容类型异常: {stat_result.content_type} (期望: application/pdf)")
                # 不作为错误，只是警告
            
            # 4. 验证ETag是否存在（表示完整性）
            if not stat_result.etag:
                error_msg = "没有ETag，可能上传不完整"
                logger.warning(f"⚠️ {error_msg}")
                return False, error_msg
            
            # 5. 可选：验证MD5校验和
            if expected_md5:
                # MinIO的ETag对于简单上传是MD5值，对于分片上传是不同的格式
                actual_etag = stat_result.etag.strip('"')  # 移除引号
                
                # 🔧 检测是否为分片上传（ETag包含 "-数字" 后缀）
                if '-' in actual_etag and actual_etag.split('-')[-1].isdigit():
                    logger.info(f"🔀 检测到分片上传，ETag: {actual_etag}")
                    logger.info(f"✅ 跳过MD5校验，分片上传由MinIO保证完整性")
                else:
                    # 简单上传，可以直接比较MD5
                    if actual_etag != expected_md5:
                        error_msg = f"MD5校验和不匹配: 期望={expected_md5}, 实际={actual_etag}"
                        logger.error(f"❌ {error_msg}")
                        return False, error_msg
                    logger.info(f"✅ MD5校验和验证通过: {actual_etag}")
            else:
                logger.info(f"✅ 跳过MD5校验（未启用）")
            
            logger.info(f"🎉 上传验证完全通过: {original_filename}")
            return True, None
            
        except Exception as e:
            error_msg = f"验证过程中出错: {e}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def delete_object_by_path(self, minio_path: str) -> Tuple[bool, Optional[str]]:
        """
        通过 minio_path 删除对象，例如: minio://bucket/object_name
        返回 (是否成功, 错误信息)
        """
        if not self.client:
            return False, "MinIO客户端未初始化"
        try:
            if not minio_path or not minio_path.startswith("minio://"):
                return False, "无效的minio_path"
            path_parts = minio_path.replace("minio://", "").split("/", 1)
            if len(path_parts) != 2:
                return False, "无效的minio_path"
            bucket_name, object_name = path_parts
            self.client.remove_object(bucket_name=bucket_name, object_name=object_name)
            logger.info(f"🗑️ 已从MinIO删除对象: {minio_path}")
            return True, None
        except Exception as e:
            error_msg = f"删除MinIO对象失败: {e}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
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
                       project_id: str = None, verify_checksum: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """
    便捷函数：上传PDF到MinIO (增强版)
    
    Args:
        file_path: 本地文件路径
        original_filename: 原始文件名
        project_id: 项目ID
        verify_checksum: 是否验证校验和
        
    Returns:
        Tuple[MinIO路径或None, 错误信息或None]
    """
    uploader = get_minio_uploader()
    if uploader:
        return uploader.upload_pdf(file_path, original_filename, project_id, verify_checksum)
    return None, "MinIO上传器初始化失败"

if __name__ == "__main__":
    # 测试代码
    uploader = MinIOUploader()
    if uploader.test_connection():
        print("🎉 MinIO连接测试成功！")
    else:
        print("❌ MinIO连接测试失败！") 