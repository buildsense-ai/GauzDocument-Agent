#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_local_rag.py

测试本地RAG工具的集成是否正常工作。
"""

import sys
import os

# 添加long_generator目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from services import search_vectordata, get_info, get_summary, get_image_info_from_local
from process_image import get_image_info
from config import Config


def test_vector_search():
    """测试向量搜索功能"""
    print("🔍 测试向量搜索功能")
    print("=" * 50)
    
    test_queries = [
        "医灵古庙",
        "刘氏宗祠",
        "可塞古庙",
        "文物保护"
    ]
    
    for query in test_queries:
        print(f"\n📝 搜索查询: '{query}'")
        print("-" * 30)
        
        try:
            results = search_vectordata(query, top_k=3)
            
            if results:
                print(f"✅ 找到 {len(results)} 条结果")
                for i, result in enumerate(results, 1):
                    preview = result[:100] + "..." if len(result) > 100 else result
                    print(f"  {i}. {preview}")
            else:
                print("⚠️ 未找到结果")
                
        except Exception as e:
            print(f"❌ 搜索失败: {e}")


def test_info_functions():
    """测试信息获取函数"""
    print("\n📋 测试信息获取功能")
    print("=" * 50)
    
    print("\n🔍 测试 get_info 函数")
    print("-" * 30)
    try:
        info = get_info("项目概况", top_k=2)
        if info:
            preview = info[:200] + "..." if len(info) > 200 else info
            print(f"✅ 获取信息成功: {preview}")
        else:
            print("⚠️ 未获取到信息")
    except Exception as e:
        print(f"❌ 获取信息失败: {e}")
    
    print("\n📝 测试 get_summary 函数")
    print("-" * 30)
    try:
        summary = get_summary("总结", top_k=1)
        if summary:
            preview = summary[:200] + "..." if len(summary) > 200 else summary
            print(f"✅ 获取总结成功: {preview}")
        else:
            print("⚠️ 未获取到总结")
    except Exception as e:
        print(f"❌ 获取总结失败: {e}")


def test_image_search():
    """测试图片搜索功能"""
    print("\n🖼️ 测试图片搜索功能")
    print("=" * 50)
    
    test_queries = [
        "古庙",
        "建筑",
        "可塞古庙"
    ]
    
    for query in test_queries:
        print(f"\n🖼️ 图片搜索查询: '{query}'")
        print("-" * 30)
        
        try:
            # 测试本地图片搜索
            print("🔹 测试本地RAG图片搜索:")
            local_results = get_image_info_from_local(query, top_k=3)
            
            if local_results:
                print(f"✅ 找到 {len(local_results)} 张图片")
                for i, url in enumerate(local_results, 1):
                    print(f"  {i}. {url}")
            else:
                print("⚠️ 未找到图片")
            
            print("\n🔹 测试process_image模块:")
            # 测试process_image模块的get_image_info函数
            image_results = get_image_info(query, top_k=3)
            
            if image_results:
                print(f"✅ 找到 {len(image_results)} 张图片")
                for i, url in enumerate(image_results, 1):
                    print(f"  {i}. {url}")
            else:
                print("⚠️ 未找到图片")
                
        except Exception as e:
            print(f"❌ 图片搜索失败: {e}")


def test_config():
    """测试配置功能"""
    print("\n⚙️ 测试配置功能")
    print("=" * 50)
    
    try:
        rag_config = Config.get_rag_config()
        print("✅ RAG配置获取成功:")
        for key, value in rag_config.items():
            print(f"  - {key}: {value}")
    except Exception as e:
        print(f"❌ 配置获取失败: {e}")


def main():
    """主测试函数"""
    print("🎯 本地RAG工具集成测试")
    print("=" * 60)
    
    # 检查基本配置
    print(f"✅ 使用本地RAG: {Config.USE_LOCAL_RAG}")
    print(f"✅ 项目隔离: {Config.USE_PROJECT_ISOLATION}")
    print(f"✅ 默认搜索数量: {Config.SEARCH_DEFAULT_TOP_K}")
    
    # 运行各项测试
    try:
        test_vector_search()
        test_info_functions()
        test_image_search()
        test_config()
        
        print("\n" + "=" * 60)
        print("🎉 本地RAG工具集成测试完成！")
        print("\n📋 测试总结:")
        print("1. ✅ 向量搜索功能测试")
        print("2. ✅ 信息获取功能测试")
        print("3. ✅ 图片搜索功能测试")
        print("4. ✅ 配置功能测试")
        
        print("\n💡 使用建议:")
        print("- 确保已有向量数据在本地RAG存储中")
        print("- 如果搜索结果为空，检查数据是否正确导入")
        print("- 可以设置项目名称实现数据隔离")
        print("- 外部API作为备用方案自动启用")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        print("请检查本地RAG工具的安装和配置")


if __name__ == "__main__":
    main() 