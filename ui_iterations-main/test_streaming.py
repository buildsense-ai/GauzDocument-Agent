#!/usr/bin/env python3
import requests
import json
import threading
import time
import sseclient

def test_streaming_thoughts():
    """测试实时thought流式输出"""
    print("🌊 开始测试流式thought输出...")
    
    # 1. 启动实时thought监听
    def listen_thoughts():
        print("🎧 启动thought监听器...")
        try:
            response = requests.get("http://localhost:8000/stream/live_thoughts", stream=True, timeout=60)
            client = sseclient.SSEClient(response)
            
            for event in client.events():
                if event.data:
                    try:
                        data = json.loads(event.data)
                        print(f"🔊 收到thought数据: {data['type']} - {data.get('content', data.get('message', ''))[:50]}...")
                    except json.JSONDecodeError:
                        print(f"🔊 收到原始数据: {event.data}")
                        
        except Exception as e:
            print(f"❌ thought监听失败: {e}")
    
    # 在后台启动监听器
    listener_thread = threading.Thread(target=listen_thoughts, daemon=True)
    listener_thread.start()
    
    # 2. 等待一下让监听器启动
    time.sleep(2)
    
    # 3. 发送复杂请求到/react_solve
    print("🚀 发送复杂请求到/react_solve...")
    url = "http://localhost:8000/react_solve"
    headers = {
        "Content-Type": "application/json",
        "x-project-id": "test123",
        "x-project-name": "test_project"
    }
    data = {
        "problem": "请帮我查询一下医灵古庙的建筑特色和历史背景",
        "project_context": {
            "project_id": "test123",
            "project_name": "test_project"
        }
    }
    
    try:
        print("⏳ 等待Agent处理...")
        response = requests.post(url, headers=headers, json=data, timeout=120)
        print(f"📊 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功！")
            print(f"📝 最终答案: {result.get('content', [{}])[0].get('text', '')[:100]}...")
            print(f"🔄 总迭代次数: {result.get('total_iterations', 0)}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
    
    # 4. 等待一下确保所有thought数据都被捕获
    print("⏳ 等待thought数据传输完成...")
    time.sleep(5)
    
    print("🎉 测试完成！")

if __name__ == "__main__":
    # 检查sseclient是否安装
    try:
        import sseclient
    except ImportError:
        print("❌ 缺少sseclient库，请安装: pip install sseclient-py")
        exit(1)
    
    test_streaming_thoughts() 