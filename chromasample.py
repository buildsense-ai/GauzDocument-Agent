# RAG开发者拿到的向量数据库状态
chroma_collection = {
    "name": "gauz_document_embeddings",
    "total_vectors": 5000+,  # 假设一个44页文档产生5000+个向量
    "vector_dimension": 1536,  # text-embedding-3-large的维度
    "documents": [
        "AlphaEvolve是一个用于科学和算法发现的编程智能体...",  # 文档摘要
        "任务规范部分详细描述了AlphaEvolve的任务定义...",        # 章节摘要
        "AlphaEvolve通过生成代码来解决科学问题...",            # 文本块
        "系统架构图显示了AlphaEvolve的主要组件和数据流",        # 图片描述
        "实验结果表格显示了不同算法的性能对比",                # 表格描述
        "AlphaEvolve如何处理复杂的科学计算任务？",            # 衍生问题
        # ... 更多内容
    ],
    "metadatas": [
        {
            "content_id": "doc_summary_alphaevolve_2024",
            "document_id": "alphaevolve_2024", 
            "content_type": "document_summary",
            "content_level": "document",
            # ... 其他元数据
        },
        {
            "content_id": "chapter_summary_alphaevolve_2024_2.1",
            "document_id": "alphaevolve_2024",
            "chapter_id": "2.1",
            "content_type": "chapter_summary", 
            "content_level": "chapter",
            # ... 其他元数据
        },
        {
            "content_id": "image_chunk_alphaevolve_2024_img_001",
            "document_id": "alphaevolve_2024",
            "chapter_id": "2.1", 
            "content_type": "image_chunk",
            "content_level": "chunk",
            "file_path": "parser_output/alphaevolve_2024/picture-1.png",
            # ... 其他元数据
        }
        # ... 更多元数据
    ]
}