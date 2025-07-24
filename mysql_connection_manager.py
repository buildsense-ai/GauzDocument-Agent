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
    - 错误恢复
    """
    
    def __init__(self):
        self.connection = None
        self.connection_lock = Lock()
        self.last_ping = 0
        self.ping_interval = 10  # 降低到10秒检查一次连接，更频繁的健康检查
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 1  # 重试延迟秒数
        
        # 增强的MySQL配置 - 专门解决连接稳定性问题
        self.config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DATABASE', 'mysql_templates'),
            'charset': os.getenv('MYSQL_CHARSET', 'utf8mb4'),
            'autocommit': True,
            
            # 连接超时优化
            'connect_timeout': 10,      # 降低连接超时，快速失败
            'read_timeout': 30,         # 降低读取超时
            'write_timeout': 30,        # 降低写入超时
            
            # 新增：连接保活参数
            'init_command': "SET SESSION wait_timeout=28800, interactive_timeout=28800",  # 8小时超时
            'sql_mode': 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO',
            
            # 启用TCP keepalive
            'use_unicode': True,
            'cursorclass': pymysql.cursors.DictCursor,  # 使用字典游标，更好的数据处理
        }
        
        logger.info(f"🔧 增强MySQL配置: {self.config['user']}@{self.config['host']}:{self.config['port']}/{self.config['database']}")
        logger.info(f"🔧 连接检查间隔: {self.ping_interval}秒, 最大重试: {self.max_retries}次")
        
    def _create_connection(self, retry_count: int = 0) -> Optional[pymysql.Connection]:
        """创建新的MySQL连接，带重试机制"""
        try:
            logger.info(f"🔄 创建新的MySQL连接... (尝试 {retry_count + 1}/{self.max_retries + 1})")
            connection = pymysql.connect(**self.config)
            
            # 连接后立即测试
            connection.ping(reconnect=False)
            logger.info("✅ MySQL连接创建并验证成功")
            return connection
            
        except Exception as e:
            logger.error(f"❌ MySQL连接创建失败 (尝试 {retry_count + 1}): {e}")
            
            # 如果还有重试机会
            if retry_count < self.max_retries:
                logger.info(f"⏳ {self.retry_delay}秒后重试...")
                time.sleep(self.retry_delay)
                return self._create_connection(retry_count + 1)
            else:
                logger.error(f"❌ 达到最大重试次数 ({self.max_retries + 1})，连接创建失败")
                return None
    
    def _is_connection_alive(self, connection: pymysql.Connection) -> bool:
        """检查连接是否存活，增强错误检测"""
        if not connection:
            return False
            
        try:
            # 使用ping检查连接
            connection.ping(reconnect=False)
            
            # 额外检查：执行简单查询
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
                
        except Exception as e:
            error_msg = str(e).lower()
            # 检测常见的连接失败模式
            connection_errors = [
                'lost connection', 'gone away', 'timeout', 'connection reset',
                'broken pipe', 'connection refused', 'not connected'
            ]
            
            if any(err in error_msg for err in connection_errors):
                logger.warning(f"⚠️ 检测到连接问题: {e}")
            else:
                logger.warning(f"⚠️ 连接检查失败: {e}")
            return False
    
    def get_connection(self) -> Optional[pymysql.Connection]:
        """获取可用的MySQL连接，增强的连接管理"""
        with self.connection_lock:
            current_time = time.time()
            
            # 更频繁的连接检查或连接不存在
            if (self.connection is None or 
                current_time - self.last_ping > self.ping_interval):
                
                # 检查现有连接
                if self.connection:
                    if not self._is_connection_alive(self.connection):
                        logger.info("🔄 检测到连接断开，重新创建...")
                        try:
                            self.connection.close()
                        except Exception as e:
                            logger.debug(f"关闭旧连接时出错: {e}")
                        self.connection = None
                    else:
                        # 连接正常，更新ping时间
                        self.last_ping = current_time
                        logger.debug("✅ 连接健康检查通过")
                
                # 创建新连接（如果需要）
                if self.connection is None:
                    self.connection = self._create_connection()
                    if self.connection:
                        self.last_ping = current_time
            
            return self.connection
    
    @contextmanager
    def get_cursor(self):
        """获取数据库游标的上下文管理器，增强错误处理"""
        max_attempts = 2  # 最多尝试2次
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                connection = self.get_connection()
                if not connection:
                    raise Exception("无法获取MySQL连接")
                
                cursor = connection.cursor()
                try:
                    yield cursor
                    return  # 成功执行，退出重试循环
                except Exception as e:
                    cursor.close()
                    raise e
                    
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # 检查是否是连接相关错误
                connection_errors = [
                    'lost connection', 'gone away', 'timeout', 'connection reset',
                    'broken pipe', 'connection refused', 'not connected', 'mysql server has gone away'
                ]
                
                if any(err in error_msg for err in connection_errors):
                    logger.warning(f"🔄 检测到连接问题 (尝试 {attempt + 1}/{max_attempts}): {e}")
                    if attempt < max_attempts - 1:  # 不是最后一次尝试
                        logger.info("🔄 重置连接并重试...")
                        self.reset_connection()
                        time.sleep(0.5)  # 短暂等待
                        continue
                
                # 非连接错误或已达最大尝试次数
                logger.error(f"❌ 数据库操作失败: {e}")
                raise e
        
        # 如果所有尝试都失败了
        if last_exception:
            raise last_exception
    
    def reset_connection(self):
        """重置连接，增强的清理逻辑"""
        with self.connection_lock:
            if self.connection:
                try:
                    # 尝试优雅关闭
                    if self._is_connection_alive(self.connection):
                        self.connection.close()
                    else:
                        # 连接已死，强制清理
                        self.connection = None
                except Exception as e:
                    logger.debug(f"关闭连接时出错: {e}")
                finally:
                    self.connection = None
            
            # 重置ping时间，强制下次获取时重新创建连接
            self.last_ping = 0
            logger.info("🔄 连接已重置")
    
    def test_connection(self) -> bool:
        """测试连接，增强的测试逻辑"""
        try:
            with self.get_cursor() as cursor:
                # 执行多个测试查询
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                
                if result and result.get('test') == 1:
                    # 额外测试：检查数据库访问权限
                    cursor.execute("SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = %s", (self.config['database'],))
                    table_result = cursor.fetchone()
                    
                    logger.info(f"✅ MySQL连接测试成功，数据库 '{self.config['database']}' 包含 {table_result.get('count', 0)} 个表")
                    return True
                else:
                    logger.error("❌ MySQL连接测试失败：查询结果异常")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ MySQL连接测试失败: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息，用于监控"""
        with self.connection_lock:
            return {
                'connected': self.connection is not None,
                'last_ping': self.last_ping,
                'ping_interval': self.ping_interval,
                'host': self.config['host'],
                'port': self.config['port'],
                'database': self.config['database'],
                'user': self.config['user']
            }
    
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
    
    # 显示连接信息
    info = mysql_manager.get_connection_info()
    print(f"📋 连接配置: {info['user']}@{info['host']}:{info['port']}/{info['database']}")
    
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
                    table_name = table.get('Tables_in_' + info['database'], list(table.values())[0])
                    print(f'  - {table_name}')
                    
                # 测试连接稳定性
                print("\n🔍 测试连接稳定性...")
                for i in range(3):
                    cursor.execute("SELECT NOW() as now_time, CONNECTION_ID() as conn_id")
                    result = cursor.fetchone()
                    print(f"  测试 {i+1}: 连接ID {result['conn_id']}, 时间 {result['now_time']}")
                    time.sleep(1)
                    
        except Exception as e:
            print(f'❌ 查询测试失败: {e}')
    else:
        print('❌ 连接管理器测试失败')
        
    # 显示最终状态
    final_info = mysql_manager.get_connection_info()
    print(f"\n📈 最终状态: {'已连接' if final_info['connected'] else '未连接'}")

if __name__ == '__main__':
    test_mysql_manager() 