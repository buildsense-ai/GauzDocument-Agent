"""
运行和测试长文生成流程的脚本
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import json
from src.generation_agent.orchestrator_agent import OrchestratorAgent
from src.generation_agent.section_writer_agent import SectionWriterAgent

def main():
    """主执行函数"""
    print("="*50)
    print("🚀 开始长文生成流程（模拟） 🚀")
    print("="*50)

    source_document_id = "医灵古庙设计方案.pdf"
    target_document_description = "医灵古庙文物评估方案"

    # 1. 初始化总监Agent并生成大纲
    orchestrator = OrchestratorAgent()
    outline = orchestrator.generate_outline(source_document_id, target_document_description)

    print("\n" + "="*20 + " 生成的大纲 " + "="*20)
    print(json.dumps(outline, indent=2, ensure_ascii=False))
    print("="*52 + "\n")

    # 2. 循环处理每个章节
    section_writer = SectionWriterAgent(source_document_id)
    full_document_context = {}

    for section in outline:
        chapter_id = section['chapter']
        title = section['title']
        
        context_for_section = section_writer.gather_context_for_section(title)
        full_document_context[chapter_id] = {"title": title, "context": context_for_section}
        print("-" * 50)

    print("\n✅ 所有章节资料收集完毕！最终的上下文结构：")
    print(json.dumps(full_document_context, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

