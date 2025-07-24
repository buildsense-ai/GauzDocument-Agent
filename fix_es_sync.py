#!/usr/bin/env python3
"""
手动同步MySQL数据到ElasticSearch
"""

import json
from mysql_connection_pool import mysql_manager
from elasticsearch import Elasticsearch

def sync_mysql_to_es():
    """手动同步MySQL数据到ElasticSearch"""
    print('🔄 开始手动同步MySQL数据到ElasticSearch...')
    
    # 连接ElasticSearch
    try:
        es_client = Elasticsearch(['http://localhost:9200'])
        if not es_client.ping():
            print('❌ ElasticSearch连接失败')
            return False
        print('✅ ElasticSearch连接成功')
    except Exception as e:
        print(f'❌ ElasticSearch连接异常: {e}')
        return False
    
    # 从MySQL获取数据
    try:
        with mysql_manager.get_cursor() as cursor:
            sql = """
            SELECT rgt.guide_id, rgt.document_type_id, rgt.template_name, rgt.project_category,
                   rgt.target_objects, rgt.report_guide, rgt.guide_summary, rgt.usage_frequency, rgt.created_at,
                   dt.type_name, dt.category
            FROM report_guide_templates rgt
            LEFT JOIN document_types dt ON rgt.document_type_id = dt.type_id
            ORDER BY rgt.usage_frequency DESC
            """
            
            cursor.execute(sql)
            results = cursor.fetchall()
            
            print(f'📊 从MySQL获取到 {len(results)} 个模板')
            
            if not results:
                print('❌ MySQL中没有数据')
                return False
                
    except Exception as e:
        print(f'❌ MySQL查询失败: {e}')
        return False
    
    # 删除并重建索引
    try:
        index_name = "template_search_index"
        
        # 删除旧索引
        if es_client.indices.exists(index=index_name):
            es_client.indices.delete(index=index_name)
            print('🗑️ 删除旧索引')
        
        # 创建新索引
        mapping = {
            "mappings": {
                "properties": {
                    "guide_id": {"type": "keyword"},
                    "template_name": {"type": "text", "analyzer": "standard"},
                    "guide_summary": {"type": "text", "analyzer": "standard"},
                    "usage_frequency": {"type": "integer"},
                    "created_at": {"type": "date"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        }
        
        es_client.indices.create(index=index_name, body=mapping)
        print('✅ 创建新索引')
        
    except Exception as e:
        print(f'❌ 索引操作失败: {e}')
        return False
    
    # 批量插入数据
    try:
        actions = []
        for result in results:
            doc = {
                "guide_id": result["guide_id"],
                "template_name": result["template_name"] or "",
                "guide_summary": result["guide_summary"] or "",
                "usage_frequency": result["usage_frequency"] or 0,
                "created_at": result["created_at"].isoformat() if result["created_at"] else ""
            }
            
            action = {
                "_index": index_name,
                "_id": result["guide_id"],
                "_source": doc
            }
            actions.append(action)
        
        # 批量插入
        from elasticsearch.helpers import bulk
        success_count, failed_items = bulk(es_client, actions, index=index_name)
        
        print(f'✅ 成功插入 {success_count} 个文档')
        
        # 刷新索引
        es_client.indices.refresh(index=index_name)
        print('✅ 索引刷新完成')
        
        # 验证数据
        count_result = es_client.count(index=index_name)
        print(f'📊 ElasticSearch中现有 {count_result["count"]} 个文档')
        
        return True
        
    except Exception as e:
        print(f'❌ 数据插入失败: {e}')
        import traceback
        traceback.print_exc()
        return False

def test_es_search():
    """测试ElasticSearch搜索"""
    print('\n🔍 测试ElasticSearch搜索...')
    
    try:
        es_client = Elasticsearch(['http://localhost:9200'])
        
        # 搜索测试
        search_body = {
            "size": 3,
            "query": {
                "multi_match": {
                    "query": "文物评估",
                    "fields": ["template_name^2", "guide_summary"]
                }
            }
        }
        
        response = es_client.search(index="template_search_index", body=search_body)
        hits = response.get('hits', {}).get('hits', [])
        
        print(f'🎯 搜索到 {len(hits)} 个结果:')
        for i, hit in enumerate(hits):
            source = hit['_source']
            score = hit['_score']
            print(f'  {i+1}. {source["template_name"]} (分数: {score:.2f})')
        
        return len(hits) > 0
        
    except Exception as e:
        print(f'❌ 搜索测试失败: {e}')
        return False

if __name__ == '__main__':
    print('🛠️ ElasticSearch数据同步修复工具')
    print('=' * 50)
    
    # 同步数据
    if sync_mysql_to_es():
        print('\n✅ 数据同步成功！')
        
        # 测试搜索
        if test_es_search():
            print('✅ 搜索功能正常！')
        else:
            print('⚠️ 搜索功能异常')
    else:
        print('\n❌ 数据同步失败')
    
    mysql_manager.close()
    print('\n🔒 完成') 