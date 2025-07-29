"""
数据库相关工具函数
"""

import os
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import SessionLocal, init_database
from .crud import init_default_data

logger = logging.getLogger(__name__)

def get_database_session() -> Session:
    """获取数据库会话的便捷函数"""
    return SessionLocal()

def setup_database() -> bool:
    """设置数据库（创建表、初始化数据）"""
    try:
        # 初始化数据库
        if not init_database():
            return False
        
        # 初始化默认数据
        db = get_database_session()
        try:
            init_default_data(db)
            logger.info("✅ 数据库设置完成")
            return True
        except Exception as e:
            logger.error(f"❌ 初始化默认数据失败: {e}")
            return False
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ 数据库设置失败: {e}")
        return False

def check_database_health() -> Dict[str, Any]:
    """检查数据库健康状态"""
    try:
        db = get_database_session()
        try:
            # 🔧 简单查询测试 - SQLAlchemy 2.0兼容
            result = db.execute(text("SELECT 1")).scalar()
            
            # 统计数据
            from .models import Project, ChatMessage, ProjectFile
            project_count = db.query(Project).count()
            message_count = db.query(ChatMessage).count()
            file_count = db.query(ProjectFile).count()
            
            return {
                "status": "healthy",
                "connection": True,
                "stats": {
                    "projects": project_count,
                    "messages": message_count,
                    "files": file_count
                }
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "connection": False,
            "error": str(e)
        } 