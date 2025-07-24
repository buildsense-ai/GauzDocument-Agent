"""
Mineru API 配置示例

基于用户提供的API密钥信息创建客户端配置
"""

from .clients.mineru_client import MineruClient

# 用户提供的Mineru API密钥
MINERU_ACCESS_KEY = "kvzbwqj2zw9ovz2q20rl"
MINERU_SECRET_KEY = "yqyb14wpqezo79jaxebo7q5per2nrkdm3pegoj5n"

# API基础URL（需要根据实际情况调整）
MINERU_BASE_URL = "https://api.mineru.net"  # 待确认实际地址


def create_mineru_client() -> MineruClient:
    """
    创建配置好的Mineru客户端
    
    Returns:
        配置好的MineruClient实例
    """
    return MineruClient(
        access_key=MINERU_ACCESS_KEY,
        secret_key=MINERU_SECRET_KEY,
        base_url=MINERU_BASE_URL
    )


async def example_usage():
    """
    Mineru客户端使用示例
    """
    async with create_mineru_client() as client:
        # 检查配额状态
        quota_status = client.get_quota_status()
        print(f"配额状态: {quota_status}")
        
        # 上传PDF文件
        project_id = "proj_20250125_demo"
        task_id = await client.upload_pdf(
            file_path="testfiles/医灵古庙设计方案.pdf",
            project_id=project_id
        )
        
        # 等待处理完成
        final_status = await client.wait_for_completion(task_id)
        
        if final_status['state'] == 'completed':
            # 获取结果
            result = await client.get_result(task_id)
            
            # 解析为V3 Schema
            schema = client.parse_mineru_output(result, project_id)
            
            print(f"处理完成: {schema.get_all_chunks_count()}")
        else:
            print(f"处理失败: {final_status}")


# 配置验证
def validate_mineru_config():
    """验证Mineru配置是否正确"""
    if not MINERU_ACCESS_KEY or not MINERU_SECRET_KEY:
        raise ValueError("Mineru API密钥未配置")
    
    if len(MINERU_ACCESS_KEY) < 10 or len(MINERU_SECRET_KEY) < 10:
        raise ValueError("Mineru API密钥格式可能不正确")
    
    print("✅ Mineru配置验证通过")


if __name__ == "__main__":
    import asyncio
    
    validate_mineru_config()
    print("📋 Mineru配置:")
    print(f"  Access Key: {MINERU_ACCESS_KEY[:8]}***")
    print(f"  Secret Key: {MINERU_SECRET_KEY[:8]}***")
    print(f"  Base URL: {MINERU_BASE_URL}")
    
    # 可以取消注释来运行示例
    # asyncio.run(example_usage()) 