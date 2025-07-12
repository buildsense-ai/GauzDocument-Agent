# 文件名: config.py
# -*- coding: utf-8 -*-

"""
config.py

集中管理项目的所有配置信息。
[已更新] 添加了本地RAG工具的配置选项。
"""

import os


class Config:
    """
    用于存放所有配置信息的静态类。
    """
    # 任务状态文件的存储目录
    TASKS_DIR = "tasks"

    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
    AI_MODEL_NAME = "deepseek-chat"

    # 大纲精炼的最大循环次数
    MAX_REFINEMENT_CYCLES = 3

    # 🆕 本地RAG工具配置
    USE_LOCAL_RAG = True  # 是否使用本地RAG工具
    LOCAL_RAG_STORAGE_DIR = "../../rag_storage"  # 相对于long_generator目录的RAG存储路径
    
    # 项目隔离配置
    USE_PROJECT_ISOLATION = True  # 是否启用项目隔离功能
    DEFAULT_PROJECT_NAME = ""  # 默认项目名称（空表示不限制）

    # 向量搜索API配置 (文本搜索) - 保留作为备用
    TEXT_SEARCH_ENDPOINT = "http://43.139.19.144:3000/search-drawings"

    # [已更新] 向量搜索API配置 (图片搜索) - 保留作为备用
    IMAGE_SEARCH_ENDPOINT = "http://65d27a3b.r23.cpolar.top/search/images"

    # 默认检索参数
    SEARCH_DEFAULT_TOP_K = 5
    IMAGE_SEARCH_MIN_SCORE = 0.4

    # MinIO云存储配置
    MINIO_ENDPOINT = "43.139.19.144:9000"
    MINIO_ACCESS_KEY = "minioadmin"
    MINIO_SECRET_KEY = "minioadmin"
    MINIO_BUCKET_NAME = "docs"
    MINIO_USE_SECURE = False

    # 🆕 本地RAG工具的高级配置
    @classmethod
    def get_rag_config(cls) -> dict:
        """
        获取本地RAG工具的配置信息
        
        Returns:
            dict: RAG工具配置字典
        """
        return {
            "use_local_rag": cls.USE_LOCAL_RAG,
            "storage_dir": cls.LOCAL_RAG_STORAGE_DIR,
            "use_project_isolation": cls.USE_PROJECT_ISOLATION,
            "default_project_name": cls.DEFAULT_PROJECT_NAME,
            "search_top_k": cls.SEARCH_DEFAULT_TOP_K,
            "fallback_to_external": True,  # 是否在本地RAG失败时回退到外部API
            "external_text_endpoint": cls.TEXT_SEARCH_ENDPOINT,
            "external_image_endpoint": cls.IMAGE_SEARCH_ENDPOINT
        }

    # 🆕 调试和日志配置
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"

