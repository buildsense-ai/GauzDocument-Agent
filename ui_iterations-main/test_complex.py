#!/usr/bin/env python3
import requests
import json

def test_complex_request():
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
    
    print("🚀 发送复杂测试请求...")
    print(f"URL: {url}")
    print(f"Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
    print("="*50)
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        print(f"状态码: {response.status_code}")
        print(f"响应:")
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    test_complex_request() 