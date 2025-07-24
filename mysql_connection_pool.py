#!/usr/bin/env python3
"""
MySQL连接池管理器
解决并发连接和线程安全问题
"""
import os
import time
import logging
import pymysql
import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager
from queue import Queue, Empty
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class MySQLConnectionPool:
    """
    MySQL连接池管理器
    - 真正的连接池（多个连接）
    - 线程安全
    - 自动重连
    - 连接健康检查
    - 连接复用
    """
    
    def __init__(self, min_connections=2, max_connections=10):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.pool_lock = threading.Lock()
        self.created_connections = 0
        
        # MySQL配置
        self.config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DATABASE', 'mysql_templates'),
            'charset': os.getenv('MYSQL_CHARSET', 'utf8mb4'),
            'autocommit': True,
            
            # 优化的连接参数
            'connect_timeout': 10,
            'read_timeout': 30,
            'write_timeout': 30,
            'init_command': "SET SESSION wait_timeout=28800, interactive_timeout=28800",
            'use_unicode': True,
            'cursorclass': pymysql.cursors.DictCursor,
        }
        
        # 初始化最小连接数
        self._initialize_pool()
        logger.info(f"🔧 MySQL连接池初始化完成: {self.min_connections}-{self.max_connections} 连接")
        
    def _create_connection(self) -> Optional[pymysql.Connection]:
        """创建新的MySQL连接"""
        try:
            logger.debug("🔄 创建新的MySQL连接...")
            connection = pymysql.connect(**self.config)
            connection.ping(reconnect=False)  # 验证连接
            logger.debug("✅ MySQL连接创建成功")
            return connection
        except Exception as e:
            logger.error(f"❌ MySQL连接创建失败: {e}")
            return None
    
    def _initialize_pool(self):
        """初始化连接池"""
        for i in range(self.min_connections):
            connection = self._create_connection()
            if connection:
                self.pool.put(connection)
                self.created_connections += 1
                logger.debug(f"➕ 添加连接到池中 ({i+1}/{self.min_connections})")
    
    def _is_connection_alive(self, connection: pymysql.Connection) -> bool:
        """检查连接是否存活"""
        try:
            connection.ping(reconnect=False)
            return True
        except Exception as e:
            logger.debug(f"⚠️ 连接检查失败: {e}")
            return False
    
    def get_connection(self, timeout=5) -> Optional[pymysql.Connection]:
        """从连接池获取连接"""
        # 尝试从池中获取连接
        try:
            connection = self.pool.get(timeout=timeout)
            
            # 检查连接是否存活
            if self._is_connection_alive(connection):
                logger.debug("✅ 从池中获取有效连接")
                return connection
            else:
                logger.debug("🔄 池中连接已失效，创建新连接")
                try:
                    connection.close()
                except:
                    pass
                
        except Empty:
            logger.debug("⏰ 池中无可用连接，尝试创建新连接")
        
        # 如果池中没有连接或连接无效，创建新连接
        with self.pool_lock:
            if self.created_connections < self.max_connections:
                new_connection = self._create_connection()
                if new_connection:
                    self.created_connections += 1
                    logger.debug(f"➕ 创建新连接 (总数: {self.created_connections}/{self.max_connections})")
                    return new_connection
        
        logger.warning("❌ 无法获取MySQL连接，连接池已满")
        return None
    
    def return_connection(self, connection: pymysql.Connection):
        """将连接返回到池中"""
        if connection and self._is_connection_alive(connection):
            try:
                self.pool.put_nowait(connection)
                logger.debug("↩️ 连接返回到池中")
            except Exception:
                # 池已满，关闭连接
                logger.debug("🔒 池已满，关闭连接")
                try:
                    connection.close()
                except:
                    pass
                with self.pool_lock:
                    self.created_connections -= 1
        else:
            # 连接无效，关闭并减少计数
            logger.debug("🗑️ 无效连接已丢弃")
            try:
                connection.close()
            except:
                pass
            with self.pool_lock:
                self.created_connections -= 1
    
    @contextmanager
    def get_cursor(self, timeout=5):
        """获取数据库游标的上下文管理器"""
        connection = None
        cursor = None
        
        try:
            connection = self.get_connection(timeout=timeout)
            if not connection:
                raise Exception("无法从连接池获取MySQL连接")
            
            cursor = connection.cursor()
            yield cursor
            
        except Exception as e:
            logger.error(f"❌ 数据库操作失败: {e}")
            # 如果是连接相关错误，不返回连接到池中
            if connection and any(keyword in str(e).lower() for keyword in 
                                ['lost connection', 'gone away', 'timeout', 'connection reset']):
                logger.debug("🔄 连接错误，不返回到池中")
                try:
                    connection.close()
                except:
                    pass
                with self.pool_lock:
                    self.created_connections -= 1
                connection = None
            raise
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                self.return_connection(connection)
    
    def test_connection(self) -> bool:
        """测试连接池"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                
                if result and result.get('test') == 1:
                    logger.info("✅ 连接池测试成功")
                    return True
                else:
                    logger.error("❌ 连接池测试失败：查询结果异常")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 连接池测试失败: {e}")
            return False
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        return {
            'pool_size': self.pool.qsize(),
            'created_connections': self.created_connections,
            'min_connections': self.min_connections,
            'max_connections': self.max_connections,
            'available_connections': self.pool.qsize(),
            'active_connections': self.created_connections - self.pool.qsize()
        }
    
    def close_all(self):
        """关闭所有连接"""
        logger.info("🔒 关闭连接池中的所有连接...")
        closed_count = 0
        
        # 关闭池中的连接
        while not self.pool.empty():
            try:
                connection = self.pool.get_nowait()
                connection.close()
                closed_count += 1
            except:
                break
        
        self.created_connections = 0
        logger.info(f"🔒 已关闭 {closed_count} 个连接")

# 全局连接池实例
mysql_pool = MySQLConnectionPool(min_connections=3, max_connections=10)

# 兼容性：保持原有接口
class MySQLConnectionManager:
    """兼容性包装器，使用连接池"""
    
    def __init__(self):
        self.pool = mysql_pool
    
    @contextmanager
    def get_cursor(self):
        with self.pool.get_cursor() as cursor:
            yield cursor
    
    def test_connection(self) -> bool:
        return self.pool.test_connection()
    
    def get_connection_info(self) -> Dict[str, Any]:
        status = self.pool.get_pool_status()
        return {
            'connected': status['created_connections'] > 0,
            'pool_status': status,
            'host': self.pool.config['host'],
            'port': self.pool.config['port'],
            'database': self.pool.config['database'],
            'user': self.pool.config['user']
        }
    
    def reset_connection(self):
        """重置操作：重新初始化连接池"""
        self.pool.close_all()
        self.pool._initialize_pool()
    
    def close(self):
        self.pool.close_all()

# 全局管理器实例（保持兼容性）
mysql_manager = MySQLConnectionManager()

def test_connection_pool():
    """测试连接池功能"""
    print('🧪 测试MySQL连接池')
    print('='*50)
    
    # 显示初始状态
    status = mysql_pool.get_pool_status()
    print(f"📊 初始状态: {status}")
    
    # 基础连接测试
    if mysql_pool.test_connection():
        print('✅ 连接池基础测试成功')
        
        # 并发测试
        import threading
        import time
        
        results = {'success': 0, 'failure': 0}
        results_lock = threading.Lock()
        
        def worker_test(worker_id, num_queries=5):
            for i in range(num_queries):
                try:
                    with mysql_pool.get_cursor() as cursor:
                        cursor.execute("SELECT %s as worker_id, %s as query_id, CONNECTION_ID() as conn_id", 
                                     (worker_id, i+1))
                        result = cursor.fetchone()
                        
                    with results_lock:
                        results['success'] += 1
                        
                    print(f"  Worker {worker_id}-{i+1}: 连接ID {result['conn_id']}")
                    
                except Exception as e:
                    with results_lock:
                        results['failure'] += 1
                    print(f"  Worker {worker_id}-{i+1} 失败: {e}")
                
                time.sleep(0.1)
        
        print('\n🔀 并发测试 (5个线程，每线程5次查询)...')
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_test, args=(i, 5))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
        
        print(f"\n📊 并发测试结果: 成功 {results['success']} 次, 失败 {results['failure']} 次")
        
        # 最终状态
        final_status = mysql_pool.get_pool_status()
        print(f"📊 最终状态: {final_status}")
        
        success_rate = (results['success'] / (results['success'] + results['failure'])) * 100
        print(f"🎯 成功率: {success_rate:.1f}%")
        
    else:
        print('❌ 连接池基础测试失败')

if __name__ == '__main__':
    try:
        test_connection_pool()
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    finally:
        mysql_pool.close_all()
        print("🔒 测试完成，连接池已关闭") 