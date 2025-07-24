"""
模版搜索工具 - ElasticSearch搜索
独立工具，输入自然语言query，输出模版内容
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError
import pymysql

# 加载环境变量
load_dotenv()

# 导入组件 - 使用稳定的连接池
from mysql_connection_pool import mysql_manager

logger = logging.getLogger(__name__)

class TemplateSearchTool:
    """
    模版搜索工具 - ElasticSearch搜索
    
    功能：
    1. ElasticSearch搜索候选模版
    2. 返回最佳匹配的模版内容
    """
    
    def __init__(self):
        """初始化模版搜索工具"""
        # 初始化ElasticSearch客户端
        self.es_client = None
        self.es_index_name = "template_search_index"
        self._init_elasticsearch()
        
        logger.info("✅ 模版搜索工具初始化完成")
        logger.info("🔍 功能: ElasticSearch搜索")
    
    def _init_elasticsearch(self):
        """初始化ElasticSearch客户端并刷新模板索引"""
        try:
            # ElasticSearch配置
            es_host = os.getenv("ELASTICSEARCH_HOST", "localhost")
            es_port = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
            es_scheme = os.getenv("ELASTICSEARCH_SCHEME", "http")
            
            # 创建ES客户端
            es_url = f"{es_scheme}://{es_host}:{es_port}"
            self.es_client = Elasticsearch(
                hosts=[es_url],
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=30
            )
            
            # 测试连接
            if self.es_client.ping():
                logger.info("✅ ElasticSearch连接成功")
                # 每次初始化时都刷新索引
                self._refresh_template_index()
            else:
                logger.warning("⚠️ ElasticSearch连接失败")
                self.es_client = None
                
        except Exception as e:
            logger.error(f"❌ ElasticSearch初始化失败: {e}")
            self.es_client = None
    
    def _refresh_template_index(self):
        """刷新模板索引 - 每次系统初始化时运行"""
        try:
            logger.info("🔄 开始刷新模板索引...")
            
            # 1. 删除现有索引（如果存在）
            if self.es_client.indices.exists(index=self.es_index_name):
                logger.info(f"🗑️ 删除现有索引: {self.es_index_name}")
                self.es_client.indices.delete(index=self.es_index_name)
            
            # 2. 创建新索引
            logger.info(f"🔨 创建新索引: {self.es_index_name}")
            mapping = {
                "mappings": {
                    "properties": {
                        "guide_id": {"type": "keyword"},
                        "template_name": {
                            "type": "text",
                            "analyzer": "standard",
                            "search_analyzer": "standard"
                        },
                        "guide_summary": {
                            "type": "text",
                            "analyzer": "standard",
                            "search_analyzer": "standard"
                        },
                        "usage_frequency": {"type": "integer"},
                        "created_at": {"type": "date"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }
            
            self.es_client.indices.create(index=self.es_index_name, body=mapping)
            logger.info("✅ 索引创建完成")
                
            # 3. 从MySQL同步最新数据
            self._sync_latest_templates_to_es()
                
        except Exception as e:
            logger.error(f"❌ 刷新模板索引失败: {e}")
    
    def _sync_latest_templates_to_es(self):
        """从MySQL同步最新模板数据到ElasticSearch"""
        try:
            logger.info("📥 开始同步最新模板数据...")
            
            # 获取模板数据
            templates = self._mysql_search_report_guides("", limit=1000)
            
            if not templates:
                logger.warning("⚠️ MySQL中没有找到模板数据")
                return
            
            # 准备批量索引数据
            actions = []
            for template in templates:
                # 修复：清理guide_summary中的多余引号
                guide_summary = template.get("guide_summary", "") or ""
                if guide_summary.startswith('"') and guide_summary.endswith('"'):
                    guide_summary = guide_summary[1:-1]  # 去掉首尾引号
                
                doc = {
                    "guide_id": template.get("guide_id"),
                    "template_name": template.get("template_name", ""),
                    "guide_summary": guide_summary,
                    "usage_frequency": template.get("usage_frequency", 0),
                    "created_at": template.get("created_at", "")
                }
                
                action = {
                    "_index": self.es_index_name,
                    "_id": template.get("guide_id"),
                    "_source": doc
                }
                actions.append(action)
            
            # 执行批量索引
            if actions:
                from elasticsearch.helpers import bulk
                bulk(self.es_client, actions)
                logger.info(f"✅ 成功同步 {len(actions)} 个模板到ElasticSearch")
                
                # 强制刷新索引
                self.es_client.indices.refresh(index=self.es_index_name)
                logger.info("✅ 索引刷新完成，数据已可搜索")
            else:
                logger.warning("⚠️ 没有数据需要同步")
            
        except Exception as e:
            logger.error(f"❌ 同步最新模板数据失败: {e}")
    

    
    def search_templates(self, query: str) -> str:
        """
        搜索模版 - 主要接口
        
        Args:
            query: 自然语言查询
            
        Returns:
            模版内容字符串
        """
        try:
            logger.info(f"🔍 模版搜索开始: {query}")
            
            # 支持多种输入格式
            if isinstance(query, list):
                combined_query = " ".join(query)
            else:
                combined_query = str(query)
            
            logger.info(f"🔗 处理后查询: {combined_query}")
            
            # 使用ElasticSearch搜索
            if self.es_client:
                logger.info("🚀 使用ElasticSearch搜索模式")
                
                # ElasticSearch搜索获取top1结果
                es_candidates = self._search_templates_with_es(combined_query, size=1)
                
                if es_candidates:
                    # 直接获取最佳匹配的report_guide内容
                    best_candidate = es_candidates[0]
                    guide_id = best_candidate.get('guide_id')
                    
                    if guide_id:
                        full_template = self._mysql_get_report_guide_by_id(guide_id)
                        if full_template:
                            best_report_guide = full_template.get('report_guide')
                            
                            if best_report_guide:
                                result_text = f"✅ 模版搜索成功 (ElasticSearch)，已找到最佳匹配的报告指南：\n\n"
                                result_text += f"📋 **报告指南内容**：\n{best_report_guide}\n"
                                
                                logger.info(f"✅ ElasticSearch模式成功找到最佳报告指南")
                                
                                # 更新使用频率统计
                                try:
                                    self._mysql_update_report_guide_usage(guide_id)
                                except:
                                    pass  # 忽略统计更新错误
                                
                                return result_text
                            else:
                                logger.warning("⚠️ 找到模板但report_guide为空")
                        else:
                            logger.warning("⚠️ 无法从MySQL获取完整模板数据")
                    else:
                        logger.warning("⚠️ ElasticSearch结果缺少guide_id")
                else:
                    logger.info("📭 ElasticSearch未找到候选模板")
                
                # ElasticSearch模式未找到结果
                return f"❌ 模版搜索 (ElasticSearch): 未找到匹配模板，建议尝试不同的查询词"
            
            else:
                # ElasticSearch不可用
                logger.error("❌ ElasticSearch不可用")
                return f"❌ 模版搜索失败: ElasticSearch服务不可用"
                
        except Exception as e:
            logger.error(f"❌ 模版搜索执行失败: {e}")
            return f"❌ 模版搜索失败: {str(e)}"
    
    def search_templates_by_params(self, params: Dict[str, Any]) -> str:
        """
        通过参数字典搜索模版（兼容原接口格式）
        
        Args:
            params: 参数字典，包含queries字段
            
        Returns:
            模版内容字符串
        """
        try:
            queries = params.get("queries", [])
            
            # 合并所有查询为一个综合查询
            if isinstance(queries, list):
                combined_query = " ".join(queries)
            else:
                combined_query = str(queries)
            
            return self.search_templates(combined_query)
            
        except Exception as e:
            logger.error(f"❌ 参数搜索失败: {e}")
            return f"❌ 参数搜索失败: {str(e)}"
    
    def _search_templates_with_es(self, query: str, size: int = 1) -> List[Dict[str, Any]]:
        """使用ElasticSearch搜索模板（召回阶段）"""
        try:
            # 构建双字段查询：只搜索template_name和guide_summary
            search_body = {
                "size": size,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "template_name^2",    # 模板名称权重较高
                            "guide_summary^3"     # 指南总结权重最高
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                },
                "sort": [
                    {"_score": {"order": "desc"}},
                    {"usage_frequency": {"order": "desc"}}
                ]
            }
            
            response = self.es_client.search(index=self.es_index_name, body=search_body)
            
            results = []
            for hit in response['hits']['hits']:
                result = hit['_source']
                result['es_score'] = hit['_score']
                results.append(result)
            
            logger.info(f"🔍 ElasticSearch召回 {len(results)} 个候选模板")
            return results
            
        except Exception as e:
            logger.error(f"❌ ElasticSearch搜索失败: {e}")
            return []
    

    
    def _mysql_search_report_guides(self, query: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        """从MySQL搜索报告指南模板"""
        try:
            with mysql_manager.get_cursor() as cursor:
                base_sql = """
                SELECT rgt.guide_id, rgt.document_type_id, rgt.template_name, rgt.project_category,
                       rgt.target_objects, rgt.report_guide, rgt.guide_summary, rgt.usage_frequency, rgt.created_at,
                       dt.type_name, dt.category
                FROM report_guide_templates rgt
                LEFT JOIN document_types dt ON rgt.document_type_id = dt.type_id
                WHERE 1=1
                """
                
                params = []
                
                if query:
                    base_sql += " AND (rgt.template_name LIKE %s OR rgt.project_category LIKE %s OR dt.type_name LIKE %s)"
                    search_pattern = f"%{query}%"
                    params.extend([search_pattern, search_pattern, search_pattern])
                
                base_sql += " ORDER BY rgt.usage_frequency DESC, rgt.created_at DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(base_sql, params)
                results = cursor.fetchall()
                
                report_guides = []
                for result in results:
                    guide = {
                        'guide_id': result['guide_id'],
                        'document_type_id': result['document_type_id'],
                        'template_name': result['template_name'],
                        'project_category': result['project_category'],
                        'target_objects': json.loads(result['target_objects']) if result['target_objects'] else [],
                        'report_guide': json.loads(result['report_guide']) if result['report_guide'] else {},
                        'guide_summary': result['guide_summary'] if result['guide_summary'] else "",
                        'usage_frequency': result['usage_frequency'],
                        'created_at': result['created_at'].isoformat() if result['created_at'] else "",
                        'document_type_name': result['type_name'],
                        'document_category': result['category']
                    }
                    report_guides.append(guide)
                
                logger.info(f"从MySQL搜索到 {len(report_guides)} 个报告指南")
                return report_guides
            
        except Exception as e:
            logger.error(f"MySQL搜索报告指南失败: {e}")
            return []

    def _mysql_get_report_guide_by_id(self, guide_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取报告指南"""
        try:
            with mysql_manager.get_cursor() as cursor:
                sql = """
                SELECT rgt.guide_id, rgt.document_type_id, rgt.template_name, rgt.project_category,
                       rgt.target_objects, rgt.report_guide, rgt.guide_summary, rgt.usage_frequency, rgt.created_at,
                       dt.type_name, dt.category
                FROM report_guide_templates rgt
                LEFT JOIN document_types dt ON rgt.document_type_id = dt.type_id
                WHERE rgt.guide_id = %s
                """
                
                cursor.execute(sql, (guide_id,))
                result = cursor.fetchone()
                
                if result:
                    return {
                        'guide_id': result['guide_id'],
                        'document_type_id': result['document_type_id'],
                        'template_name': result['template_name'],
                        'project_category': result['project_category'],
                        'target_objects': json.loads(result['target_objects']) if result['target_objects'] else [],
                        'report_guide': json.loads(result['report_guide']) if result['report_guide'] else {},
                        'guide_summary': result['guide_summary'] if result['guide_summary'] else "",
                        'usage_frequency': result['usage_frequency'],
                        'created_at': result['created_at'].isoformat() if result['created_at'] else "",
                        'document_type_name': result['type_name'],
                        'document_category': result['category']
                    }
                
                return None
            
        except Exception as e:
            logger.error(f"根据ID获取报告指南失败: {e}")
            return None

    def _mysql_update_report_guide_usage(self, guide_id: str) -> bool:
        """更新报告指南使用频率"""
        try:
            with mysql_manager.get_cursor() as cursor:
                sql = """
                UPDATE report_guide_templates 
                SET usage_frequency = usage_frequency + 1, last_updated = NOW()
                WHERE guide_id = %s
                """
                
                cursor.execute(sql, (guide_id,))
                
                if cursor.rowcount > 0:
                    logger.info(f"成功更新报告指南 {guide_id} 的使用频率")
                    return True
                else:
                    logger.warning(f"报告指南 {guide_id} 不存在")
                    return False
            
        except Exception as e:
            logger.error(f"更新报告指南使用频率失败: {e}")
            return False 