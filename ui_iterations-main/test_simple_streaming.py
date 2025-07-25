#!/usr/bin/env python3
import requests
import json
import threading
import time

def simple_streaming_test():
    """简单的流式输出测试"""
    print("🌊 开始测试修复后的thought输出...")
    
    # 发送请求到/react_solve（现在已启用ThoughtLogger）
    url = "http://localhost:8000/react_solve"
    headers = {
        "Content-Type": "application/json",
        "x-project-id": "test123",
        "x-project-name": "test_project"
    }
    data = {
        "problem": "请帮我查询一下医灵古庙的建筑特色",
        "project_context": {
            "project_id": "test123",
            "project_name": "test_project"
        }
    }
    
    print("🚀 发送测试请求...")
    print("📋 请求数据:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("="*50)
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        print(f"📊 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功！")
            print("\n📝 响应内容:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            # 显示思考过程
            thinking_process = result.get('thinking_process', [])
            if thinking_process:
                print(f"\n🧠 思考过程 ({len(thinking_process)} 轮):")
                for i, step in enumerate(thinking_process, 1):
                    print(f"\n--- 第 {i} 轮 ---")
                    if step.get('thought'):
                        print(f"💭 Thought: {step['thought']}")
                    if step.get('action'):
                        print(f"🔧 Action: {step['action']}")
                    if step.get('action_input'):
                        print(f"📋 Action Input: {step['action_input']}")
                    if step.get('observation'):
                        print(f"👁️  Observation: {step['observation'][:100]}...")
                    if step.get('final_answer'):
                        print(f"🎯 Final Answer: {step['final_answer'][:100]}...")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")

def test_streaming_endpoint():
    """测试流式端点"""
    print("\n🌊 测试实时thought监听端点...")
    
    try:
        # 测试是否能连接到流式端点
        response = requests.get("http://localhost:8000/stream/live_thoughts", stream=True, timeout=5)
        print(f"📊 流式端点状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 流式端点可用！")
            # 读取前几行数据
            lines_read = 0
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith('data: '):
                    data_str = line[6:]  # 移除 'data: ' 前缀
                    try:
                        data = json.loads(data_str)
                        print(f"🔊 流式数据: {data}")
                        lines_read += 1
                        if lines_read >= 3:  # 只读前3行
                            break
                    except json.JSONDecodeError:
                        print(f"🔊 原始数据: {data_str}")
        else:
            print(f"❌ 流式端点不可用: {response.text}")
            
    except Exception as e:
        print(f"❌ 流式端点测试失败: {e}")

if __name__ == "__main__":
    print("🚀 开始测试修复后的功能...")
    
    # 1. 测试修复后的/react_solve端点
    simple_streaming_test()
    
    # 2. 测试新的流式端点
    test_streaming_endpoint()
    
    print("\n🎉 测试完成！")
    print("\n💡 说明:")
    print("1. 现在/react_solve端点已启用ThoughtLogger")
    print("2. 服务器端会显示完整的调试信息")
    print("3. 前端可以通过/stream/live_thoughts监听实时thought数据")
    print("4. 查看FastAPI服务器的控制台输出以看到详细的thought过程") 