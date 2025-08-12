from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from minio.commonconfig import CopySource
from minio.error import S3Error
import logging
import io
import os

# 这是一个假设，我们假设主应用中有一个已经配置好的minio_client实例
# 通常这个实例会在应用的入口文件（如main.py）中创建并传递
# 这里我们先从上级目录的minio_client.py导入
try:
    from ..minio_client import minio_client
except (ImportError, ValueError):
    # 如果直接运行此文件或结构不同，提供一个备用方案
    from minio import Minio
    logging.warning("Could not import minio_client from parent, creating a new instance.")
    minio_client = Minio(
        os.getenv("MINIO_API_HOST", "43.139.19.144:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False
    )


router = APIRouter()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUCKET_NAME = "vertioncontrol"
ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "text/markdown": ".md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"
}

@router.post("/api/uploadwithversion", tags=["File Upload with Versioning"])
async def upload_with_versioning(file: UploadFile = File(...)):
    """
    将文件（PDF、Markdown或DOCX）上传到启用了版本控制的MinIO存储桶。
    如果存储桶不存在，则会自动创建并启用版本控制。
    """
    # 1. 验证文件类型
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning(f"上传了无效的文件类型: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"文件类型无效。只允许上传 PDF, Markdown, 和 DOCX。当前类型为 {file.content_type}"
        )

    try:
        # 2. 确保存储桶存在并启用了版本控制
        found = minio_client.bucket_exists(BUCKET_NAME)
        if not found:
            minio_client.make_bucket(BUCKET_NAME)
            logger.info(f"存储桶 '{BUCKET_NAME}' 已创建。")
            # 启用版本控制
            minio_client.set_bucket_versioning(BUCKET_NAME, {"Status": "Enabled"})
            logger.info(f"存储桶 '{BUCKET_NAME}' 已启用版本控制。")
        else:
            # 检查版本控制状态，以防万一存储桶已存在但未启用版本控制
            versioning_status = minio_client.get_bucket_versioning(BUCKET_NAME)
            if versioning_status.status != "Enabled":
                 minio_client.set_bucket_versioning(BUCKET_NAME, {"Status": "Enabled"})
                 logger.info(f"检测到版本控制未启用，现已为存储桶 '{BUCKET_NAME}' 启用。")

        # 3. 将文件内容读入内存
        file_content = await file.read()
        file_size = len(file_content)
        file_stream = io.BytesIO(file_content)

        # 4. 上传文件
        object_name = file.filename
        result = minio_client.put_object(
            bucket_name=BUCKET_NAME,
            object_name=object_name,
            data=file_stream,
            length=file_size,
            content_type=file.content_type,
        )

        logger.info(
            f"成功将 '{object_name}' (版本ID: {result.version_id}) 上传到存储桶 '{BUCKET_NAME}'。"
        )

        # 5. 返回成功响应
        return {
            "message": "文件已成功上传并启用版本控制。",
            "filename": object_name,
            "bucket": result.bucket_name,
            "versionId": result.version_id,
            "etag": result.etag,
        }

    except S3Error as exc:
        logger.error(f"MinIO S3 错误: {exc}")
        raise HTTPException(status_code=500, detail=f"发生 S3 错误: {exc}")
    except Exception as exc:
        logger.error(f"发生意外错误: {exc}")
        raise HTTPException(status_code=500, detail=f"发生意外错误: {exc}")


@router.post("/api/upload_return_url", tags=["File Upload with Versioning"])
async def uploadfile_with_return_url(file: UploadFile = File(...)):
    """
    上传文件并直接返回可访问的 MinIO URL。

    - 入参: 单文件（支持 PDF/Markdown/DOCX，与版本化上传保持一致）
    - 行为: 若桶不存在则创建并确保启用版本控制；对象名使用原文件名
    - 返回: 最小可用信息 + 多种 URL 形式（minio://、HTTP直链、长效预签名）
    """
    # 1. 验证文件类型
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning(f"上传了无效的文件类型: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"文件类型无效。只允许上传 PDF, Markdown, 和 DOCX。当前类型为 {file.content_type}"
        )

    try:
        # 2. 确保存储桶存在并启用版本控制
        found = minio_client.bucket_exists(BUCKET_NAME)
        if not found:
            minio_client.make_bucket(BUCKET_NAME)
            logger.info(f"存储桶 '{BUCKET_NAME}' 已创建。")
            minio_client.set_bucket_versioning(BUCKET_NAME, {"Status": "Enabled"})
            logger.info(f"存储桶 '{BUCKET_NAME}' 已启用版本控制。")
        else:
            versioning_status = minio_client.get_bucket_versioning(BUCKET_NAME)
            if getattr(versioning_status, 'status', None) != "Enabled":
                minio_client.set_bucket_versioning(BUCKET_NAME, {"Status": "Enabled"})
                logger.info(f"检测到版本控制未启用，现已为存储桶 '{BUCKET_NAME}' 启用。")

        # 3. 读取文件内容
        file_content = await file.read()
        file_size = len(file_content)
        file_stream = io.BytesIO(file_content)

        # 4. 上传对象（使用原始文件名；若重名将产生新版本）
        object_name = file.filename
        result = minio_client.put_object(
            bucket_name=BUCKET_NAME,
            object_name=object_name,
            data=file_stream,
            length=file_size,
            content_type=file.content_type,
        )

        logger.info(
            f"成功上传 '{object_name}' (version_id: {getattr(result, 'version_id', None)}) 到 '{BUCKET_NAME}'"
        )

        # 5. 组装多种可用URL
        minio_uri = f"minio://{BUCKET_NAME}/{object_name}"
        public_host = os.getenv("MINIO_PUBLIC_HOST", os.getenv("MINIO_API_HOST", "43.139.19.144:9000"))
        http_url = f"http://{public_host}/{BUCKET_NAME}/{object_name}"

        # 生成长效预签名URL（演示用途，可按需缩短）
        try:
            from datetime import timedelta
            presigned_url = minio_client.presigned_get_object(
                BUCKET_NAME,
                object_name,
                expires=timedelta(days=365*10),
                version_id=getattr(result, 'version_id', None)
            )
        except Exception as e:
            logger.warning(f"生成预签名URL失败，将返回空值: {e}")
            presigned_url = None

        return {
            "success": True,
            "message": "文件上传成功",
            "filename": object_name,
            "bucket": getattr(result, 'bucket_name', BUCKET_NAME),
            "version_id": getattr(result, 'version_id', None),
            "minio_url": minio_uri,
            "http_url": http_url,
            "presigned_url": presigned_url,
        }

    except S3Error as exc:
        logger.error(f"MinIO S3 错误: {exc}")
        raise HTTPException(status_code=500, detail=f"发生 S3 错误: {exc}")
    except Exception as exc:
        logger.error(f"发生意外错误: {exc}")
        raise HTTPException(status_code=500, detail=f"发生意外错误: {exc}")

@router.get("/api/getfile_versions", tags=["File Upload with Versioning"])
async def get_file_versions(filename: str):
    """
    获取指定文件的所有版本信息。
    """
    try:
        # 1. 检查存储桶是否存在
        if not minio_client.bucket_exists(BUCKET_NAME):
            raise HTTPException(status_code=404, detail=f"存储桶 '{BUCKET_NAME}' 不存在。")

        # 2. 列出对象的所有版本
        objects = minio_client.list_objects(BUCKET_NAME, prefix=filename, include_version=True)
        
        versions = []
        for obj in objects:
            # 确保只返回与查询文件名完全匹配的对象版本
            if obj.object_name == filename:
                versions.append({
                    "versionId": obj.version_id,
                    "isLatest": obj.is_latest,
                    "lastModified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag,
                    "size": obj.size,
                    "storageClass": obj.storage_class
                })

        # 3. 如果未找到任何版本
        if not versions:
            raise HTTPException(status_code=404, detail=f"文件 '{filename}' 在存储桶 '{BUCKET_NAME}' 中未找到。")

        logger.info(f"成功检索到文件 '{filename}' 的 {len(versions)} 个版本。")
        
        # 4. 返回版本信息
        return {
            "filename": filename,
            "bucket": BUCKET_NAME,
            "versions": versions
        }

    except S3Error as exc:
        logger.error(f"查询版本时发生MinIO S3错误: {exc}")
        raise HTTPException(status_code=500, detail=f"查询版本时发生S3错误: {exc}")
    except HTTPException as http_exc:
        # 重新抛出已捕获的HTTPException，避免被下面的通用异常覆盖
        raise http_exc
    except Exception as exc:
        logger.error(f"查询版本时发生意外错误: {exc}")
        raise HTTPException(status_code=500, detail=f"查询版本时发生意外错误: {exc}")


class RevertRequest(BaseModel):
    version_id: str



@router.get("/api/get_fileurlby_version", tags=["File Upload with Versioning"])
async def get_fileurlby_version(filename: str, version_id: str):
    """
    获取文件特定版本的下载URL。
    """
    try:
        # 1. 检查存储桶是否存在
        if not minio_client.bucket_exists(BUCKET_NAME):
            raise HTTPException(status_code=404, detail=f"存储桶 '{BUCKET_NAME}' 不存在。")

        # 2. 检查文件版本是否存在
        try:
            minio_client.stat_object(BUCKET_NAME, filename, version_id=version_id)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise HTTPException(status_code=404, detail=f"文件 '{filename}' 的版本 '{version_id}' 未找到。")
            raise

        # 3. 生成预签名下载URL（永久有效，适用于demo阶段）
        from datetime import timedelta
        download_url = minio_client.presigned_get_object(
            BUCKET_NAME, 
            filename, 
            expires=timedelta(days=365*10),  # 设置为10年，实际上相当于永久
            version_id=version_id
        )
        
        return {
            "message": "获取下载URL成功",
            "filename": filename,
            "version_id": version_id,
            "download_url": download_url,
            "expires_in_days": "永久有效（demo阶段）"
        }

    except S3Error as exc:
        logger.error(f"获取文件下载URL时发生MinIO S3错误: {exc}")
        raise HTTPException(status_code=500, detail=f"获取文件下载URL时发生S3错误: {exc}")
    except Exception as exc:
        logger.error(f"获取文件下载URL时发生意外错误: {exc}")
        raise HTTPException(status_code=500, detail=f"获取文件下载URL时发生意外错误: {exc}")


@router.get("/api/get_fileBinby_version", tags=["File Upload with Versioning"])
async def get_fileBinby_version(filename: str, version_id: str):
    """
    获取文件特定版本的二进制文件。
    """
    try:
        # 1. 检查存储桶是否存在
        if not minio_client.bucket_exists(BUCKET_NAME):
            raise HTTPException(status_code=404, detail=f"存储桶 '{BUCKET_NAME}' 不存在。")

        # 2. 检查文件版本是否存在并获取文件信息
        try:
            file_stat = minio_client.stat_object(BUCKET_NAME, filename, version_id=version_id)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise HTTPException(status_code=404, detail=f"文件 '{filename}' 的版本 '{version_id}' 未找到。")
            raise

        # 3. 获取文件对象
        try:
            file_data = minio_client.get_object(BUCKET_NAME, filename, version_id=version_id)
            
            # 创建一个生成器函数来流式传输文件内容
            def file_generator():
                try:
                    for chunk in file_data.stream(1024 * 1024):  # 1MB chunks
                        yield chunk
                finally:
                    file_data.close()
                    file_data.release_conn()
            
            # 确定文件的MIME类型
            import mimetypes
            import urllib.parse
            content_type, _ = mimetypes.guess_type(filename)
            if content_type is None:
                content_type = "application/octet-stream"
            
            # 处理文件名编码，支持中文字符
            # 使用RFC 5987标准进行编码
            encoded_filename = urllib.parse.quote(filename, safe='')
            
            # 返回流式响应
            return StreamingResponse(
                file_generator(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                    "Content-Length": str(file_stat.size)
                }
            )
            
        except S3Error as exc:
            logger.error(f"获取文件内容时发生MinIO S3错误: {exc}")
            raise HTTPException(status_code=500, detail=f"获取文件内容时发生S3错误: {exc}")

    except S3Error as exc:
        logger.error(f"获取文件时发生MinIO S3错误: {exc}")
        raise HTTPException(status_code=500, detail=f"获取文件时发生S3错误: {exc}")
    except Exception as exc:
        logger.error(f"获取文件时发生意外错误: {exc}")
        raise HTTPException(status_code=500, detail=f"获取文件时发生意外错误: {exc}")