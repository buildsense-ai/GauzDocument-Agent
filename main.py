#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立工具交互式测试主程序
让用户选择使用模版搜索或文档搜索工具
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

# 配置简单日志
logging.basicConfig(level=logging.WARNING)

def setup_environment():
    """设置运行环境"""
    storage_dir = os.getenv("RAG_STORAGE_DIR", "final_chromadb")
    os.makedirs(storage_dir, exist_ok=True)
    os.environ.setdefault("PYTHONPATH", ".")
    print("✅ 环境设置完成")

def show_welcome():
    """显示欢迎信息"""
    print("\n" + "="*60)
    print("🔍 独立工具交互式测试系统")
    print("="*60)
    print("💡 功能说明:")
    print("   1️⃣ 模版搜索工具 - ElasticSearch搜索模版内容")
    print("   2️⃣ 文档搜索工具 - 向量搜索文档内容(文本+图片+表格)")
    print("   0️⃣ 退出系统")
    print("="*60)

def get_user_choice():
    """获取用户选择"""
    while True:
        print("\n🎯 请选择工具:")
        print("  [1] 模版搜索 (Template Search)")
        print("  [2] 文档搜索 (Document Search)")
        print("  [0] 退出")
        
        choice = input("\n👉 请输入选择 (0/1/2): ").strip()
        
        if choice in ['0', '1', '2']:
            return choice
        else:
            print("❌ 无效选择，请输入 0、1 或 2")

def get_query():
    """获取用户查询"""
    while True:
        query = input("\n📝 请输入查询内容: ").strip()
        if query:
            return query
        else:
            print("❌ 查询内容不能为空，请重新输入")

def save_search_results(query, project_name, top_k, content_type, result_json):
    """保存文档搜索结果到results目录"""
    try:
        # 确保results目录存在
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)
        
        # 生成文件名 (时间戳 + 查询关键词)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理查询字符串用于文件名
        safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_query = safe_query.replace(' ', '_')[:20]  # 限制长度
        filename = f"document_search_{timestamp}_{safe_query}.json"
        filepath = os.path.join(results_dir, filename)
        
        # 构建完整的搜索记录
        search_record = {
            "search_type": "document_search",
            "search_info": {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "project_name": project_name,
                "top_k": top_k,
                "content_type": content_type
            },
            "results": json.loads(result_json)
        }
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(search_record, f, ensure_ascii=False, indent=2)
        
        return filepath
        
    except Exception as e:
        print(f"⚠️ 保存文件时出错: {e}")
        return None

def save_template_results(query, template_content):
    """保存模版搜索结果到results目录"""
    try:
        # 确保results目录存在
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)
        
        # 生成文件名 (时间戳 + 查询关键词)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理查询字符串用于文件名
        safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_query = safe_query.replace(' ', '_')[:20]  # 限制长度
        filename = f"template_search_{timestamp}_{safe_query}.json"
        filepath = os.path.join(results_dir, filename)
        
        # 构建完整的搜索记录
        search_record = {
            "search_type": "template_search",
            "search_info": {
                "timestamp": datetime.now().isoformat(),
                "query": query
            },
            "results": {
                "status": "success" if template_content else "no_results",
                "template_content": template_content,
                "content_length": len(template_content) if template_content else 0
            }
        }
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(search_record, f, ensure_ascii=False, indent=2)
        
        return filepath
        
    except Exception as e:
        print(f"⚠️ 保存文件时出错: {e}")
        return None

def test_template_search():
    """测试模版搜索工具"""
    print("\n" + "🔍 模版搜索工具测试")
    print("-" * 40)
    
    try:
        # 导入和初始化工具
        from template_search_tool import TemplateSearchTool
        print("🔧 正在初始化模版搜索工具...")
        tool = TemplateSearchTool()
        print("✅ 模版搜索工具初始化成功")
        
        # 获取用户查询
        query = get_query()
        print(f"\n🚀 开始搜索: {query}")
        
        # 执行搜索
        result = tool.search_templates(query)
        
        # 显示结果
        print("\n📋 搜索结果:")
        print("-" * 40)
        if result:
            print(f"✅ 找到模版内容 (长度: {len(result)}字符)")
            print("\n📄 模版内容:")
            print(result)
            
            # 自动保存结果到文件
            print(f"\n💾 正在保存模版搜索结果到results目录...")
            saved_file = save_template_results(query, result)
            if saved_file:
                print(f"✅ 模版结果已保存到: {saved_file}")
            else:
                print("❌ 保存失败")
        else:
            print("❌ 未找到相关模版")
        
        return True
        
    except Exception as e:
        print(f"❌ 模版搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_document_search():
    """测试文档搜索工具"""
    print("\n" + "🔍 文档搜索工具测试")
    print("-" * 40)
    
    try:
        # 导入和初始化工具
        from document_search_tool import DocumentSearchTool
        print("🔧 正在初始化文档搜索工具...")
        storage_dir = os.getenv("RAG_STORAGE_DIR", "final_chromadb")
        tool = DocumentSearchTool(storage_dir=storage_dir)
        print("✅ 文档搜索工具初始化成功")
        
        # 获取用户查询
        query = get_query()
        
        # 使用默认参数
        project_name = "医灵古庙"  # 默认项目名称
        top_k = 5               # 默认返回结果数量
        content_type = "all"    # 默认搜索所有类型
        
        print(f"\n⚙️ 使用默认搜索参数:")
        print(f"📁 项目名称: {project_name}")
        print(f"📊 返回数量: {top_k}")
        print(f"🎯 内容类型: {content_type}")
        
        print(f"\n🚀 开始搜索: {query}")
        print(f"📁 项目: {project_name}")
        print(f"📊 数量: {top_k}")
        print(f"🎯 类型: {content_type}")
        
        # 执行搜索
        result_json = tool.search_documents(
            query_text=query,
            project_name=project_name,
            top_k=top_k,
            content_type=content_type
        )
        
        # 解析和显示结果
        result = json.loads(result_json)
        status = result.get("status", "unknown")
        
        print("\n📋 搜索结果:")
        print("-" * 40)
        
        if status == "success":
            text_results = result.get("retrieved_text", [])
            image_results = result.get("retrieved_image", [])
            table_results = result.get("retrieved_table", [])
            
            print(f"✅ 搜索成功!")
            print(f"📝 文本内容: {len(text_results)}个")
            print(f"🖼️ 图片内容: {len(image_results)}个")
            print(f"📊 表格内容: {len(table_results)}个")
            
            # 显示文本结果预览
            if text_results:
                print(f"\n📝 文本内容预览:")
                for i, text_item in enumerate(text_results[:3], 1):
                    content = text_item.get("content", "")
                    chapter_title = text_item.get("chapter_title", "")
                    print(f"  {i}. {chapter_title}: {content[:100]}...")
            
            # 显示图片结果预览
            if image_results:
                print(f"\n🖼️ 图片内容预览:")
                for i, image_item in enumerate(image_results[:3], 1):
                    caption = image_item.get("caption", "")
                    image_url = image_item.get("image_url", "")
                    print(f"  {i}. {caption}: {image_url}")
            
            # 显示表格结果预览
            if table_results:
                print(f"\n📊 表格内容预览:")
                for i, table_item in enumerate(table_results[:3], 1):
                    caption = table_item.get("caption", "")
                    table_url = table_item.get("table_url", "")
                    print(f"  {i}. {caption}: {table_url}")
            
            # 自动保存结果到文件
            print(f"\n💾 正在保存搜索结果到results目录...")
            saved_file = save_search_results(query, project_name, top_k, content_type, result_json)
            if saved_file:
                print(f"✅ 结果已保存到: {saved_file}")
            else:
                print("❌ 保存失败")
            
            # 完整JSON结果已保存到文件，不在控制台显示
            print(f"\n📄 完整JSON结果已保存到文件中")
        
        else:
            print(f"❌ 搜索失败: {status}")
            message = result.get("message", "未知错误")
            print(f"错误信息: {message}")
        
        return True
        
    except Exception as e:
        print(f"❌ 文档搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主程序"""
    try:
        # 设置环境
        setup_environment()
        
        # 显示欢迎信息
        show_welcome()
        
        # 主循环
        while True:
            choice = get_user_choice()
            
            if choice == '0':
                print("\n👋 感谢使用，再见！")
                break
            
            elif choice == '1':
                print("\n" + "="*60)
                success = test_template_search()
                if success:
                    print("\n✅ 模版搜索测试完成")
                else:
                    print("\n❌ 模版搜索测试失败")
            
            elif choice == '2':
                print("\n" + "="*60)
                success = test_document_search()
                if success:
                    print("\n✅ 文档搜索测试完成")
                else:
                    print("\n❌ 文档搜索测试失败")
            
            # 询问是否继续
            print("\n" + "-"*60)
            continue_choice = input("🔄 是否继续测试其他功能? (y/n): ").strip().lower()
            if continue_choice not in ['y', 'yes', '是', '继续']:
                print("\n👋 感谢使用，再见！")
                break
    
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，程序退出")
    except Exception as e:
        print(f"\n❌ 程序运行错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()