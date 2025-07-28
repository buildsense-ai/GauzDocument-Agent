"""
模版搜索工具 - MySQL FULLTEXT搜索
独立工具，输入自然语言query，输出模版内容
"""
import os
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
# 移除ElasticSearch依赖，改用MySQL FULLTEXT搜索
import pymysql
import jieba
import jieba.posseg as pseg

# 加载环境变量
load_dotenv()

# 导入组件 - 使用稳定的连接池
from mysql_connection_pool import mysql_manager

logger = logging.getLogger(__name__)

class TemplateSearchTool:
    """
    模版搜索工具 - MySQL FULLTEXT搜索
    
    功能：
    1. jieba分词提取关键词
    2. MySQL FULLTEXT搜索匹配模版
    3. 返回最佳匹配的模版内容
    """
    
    def __init__(self):
        """初始化模版搜索工具"""
        # 初始化jieba（可选，用于更好的分词效果）
        self._init_jieba()
        
        # 定义停用词列表
        self.stop_words = {
            '我', '需要', '一个', '关于', '的', '了', '在', '是', '有', '和', '与', '或者', 
            '以及', '还有', '如何', '怎么', '什么', '哪个', '这个', '那个', '给我', '帮我',
            '请', '谢谢', '模板', '模版', '报告', '文档', '资料', '内容'
        }
        
        logger.info("✅ 模版搜索工具初始化完成")
        logger.info("🔍 功能: jieba分词 + MySQL FULLTEXT搜索")
        logger.info("📝 FULLTEXT搜索: template_name, guide_summary")
        logger.info("📝 LIKE回退搜索: template_name, guide_summary, report_guide")
    
    def _init_jieba(self):
        """初始化jieba分词器"""
        try:
            # 设置jieba为精确模式
            jieba.setLogLevel(logging.INFO)
            logger.info("✅ jieba分词器初始化完成")
        except Exception as e:
            logger.error(f"❌ jieba初始化失败: {e}")
    
    def _extract_keywords_with_jieba(self, query: str) -> str:
        """使用jieba分词提取关键词"""
        try:
            # 使用jieba进行词性标注分词
            words = pseg.cut(query)
            
            # 提取有效关键词（名词、动词、形容词等）
            keywords = []
            for word, flag in words:
                # 过滤停用词和单字符
                if (len(word) >= 2 and 
                    word not in self.stop_words and
                    flag in ['n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'a', 'an']):  # 名词、动词、形容词
                    keywords.append(word)
            
            # 如果没有提取到关键词，使用原查询
            if not keywords:
                # 简单去除常见停用词
                cleaned_query = query
                for stop_word in self.stop_words:
                    cleaned_query = cleaned_query.replace(stop_word, ' ')
                return cleaned_query.strip()
            
            result = ' '.join(keywords)
            logger.info(f"🔪 jieba分词结果: '{query}' -> '{result}'")
            return result
            
        except Exception as e:
            logger.error(f"❌ jieba分词失败: {e}")
            # 如果分词失败，返回原查询
            return query
    
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
            
            # 使用jieba分词提取关键词
            processed_query = self._extract_keywords_with_jieba(combined_query)
            
            logger.info(f"🔗 处理后查询: {processed_query}")
            
            # 使用MySQL FULLTEXT搜索
            mysql_candidates = self._search_templates_with_mysql_fulltext(processed_query, limit=1)
            
            if mysql_candidates:
                # 直接返回最佳匹配的report_guide内容
                best_candidate = mysql_candidates[0]
                guide_id = best_candidate.get('guide_id')
                report_guide = best_candidate.get('report_guide')
                template_name = best_candidate.get('template_name', '未知模板')
                
                if report_guide:
                    # 将report_guide转换为适合返回的格式
                    if isinstance(report_guide, dict):
                        # 如果是字典对象，转换为JSON字符串
                        report_guide_content = json.dumps(report_guide, ensure_ascii=False, indent=2)
                    else:
                        # 如果已经是字符串，直接使用
                        report_guide_content = str(report_guide)
                    
                    logger.info(f"✅ MySQL FULLTEXT模式成功找到最佳报告指南: {template_name}")
                    
                    # 更新使用频率统计
                    try:
                        if guide_id:
                            self._mysql_update_report_guide_usage(guide_id)
                    except:
                        pass  # 忽略统计更新错误
                    
                    # 直接返回report_guide内容，不添加额外的格式化文本
                    return report_guide_content
                else:
                    logger.warning("⚠️ 找到模板但report_guide为空")
            else:
                logger.info("📭 MySQL FULLTEXT未找到候选模板")
            
            # 未找到结果
            return f"❌ 模版搜索 (MySQL FULLTEXT): 未找到匹配模板，建议尝试不同的查询词"
                
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
    
    def _search_templates_with_mysql_fulltext(self, query: str, limit: int = 1) -> List[Dict[str, Any]]:
        """使用MySQL FULLTEXT搜索模板"""
        try:
            with mysql_manager.get_cursor() as cursor:
                # 使用MySQL FULLTEXT搜索，只搜索template_name和guide_summary字段
                # 注意：report_guide通常为JSON类型，不支持FULLTEXT索引
                sql = """
                SELECT rgt.guide_id, rgt.template_name, rgt.report_guide, rgt.guide_summary, 
                       rgt.usage_frequency, rgt.created_at,
                       MATCH(rgt.template_name, rgt.guide_summary) AGAINST(%s) AS relevance
                FROM report_guide_templates rgt
                WHERE MATCH(rgt.template_name, rgt.guide_summary) AGAINST(%s)
                ORDER BY relevance DESC, rgt.usage_frequency DESC
                LIMIT %s
                """
                
                cursor.execute(sql, (query, query, limit))
                results = cursor.fetchall()
                
                templates = []
                for result in results:
                    template = {
                        'guide_id': result['guide_id'],
                        'template_name': result['template_name'],
                        'report_guide': json.loads(result['report_guide']) if result['report_guide'] else {},
                        'guide_summary': result['guide_summary'] if result['guide_summary'] else "",
                        'usage_frequency': result['usage_frequency'],
                        'created_at': result['created_at'].isoformat() if result['created_at'] else "",
                        'relevance': float(result['relevance'])
                    }
                    templates.append(template)
                
                logger.info(f"🔍 MySQL FULLTEXT搜索找到 {len(templates)} 个候选模板")
                return templates
            
        except Exception as e:
            logger.error(f"❌ MySQL FULLTEXT搜索失败: {e}")
            # 如果FULLTEXT搜索失败，回退到LIKE搜索
            return self._search_templates_with_mysql_like(query, limit)
    
    def _search_templates_with_mysql_like(self, query: str, limit: int = 1) -> List[Dict[str, Any]]:
        """使用MySQL LIKE搜索模板（FULLTEXT搜索的回退方案）"""
        try:
            with mysql_manager.get_cursor() as cursor:
                # 使用LIKE搜索作为回退方案
                sql = """
                SELECT rgt.guide_id, rgt.template_name, rgt.report_guide, rgt.guide_summary, 
                       rgt.usage_frequency, rgt.created_at
                FROM report_guide_templates rgt
                WHERE rgt.template_name LIKE %s 
                   OR rgt.guide_summary LIKE %s
                   OR rgt.report_guide LIKE %s
                ORDER BY rgt.usage_frequency DESC, rgt.created_at DESC
                LIMIT %s
                """
                
                search_pattern = f"%{query}%"
                cursor.execute(sql, (search_pattern, search_pattern, search_pattern, limit))
                results = cursor.fetchall()
                
                templates = []
                for result in results:
                    template = {
                        'guide_id': result['guide_id'],
                        'template_name': result['template_name'],
                        'report_guide': json.loads(result['report_guide']) if result['report_guide'] else {},
                        'guide_summary': result['guide_summary'] if result['guide_summary'] else "",
                        'usage_frequency': result['usage_frequency'],
                        'created_at': result['created_at'].isoformat() if result['created_at'] else "",
                        'relevance': 1.0  # LIKE搜索没有相关性分数，设为固定值
                    }
                    templates.append(template)
                
                logger.info(f"🔍 MySQL LIKE搜索找到 {len(templates)} 个候选模板")
                return templates
            
        except Exception as e:
            logger.error(f"❌ MySQL LIKE搜索失败: {e}")
            return []
    

    
# 移除旧的MySQL搜索方法，已由新的FULLTEXT搜索方法替代

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