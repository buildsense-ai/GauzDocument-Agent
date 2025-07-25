#!/usr/bin/env python3
import requests
import json
import time

def test_fixed_multiround():
    """测试修复后的多轮生成问题"""
    print("🔧 测试修复后的多轮ReAct循环...")
    
    url = "http://localhost:8000/react_solve"
    headers = {
        "Content-Type": "application/json",
        "x-project-id": "test123",
        "x-project-name": "医灵古庙"
    }
    data = {
        "problem": "请查询医灵古庙的历史沿革信息",
        "project_context": {
            "project_id": "test123",
            "project_name": "医灵古庙"
        }
    }
    
    print("🚀 发送测试请求...")
    print("📋 问题：", data["problem"])
    print("="*60)
    
    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=120)
        end_time = time.time()
        
        print(f"⏱️ 处理时间: {end_time - start_time:.2f}秒")
        print(f"📊 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功！")
            
            # 分析thinking_process
            thinking_process = result.get('thinking_process', [])
            print(f"\n🧠 思考过程分析 (共 {len(thinking_process)} 轮):")
            
            for i, step in enumerate(thinking_process, 1):
                print(f"\n--- 第 {i} 轮 ---")
                
                if step.get('thought'):
                    print(f"💭 Thought: {step['thought'][:80]}...")
                else:
                    print("💭 Thought: [无]")
                
                if step.get('action'):
                    print(f"🔧 Action: {step['action']}")
                    if step.get('action_input'):
                        try:
                            action_input = json.loads(step['action_input']) if isinstance(step['action_input'], str) else step['action_input']
                            print(f"📋 Action Input: {json.dumps(action_input, ensure_ascii=False)}")
                        except:
                            print(f"📋 Action Input: {step['action_input']}")
                else:
                    print("🔧 Action: [无]")
                
                if step.get('observation'):
                    obs_preview = step['observation'][:100] + "..." if len(step['observation']) > 100 else step['observation']
                    print(f"👁️  Observation: {obs_preview}")
                else:
                    print("👁️  Observation: [无]")
                
                if step.get('final_answer'):
                    answer_preview = step['final_answer'][:100] + "..." if len(step['final_answer']) > 100 else step['final_answer']
                    print(f"🎯 Final Answer: {answer_preview}")
            
            # 显示最终答案
            final_content = result.get('content', [{}])[0].get('text', '')
            print(f"\n📝 最终回答:")
            print(final_content)
            
            # 验证多轮执行
            action_count = sum(1 for step in thinking_process if step.get('action'))
            print(f"\n📊 统计信息:")
            print(f"- 总轮次: {len(thinking_process)}")
            print(f"- 工具调用次数: {action_count}")
            print(f"- 是否执行了真实的多轮: {'✅ 是' if action_count > 1 else '❌ 否'}")
            
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")

def test_health():
    """检查服务健康状态"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"🏥 服务状态: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ 服务正常运行，uptime: {health_data.get('uptime', 0):.1f}秒")
            return True
    except Exception as e:
        print(f"❌ 服务不可用: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始测试修复后的多轮ReAct功能...")
    
    # 1. 检查服务状态
    if not test_health():
        print("⚠️ 请先确保FastAPI服务正在运行")
        exit(1)
    
    # 2. 测试修复后的功能
    test_fixed_multiround()
    
    print("\n🎉 测试完成！")
    print("\n💡 期望结果:")
    print("- 应该看到多轮真实的工具调用")
    print("- 每轮都有真实的Observation")
    print("- 没有LLM自己生成的假Observation")
    print("- 服务端应该显示检测和修复假Observation的日志") 