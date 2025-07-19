#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG检索工具系统 - 主启动脚本
React Agent：可视化思考模式（两个核心工具）
- 模版搜索工具：支持三轮放宽策略
- 章节内容搜索工具：支持三步融合搜索
"""

import sys
import os
import json
import sqlite3
import shutil
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)

# 配置日志 - 移除时间戳，专注于AI思考过程
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

def setup_environment():
    """设置环境"""
    # 从环境变量获取目录配置
    storage_dir = os.getenv("RAG_STORAGE_DIR", "pdf_embedding_storage")
    
    # 创建必要的目录
    os.makedirs(storage_dir, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # 设置环境变量（如果需要）
    os.environ.setdefault("PYTHONPATH", ".")
    
    # 检查必要的环境变量
    # 检查DeepSeek API密钥（用于对话）
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        logger.error("缺少DeepSeek API密钥")
        print("❌ 缺少DeepSeek API密钥，请在环境变量中设置 DEEPSEEK_API_KEY")
        sys.exit(1)
    
    # 检查Qwen API密钥（用于embedding）
    qwen_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not qwen_key:
        logger.error("缺少Qwen API密钥")
        print("❌ 缺少Qwen API密钥，请在环境变量中设置 QWEN_API_KEY 或 DASHSCOPE_API_KEY")
        sys.exit(1)
    
    print("✅ 环境变量检查完成：DeepSeek用于对话，Qwen用于embedding")
    
    logger.info("环境设置完成")

try:
    from react_rag_agent import SimplifiedReactAgent
    print("✅ React Agent组件导入成功")
except ImportError as e:
    print(f"❌ 组件导入失败: {e}")
    sys.exit(1)

class SimpleRAGSystem:
    """简化的RAG检索系统 - React Agent"""
    
    def __init__(self):
        self.react_agent = None
        self.init_components()
    
    def init_components(self):
        """初始化系统组件"""
        try:
            print("🔧 正在初始化智能检索系统...")
            
            # 获取存储目录配置
            storage_dir = os.getenv("RAG_STORAGE_DIR", "pdf_embedding_storage")
            
            # 初始化React Agent（简化工具系统）
            print("🤖 初始化React Agent (简化工具系统)...")
            self.react_agent = SimplifiedReactAgent(storage_dir=storage_dir)
            print("✅ React Agent初始化成功")
            
            print("🎉 系统初始化完成！")
        except Exception as e:
            print(f"❌ 系统初始化失败: {e}")
            print(f"错误详情: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def show_welcome(self):
        """显示欢迎信息"""
        print("\n" + "="*60)
        print("🤖 智能文档检索系统 - React Agent")
        print("="*60)
        print("💡 系统特性:")
        print("   🔍 React Agent - 优化版可视化思考 (3步循环)")
        print("   🚀 Qwen API - 高性能语言模型")
        print("   🛠️ 简化工具系统 - 两个核心工具")
        print("   📈 三轮放宽策略 - 模版搜索智能降级")
        print("   🔄 三步融合搜索 - 元数据+向量+BM25")
        print("   🧠 自动决策 - AI智能选择搜索策略")
        print("="*60)
    
    def show_agent_info(self):
        """显示Agent信息"""
        print("\n🎯 React Agent - 可视化思考模式:")
        print("="*40)
        print("   ✨ 特点：能看到AI每一步的思考过程")
        print("   🎯 适用：演示、学习、调试")
        print("   🛠️ 工具：两个核心工具（模版搜索+章节内容搜索）")
        print("   📊 策略：三轮放宽 + 三步融合")
        print("-"*40)
    
    def collect_queries_for_react(self):
        """为React Agent收集单个查询"""
        print("\n📝 React Agent - 单查询模式:")
        print("💡 建议查询示例:")
        print("   • 医灵古庙评估报告")
        print("   • 古庙修缮方案模板")
        print("   • 文物保护技术标准")
        print("   • 古庙历史背景资料")
        print("   • 建筑文化价值分析")
        print("-"*50)
        
        while True:
            query = input("\n🔍 请输入您的查询: ").strip()
            
            if query.lower() == 'quit':
                print("👋 再见！")
                sys.exit(0)
            
            if query:
                print(f"✅ 查询已记录: {query}")
                return query
            else:
                print("❌ 请输入有效的查询内容")
    

    
    def process_react_query(self, query):
        """使用React Agent处理单个查询"""
        print(f"\n🚀 React Agent开始处理查询...")
        print("="*60)
        
        try:
            # 使用React Agent处理查询
            result_json = self.react_agent.process_query(query)
            result_data = json.loads(result_json)
            
            # 显示React思考过程
            self.display_react_process(result_data)
            
            # 保存结果
            self.save_react_results(query, result_data)
            
            return True
            
        except Exception as e:
            print(f"❌ React Agent处理失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    

    
    def display_react_process(self, result_data):
        """显示React Agent的思考过程"""
        print("\n🤔 React Agent思考过程:")
        print("="*50)
        
        if result_data.get("status") == "success":
            react_process = result_data.get("react_process", {})
            steps = react_process.get("steps", [])
            
            for step in steps:
                step_num = step.get("step_number")
                thought = step.get("thought", "")
                action = step.get("action", "")
                observation = step.get("observation", "")
                
                print(f"\n🔄 步骤 {step_num}:")
                print(f"   💭 思考: {thought}")
                print(f"   🎯 行动: {action}")
                print(f"   👀 观察: {observation[:200]}...")
            
            print(f"\n✅ 最终答案:")
            print("-"*30)
            final_answer = result_data.get("final_answer", "")
            print(final_answer)
            
        else:
            print(f"❌ React处理失败: {result_data.get('error', '未知错误')}")
    

    
    def save_react_results(self, query, result_data):
        """保存React Agent结果"""
        try:
            # 准备保存数据
            save_data = {
                "agent_type": "react",
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "status": result_data.get("status"),
                "execution_time": result_data.get("execution_time"),
                "react_process": result_data.get("react_process"),
                "final_answer": result_data.get("final_answer"),
                "metadata": result_data.get("metadata")
            }
            
            # 保存到文件
            os.makedirs('results', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"results/react_agent_result_{timestamp}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 React结果已保存到: {filename}")
            
        except Exception as e:
            print(f"⚠️ 保存React结果失败: {e}")
    

    
    def run(self):
        """运行系统主循环"""
        self.show_welcome()
        
        while True:
            print("\n" + "-"*60)
            print("🔍 开始新一轮查询")
            
            # 显示Agent信息
            self.show_agent_info()
            
            # React Agent模式：单查询处理
            query = self.collect_queries_for_react()
            success = self.process_react_query(query)
            
            if success:
                print(f"\n✨ React Agent处理完成！")
            else:
                print(f"\n❌ React Agent处理失败")
            
            # 询问是否继续
            print("\n" + "-"*60)
            while True:
                continue_choice = input("🔄 是否继续进行新的查询？(y/n): ").strip().lower()
                if continue_choice in ['y', 'yes', '是', '继续']:
                    break
                elif continue_choice in ['n', 'no', '否', '退出']:
                    print("👋 感谢使用智能检索系统，再见！")
                    return
                else:
                    print("❌ 请输入 y/yes 继续，或 n/no 退出")

def main():
    """主程序入口"""
    setup_environment()
    
    try:
        system = SimpleRAGSystem()
        system.run()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，系统退出")
    except Exception as e:
        print(f"\n❌ 系统运行错误: {e}")
        logger.error(f"系统运行错误: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 