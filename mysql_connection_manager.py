#!/usr/bin/env python3
"""
增强的MySQL连接管理器
解决连接丢失和超时问题
"""
import os
import time
import logging
import pymysql
from typing import Optional, Dict, Any
from contextlib import contextmanager
from threading import Lock
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class MySQLConnectionManager:
    """
    增强的MySQL连接管理器
    - 连接池管理
    - 自动重连
    - 连接健康检查
    - 超时处理
    """
    
    def __init__(self):
        self.connection = None
        self.connection_lock = Lock()
        self.last_ping = 0
        self.ping_interval = 30  # 30秒检查一次连接
        
        # MySQL配置 - 使用环境变量（仅PyMySQL支持的参数）
        self.config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DATABASE', 'mysql_templates'),
            'charset': os.getenv('MYSQL_CHARSET', 'utf8mb4'),
            'autocommit': True,
            'connect_timeout': 30,      # 连接超时
            'read_timeout': 300,        # 读取超时5分钟  
            'write_timeout': 300,       # 写入超时5分钟
        }
        
        logger.info(f"🔧 MySQL配置: {self.config['user']}@{self.config['host']}:{self.config['port']}/{self.config['database']}")
        
    def _create_connection(self) -> Optional[pymysql.Connection]:
        """创建新的MySQL连接"""
        try:
            logger.info("🔄 创建新的MySQL连接...")
            connection = pymysql.connect(**self.config)
            logger.info("✅ MySQL连接创建成功")
            return connection
        except Exception as e:
            logger.error(f"❌ MySQL连接创建失败: {e}")
            return None
    
    def _is_connection_alive(self, connection: pymysql.Connection) -> bool:
        """检查连接是否存活"""
        try:
            connection.ping(reconnect=False)
            return True
        except Exception as e:
            logger.warning(f"⚠️ 连接检查失败: {e}")
            return False
    
    def get_connection(self) -> Optional[pymysql.Connection]:
        """获取可用的MySQL连接"""
        with self.connection_lock:
            current_time = time.time()
            
            # 如果连接不存在或需要检查健康状态
            if (self.connection is None or 
                current_time - self.last_ping > self.ping_interval):
                
                # 检查现有连接
                if self.connection and not self._is_connection_alive(self.connection):
                    logger.info("🔄 检测到连接断开，重新创建...")
                    try:
                        self.connection.close()
                    except:
                        pass
                    self.connection = None
                
                # 创建新连接（如果需要）
                if self.connection is None:
                    self.connection = self._create_connection()
                
                self.last_ping = current_time
            
            return self.connection
    
    @contextmanager
    def get_cursor(self):
        """获取数据库游标的上下文管理器"""
        connection = self.get_connection()
        if not connection:
            raise Exception("无法获取MySQL连接")
        
        cursor = connection.cursor()
        try:
            yield cursor
        except Exception as e:
            logger.error(f"❌ 数据库操作失败: {e}")
            # 如果是连接相关错误，重置连接
            if any(keyword in str(e).lower() for keyword in ['lost connection', 'gone away', 'timeout']):
                logger.info("🔄 检测到连接问题，重置连接...")
                self.reset_connection()
            raise
        finally:
            cursor.close()
    
    def reset_connection(self):
        """重置连接"""
        with self.connection_lock:
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None
            logger.info("🔄 连接已重置")
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    logger.info("✅ MySQL连接测试成功")
                    return True
                else:
                    logger.error("❌ MySQL连接测试失败：查询结果异常")
                    return False
        except Exception as e:
            logger.error(f"❌ MySQL连接测试失败: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        with self.connection_lock:
            if self.connection:
                try:
                    self.connection.close()
                    logger.info("🔒 MySQL连接已关闭")
                except Exception as e:
                    logger.error(f"❌ 关闭MySQL连接失败: {e}")
                finally:
                    self.connection = None

# 全局连接管理器实例
mysql_manager = MySQLConnectionManager()

def test_mysql_manager():
    """测试MySQL连接管理器"""
    print('🧪 测试增强的MySQL连接管理器')
    print('='*50)
    
    # 测试连接
    if mysql_manager.test_connection():
        print('✅ 连接管理器工作正常')
        
        # 测试查询
        try:
            with mysql_manager.get_cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print(f'📊 数据库中有 {len(tables)} 个表')
                for table in tables:
                    print(f'  - {table[0]}')
        except Exception as e:
            print(f'❌ 查询测试失败: {e}')
    else:
        print('❌ 连接管理器测试失败')

if __name__ == '__main__':
    test_mysql_manager() 