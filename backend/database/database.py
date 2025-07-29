"""
数据库连接配置
"""

import os
import urllib.parse
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

# 🆕 数据库配置 - 从环境变量读取
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ai_assistant_db")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")
MYSQL_POOL_SIZE = int(os.getenv("MYSQL_POOL_SIZE", "10"))
MYSQL_MAX_OVERFLOW = int(os.getenv("MYSQL_MAX_OVERFLOW", "20"))

# 🔧 构建数据库连接URL - 对密码进行URL编码处理特殊字符
encoded_password = urllib.parse.quote_plus(MYSQL_PASSWORD)
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{encoded_password}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

logger.info(f"数据库连接信息: {MYSQL_USER}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,           # 连接池预检
    pool_recycle=3600,            # 连接回收时间
    pool_size=MYSQL_POOL_SIZE,    # 连接池大小（从环境变量）
    max_overflow=MYSQL_MAX_OVERFLOW,  # 最大溢出连接数（从环境变量）
    echo=False,                   # 生产环境关闭SQL日志
    connect_args={
        "charset": MYSQL_CHARSET,  # 字符集（从环境变量）
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"
    }
)

# 数据库会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ORM基类
Base = declarative_base()

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# 数据库连接测试
def test_connection():
    """测试数据库连接"""
    try:
        db = SessionLocal()
        # 🔧 SQLAlchemy 2.0 需要显式声明文本SQL
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("✅ 数据库连接测试成功")
        return True
    except Exception as e:
        logger.error(f"❌ 数据库连接测试失败: {e}")
        return False

# 创建所有表
def create_tables():
    """创建所有数据库表"""
    try:
        # 导入所有模型以确保表被创建
        from . import models
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表创建成功")
        return True
    except Exception as e:
        logger.error(f"❌ 数据库表创建失败: {e}")
        return False

# 数据库初始化
def init_database():
    """初始化数据库"""
    if test_connection():
        return create_tables()
    return False 