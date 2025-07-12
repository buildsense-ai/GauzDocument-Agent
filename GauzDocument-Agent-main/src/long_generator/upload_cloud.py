# 文件名: cloud_upload.py
# -*- coding: utf-8 -*-

"""
cloud_upload.py

封装了与MinIO云存储交互的功能。
"""
from minio import Minio
from minio.error import S3Error
import os

from config import Config


def upload_to_minio(file_path: str, object_name: str) -> str | None:
    """
    将本地文件上传到MinIO存储桶。

    Args:
        file_path (str): 本地文件的完整路径。
        object_name (str): 上传后在存储桶中对象（文件）的名称。

    Returns:
        str | None: 如果上传成功，返回文件的公共访问URL；否则返回None。
    """
    print(f"--- 准备上传文件到MinIO: {object_name} ---")
    try:
        # 1. 初始化MinIO客户端
        client = Minio(
            Config.MINIO_ENDPOINT,
            access_key=Config.MINIO_ACCESS_KEY,
            secret_key=Config.MINIO_SECRET_KEY,
            secure=Config.MINIO_USE_SECURE
        )

        # 2. 检查存储桶是否存在，如果不存在则创建
        bucket_name = Config.MINIO_BUCKET_NAME
        found = client.bucket_exists(bucket_name)
        if not found:
            print(f"存储桶 '{bucket_name}' 不存在，正在创建...")
            client.make_bucket(bucket_name)
            print(f"存储桶 '{bucket_name}' 创建成功。")
            # 可选：设置存储桶的访问策略为公开读
            # import json
            # policy = {"Version": "2012-10-17", "Statement": [{"Action": ["s3:GetObject"], "Effect": "Allow", "Principal": {"AWS": ["*"]}, "Resource": [f"arn:aws:s3:::{bucket_name}/*"], "Sid": ""}]}
            # client.set_bucket_policy(bucket_name, json.dumps(policy))

        # 3. 上传文件
        client.fput_object(
            bucket_name,
            object_name,
            file_path,
        )

        # 4. 构造并返回公共URL
        # 注释：这个URL的格式取决于您的MinIO服务器配置和网络环境。
        #       这里我们构造一个标准的HTTP URL。
        public_url = f"http://{Config.MINIO_ENDPOINT}/{bucket_name}/{object_name}"
        print(f"--- 文件上传成功！公共访问地址: {public_url} ---")
        return public_url

    except S3Error as exc:
        print(f"!! [错误] 与MinIO交互时发生错误: {exc}")
        return None
    except Exception as exc:
        print(f"!! [错误] 上传文件到MinIO时发生未知错误: {exc}")
        return None

