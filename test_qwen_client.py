#!/usr/bin/env python3
"""
测试 Qwen 客户端
"""

import os
import sys
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.qwen_client import QwenClient
    print("✅ Qwen客户端导入成功")
except ImportError as e:
    print(f"❌ 无法导入Qwen客户端: {e}")
    sys.exit(1)

def test_single_request():
    """测试单个请求"""
    print("\n🧪 测试单个请求...")
    
    try:
        client = QwenClient(
            model="qwen-turbo-latest",
            max_tokens=500,
            timeout=30,
            max_retries=3
        )
        
        test_prompt = "请用一句话总结：人工智能是什么？"
        print(f"📝 发送提示: {test_prompt}")
        
        start_time = time.time()
        response = client.generate_response(test_prompt)
        end_time = time.time()
        
        print(f"🤖 响应: {response}")
        print(f"⏱️ 耗时: {end_time - start_time:.2f} 秒")
        
        # 显示统计信息
        client.print_stats()
        
        return True
        
    except Exception as e:
        print(f"❌ 单个请求测试失败: {e}")
        return False

def test_batch_requests():
    """测试批量请求"""
    print("\n🧪 测试批量请求...")
    
    try:
        client = QwenClient(
            model="qwen-turbo-latest",
            max_tokens=200,
            timeout=30,
            max_retries=3,
            enable_batch_mode=True
        )
        
        test_prompts = [
            "请用一句话解释：什么是机器学习？",
            "请用一句话解释：什么是深度学习？",
            "请用一句话解释：什么是自然语言处理？",
            "请用一句话解释：什么是计算机视觉？",
            "请用一句话解释：什么是强化学习？"
        ]
        
        print(f"📝 发送 {len(test_prompts)} 个批量请求...")
        
        start_time = time.time()
        responses = client.batch_generate_responses(test_prompts, max_workers=5)
        end_time = time.time()
        
        print(f"🤖 批量响应:")
        for i, response in enumerate(responses):
            print(f"  {i+1}. {response}")
        
        print(f"⏱️ 总耗时: {end_time - start_time:.2f} 秒")
        print(f"⚡ 平均每个请求: {(end_time - start_time) / len(test_prompts):.2f} 秒")
        
        # 显示统计信息
        client.print_stats()
        
        return True
        
    except Exception as e:
        print(f"❌ 批量请求测试失败: {e}")
        return False

def test_error_handling():
    """测试错误处理"""
    print("\n🧪 测试错误处理...")
    
    try:
        # 使用错误的API Key测试
        client = QwenClient(
            api_key="invalid-key",
            model="qwen-turbo-latest",
            max_tokens=100,
            timeout=10,
            max_retries=2
        )
        
        test_prompt = "这是一个错误处理测试"
        print(f"📝 发送错误测试提示: {test_prompt}")
        
        try:
            response = client.generate_response(test_prompt)
            print(f"🤖 意外成功响应: {response}")
        except Exception as e:
            print(f"✅ 预期错误处理成功: {e}")
            client.print_stats()
            return True
            
        return False
        
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试 Qwen 客户端...")
    
    # 检查环境变量
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        print("❌ 未设置 QWEN_API_KEY 环境变量")
        print("请设置: export QWEN_API_KEY='sk-73a2d302ee7042eb930a944722441d66'")
        return
    
    print(f"✅ API Key 已设置: {api_key[:10]}...")
    
    # 运行测试
    tests = [
        ("单个请求测试", test_single_request),
        ("批量请求测试", test_batch_requests),
        ("错误处理测试", test_error_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"📋 {test_name}")
        print(f"{'='*50}")
        
        result = test_func()
        results.append((test_name, result))
        
        if result:
            print(f"✅ {test_name} 通过")
        else:
            print(f"❌ {test_name} 失败")
    
    # 总结
    print(f"\n{'='*50}")
    print("📊 测试总结")
    print(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n🎯 总体结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！Qwen 客户端工作正常。")
    else:
        print("⚠️ 部分测试失败，请检查配置。")

if __name__ == "__main__":
    main() 