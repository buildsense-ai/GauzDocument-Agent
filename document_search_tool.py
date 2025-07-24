"""
文档搜索工具 - 内容搜索
独立工具，输入query_text等参数，输出JSON格式的retrieved text/image/table
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入组件
from rag_tool_chroma import RAGTool
from llm_client import LLMClient, LLMConfig

logger = logging.getLogger(__name__)

class DocumentSearchTool:
    """
    文档搜索工具 - 统一内容搜索
    
    功能：
    1. 支持文本、图片、表格的统一搜索
    2. 混合搜索引擎（向量相似性 + BM25关键词匹配）
    3. 返回标准化JSON格式结果
    """
    
    def __init__(self, storage_dir: str = None):
        """初始化文档搜索工具"""
        # 使用final_chromadb作为默认存储目录
        self.storage_dir = storage_dir or os.getenv("RAG_STORAGE_DIR", "final_chromadb")
        
        # 初始化LLM客户端 - 必须使用Qwen v4的1024维embedding
        try:
            self.llm_client = LLMClient(LLMConfig())
            logger.info("✅ LLM客户端初始化成功，使用Qwen 1024维embedding")
        except Exception as e:
            logger.error(f"❌ LLM客户端初始化失败: {e}")
            logger.error("❌ 无法使用1024维embedding，数据collection需要1024维")
            logger.error("💡 请检查API密钥配置或网络连接")
            # 为了与现有的1024维数据兼容，这里先设置为None，让RAGTool处理
            self.llm_client = None
        
        # 初始化RAG工具（传入LLM客户端）
        self.rag_tool = RAGTool(self.storage_dir, self.llm_client)
        
        logger.info("✅ 文档搜索工具初始化完成")
        logger.info(f"📁 存储目录: {self.storage_dir}")
        logger.info("🔍 功能: 统一内容搜索 (文本+图片+表格)")
    
    def search_documents(self, query_text: str, project_name: str = "all", 
                        top_k: int = 5, content_type: str = "all") -> str:
        """
        搜索文档内容 - 主要接口
        
        Args:
            query_text: 查询文本
            project_name: 项目名称 (默认"all")
            top_k: 返回结果数量 (默认5)
            content_type: 内容类型 (默认"all")
            
        Returns:
            标准化的JSON响应字符串
        """
        try:
            logger.info(f"🔍 开始文档搜索:")
            logger.info(f"   📝 查询: {query_text}")
            logger.info(f"   📊 项目: {project_name}")
            logger.info(f"   📊 数量: {top_k}")
            logger.info(f"   🎯 类型: {content_type}")
            
            if not query_text:
                error_msg = "查询文本不能为空"
                logger.error(f"❌ {error_msg}")
                return json.dumps({
                    "status": "error",
                    "message": error_msg,
                    "retrieved_text": [],
                    "retrieved_image": [],
                    "retrieved_table": []
                }, ensure_ascii=False, indent=2)
            
            # 根据content_type决定搜索策略
            if content_type == "text":
                # 只搜索文本
                text_results = self._unified_content_search(project_name, query_text, top_k, "text_chunk")
                image_results = []
                table_results = []
                
            elif content_type == "image":
                # 只搜索图片
                text_results = []
                image_results = self._unified_content_search(project_name, query_text, top_k, "image_chunk")
                table_results = []
                
            elif content_type == "table":
                # 只搜索表格
                text_results = []
                image_results = []
                table_results = self._unified_content_search(project_name, query_text, top_k, "table_chunk")
                
            else:
                # content_type="all": 搜索所有类型，每种类型返回top3
                logger.info("🔄 执行统一混合搜索 - 所有内容类型")
                
                # 搜索所有类型的内容
                text_candidates = self._unified_content_search(project_name, query_text, top_k, "text_chunk")
                image_candidates = self._unified_content_search(project_name, query_text, top_k, "image_chunk")
                table_candidates = self._unified_content_search(project_name, query_text, top_k, "table_chunk")
                
                logger.info(f"📊 统一搜索候选结果: text({len(text_candidates)}) + image({len(image_candidates)}) + table({len(table_candidates)})")
                
                # 文本使用两阶段策略的全部结果(固定5个)，图片表格取top3
                text_results = text_candidates  # 两阶段搜索已经固定返回5个
                image_results = image_candidates[:3]
                table_results = table_candidates[:3]
            
            # 格式化结果
            formatted_text = [self._format_text_chunk(result) for result in text_results]
            formatted_image = [self._format_image_chunk(result) for result in image_results]
            formatted_table = [self._format_table_chunk(result) for result in table_results]
            
            # 生成响应
            response = {
                "status": "success",
                "message": f"search_document执行完成",
                "query_text": query_text,
                "project_name": project_name,
                "content_type": content_type,
                "total_results": len(text_results) + len(image_results) + len(table_results),
                "retrieved_text": formatted_text,
                "retrieved_image": formatted_image,
                "retrieved_table": formatted_table,
                "search_metadata": {
                    "search_timestamp": datetime.now().isoformat(),
                    "search_strategy": "统一混合搜索 (embedding + BM25)",
                    "top_k": top_k,
                    "project_filter": project_name != "all"
                }
            }
            
            logger.info(f"📊 搜索完成:")
            logger.info(f"   📝 文本片段: {len(formatted_text)}个")
            logger.info(f"   🖼️ 图片片段: {len(formatted_image)}个")
            logger.info(f"   📊 表格片段: {len(formatted_table)}个")
            
            return json.dumps(response, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ 文档搜索失败: {e}")
            return json.dumps({
                "status": "error",
                "message": f"搜索失败: {str(e)}",
                "retrieved_text": [],
                "retrieved_image": [],
                "retrieved_table": []
            }, ensure_ascii=False, indent=2)
    
    def search_documents_by_params(self, params: Dict[str, Any]) -> str:
        """
        通过参数字典搜索文档（兼容原接口格式）
        
        Args:
            params: 参数字典，包含query_text等字段
            
        Returns:
            标准化的JSON响应字符串
        """
        try:
            # 提取参数 - 支持多种参数格式
            query_text = params.get("query_text", "") or params.get("query", "")
            
            # 如果没有query_text，尝试从queries参数中提取
            if not query_text and "queries" in params:
                queries = params["queries"]
                if isinstance(queries, list) and queries:
                    query_text = " ".join(queries)
                elif isinstance(queries, str):
                    query_text = queries
                logger.info(f"✅ 从queries参数转换得到query_text: '{query_text}'")
            
            project_name = params.get("project_name", "all")
            top_k = params.get("top_k", 5)
            content_type = params.get("content_type", "all")
            
            logger.info(f"🔍 参数提取结果:")
            logger.info(f"   📝 原始参数: {params}")
            logger.info(f"   🔍 提取的query_text: '{query_text}'")
            logger.info(f"   📊 提取的project_name: '{project_name}'")
            logger.info(f"   📊 提取的top_k: {top_k}")
            logger.info(f"   🎯 提取的content_type: '{content_type}'")
            
            return self.search_documents(query_text, project_name, top_k, content_type)
            
        except Exception as e:
            logger.error(f"❌ 参数搜索失败: {e}")
            return json.dumps({
                "status": "error",
                "message": f"参数搜索失败: {str(e)}",
                "retrieved_text": [],
                "retrieved_image": [],
                "retrieved_table": []
            }, ensure_ascii=False, indent=2)
    
    def _unified_content_search(self, project_name: str, query: str, top_k: int = 5, chunk_type: str = "text_chunk") -> List[Dict]:
        """
        统一的搜索函数 - 支持文本、图片、表格的统一搜索逻辑
        
        对于text_chunk使用两阶段搜索策略：
        1. 搜索chapter_summary找到最相关章节
        2. 在该章节内embedding搜索text_chunks (top10)
        3. BM25重排序后固定返回top5
        
        Args:
            project_name: 项目名称
            query: 自然语言查询
            top_k: 返回结果数量 (text_chunk固定返回5个)
            chunk_type: 内容类型 ("text_chunk", "image_chunk", "table_chunk")
            
        Returns:
            搜索结果列表
        """
        logger.info(f"🔍 执行统一搜索: project={project_name}, query='{query}', type={chunk_type}, top_k={top_k}")
        
        try:
            # 对text_chunk使用特殊的两阶段搜索策略
            if chunk_type == "text_chunk":
                return self._two_stage_text_search(project_name, query, top_k)
            
            # 对image_chunk和table_chunk使用原有的搜索逻辑
            # 1. 构建元数据过滤条件
            metadata_filter = {
                "type": chunk_type
            }
            
            # 如果有项目名称，添加到过滤条件
            if project_name and project_name != "all":
                metadata_filter["project_name"] = project_name
            
            # 2. 使用RAG工具进行向量搜索
            search_results = self.rag_tool.vector_store.search_documents(
                query=query,
                n_results=top_k,
                where_filter=metadata_filter
            )
            
            # 3. 转换为标准格式
            results = []
            for result in search_results:
                # 基础字段
                formatted_result = {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "similarity_score": result.get("similarity_score", 0.0),
                    "bm25_score": result.get("bm25_score", 0.0),
                    "final_score": result.get("final_score", 0.0)
                }
                
                # 根据chunk_type添加特定字段
                if chunk_type == "image_chunk":
                    formatted_result["content_type"] = "image"
                    metadata = result.get("metadata", {})
                    formatted_result["image_path"] = metadata.get("image_path", "")
                    formatted_result["caption"] = metadata.get("caption", "")
                    formatted_result["page_context"] = metadata.get("page_context", "")
                    formatted_result["detailed_description"] = metadata.get("detailed_description", "")
                elif chunk_type == "table_chunk":
                    formatted_result["content_type"] = "table"
                    metadata = result.get("metadata", {})
                    formatted_result["table_path"] = metadata.get("table_path", "")
                    formatted_result["caption"] = metadata.get("caption", "")
                    formatted_result["page_context"] = metadata.get("page_context", "")
                    formatted_result["detailed_description"] = metadata.get("detailed_description", "")
                
                results.append(formatted_result)
            
            logger.info(f"✅ {chunk_type}搜索完成，找到{len(results)}个结果")
            return results
            
        except Exception as e:
            logger.error(f"❌ {chunk_type}搜索失败: {e}")
            return []
    
    def _two_stage_text_search(self, project_name: str, query: str, top_k: int = 5) -> List[Dict]:
        """
        两阶段文本搜索策略 (改进版)
        
        第一阶段：搜索chapter_summary，找到最相关的top2章节
        第二阶段：智能处理章节和text_chunks的组合：
        - 两个章节都有chunks：搜索所有chunks
        - 部分章节有chunks：无chunks章节的raw_content作为虚拟chunk参与搜索
        - 两个章节都无chunks：直接返回章节raw_content
        第三阶段：embedding搜索top10，BM25重排序返回top5
        
        Args:
            project_name: 项目名称
            query: 自然语言查询
            top_k: 最终返回结果数量 (注意：两阶段搜索固定返回5个结果)
            
        Returns:
            搜索结果列表 (固定返回top5)
        """
        logger.info(f"🔍 执行两阶段文本搜索: query='{query}', 策略=top2章节->混合搜索->top5")
        
        try:
            # 第一阶段：搜索chapter_summary找到最相关的top2章节
            logger.info("📖 第一阶段：搜索章节摘要")
            
            chapter_filter = {"type": "chapter_summary"}
            if project_name and project_name != "all":
                chapter_filter["project_name"] = project_name
            
            # 搜索最相关的top2章节
            chapter_results = self.rag_tool.vector_store.search_documents(
                query=query,
                n_results=2,  # 取最相关的两个章节
                where_filter=chapter_filter
            )
            
            if not chapter_results:
                logger.warning("⚠️ 没有找到相关章节，回退到全局搜索")
                return self._fallback_text_search(project_name, query, top_k)
            
            # 提取章节信息
            chapters_info = []
            for chapter_result in chapter_results:
                chapter_metadata = chapter_result.get("metadata", {})
                chapter_id = chapter_metadata.get("chapter_id")
                chapter_title = chapter_metadata.get("chapter_title", "未知章节")
                
                if chapter_id:
                    chapters_info.append({
                        "result": chapter_result,
                        "chapter_id": chapter_id,
                        "chapter_title": chapter_title,
                        "metadata": chapter_metadata
                    })
            
            if not chapters_info:
                logger.warning("⚠️ 所有章节ID为空，回退到全局搜索")
                return self._fallback_text_search(project_name, query, top_k)
            
            chapter_ids = [info["chapter_id"] for info in chapters_info]
            chapter_names = [f"{info['chapter_id']} - {info['chapter_title']}" for info in chapters_info]
            logger.info(f"✅ 找到相关章节: {', '.join(chapter_names)}")
            
            # 第二阶段：智能处理章节和text_chunks的组合
            logger.info(f"📝 第二阶段：分析章节内容组合策略")
            
            # 检查每个章节是否有text_chunks
            chapters_with_chunks = []
            chapters_without_chunks = []
            
            for chapter_info in chapters_info:
                chapter_id = chapter_info["chapter_id"]
                
                # 构建章节内搜索的过滤条件
                text_filter = {
                    "$and": [
                        {"type": "text_chunk"},
                        {"chapter_id": chapter_id}
                    ]
                }
                if project_name and project_name != "all":
                    text_filter["$and"].append({"project_name": project_name})
                
                # 检查该章节是否有text_chunks（只查询1个用于判断）
                chapter_chunks = self.rag_tool.vector_store.search_documents(
                    query=query,
                    n_results=1,  # 只用于检查是否存在
                    where_filter=text_filter
                )
                
                if chapter_chunks:
                    chapters_with_chunks.append(chapter_info)
                    logger.info(f"  📚 章节 {chapter_id} 有text_chunks")
                else:
                    chapters_without_chunks.append(chapter_info)
                    logger.info(f"  📄 章节 {chapter_id} 无text_chunks，将使用raw_content")
            
            # 根据不同情况处理
            if not chapters_with_chunks and not chapters_without_chunks:
                logger.warning("⚠️ 所有章节都无法处理，回退到全局搜索")
                return self._fallback_text_search(project_name, query, top_k)
            elif not chapters_with_chunks:
                # 情况3：所有章节都没有chunks，直接返回章节raw_content
                logger.info("📖 情况3：所有章节都无chunks，返回章节摘要内容")
                return self._use_multiple_chapter_contents(chapters_without_chunks, query)
            else:
                # 情况1和2：至少有一个章节有chunks，进行混合搜索
                logger.info(f"🔄 情况1/2：混合搜索 - {len(chapters_with_chunks)}个章节有chunks，{len(chapters_without_chunks)}个章节无chunks")
                return self._perform_hybrid_chapter_search(chapters_with_chunks, chapters_without_chunks, query, project_name)
            
            # 移除了原来的第三阶段逻辑，现在由具体的处理方法负责
            
        except Exception as e:
            logger.error(f"❌ 两阶段文本搜索失败: {e}")
            # 回退到原有的全局搜索
            return self._fallback_text_search(project_name, query, top_k)
    
    def _fallback_text_search(self, project_name: str, query: str, top_k: int) -> List[Dict]:
        """回退的全局文本搜索"""
        logger.info("🔄 执行回退的全局文本搜索")
        
        try:
            metadata_filter = {"type": "text_chunk"}
            if project_name and project_name != "all":
                metadata_filter["project_name"] = project_name
            
            search_results = self.rag_tool.vector_store.search_documents(
                query=query,
                n_results=top_k,
                where_filter=metadata_filter
            )
            
            results = []
            for result in search_results:
                formatted_result = {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "similarity_score": result.get("similarity_score", 0.0),
                    "bm25_score": result.get("bm25_score", 0.0),
                    "final_score": result.get("final_score", 0.0),
                    "content_type": "text"
                }
                results.append(formatted_result)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 回退搜索失败: {e}")
            return []
    
    def _apply_text_bm25_reranking(self, results: List[Dict], query: str, top_k: int) -> List[Dict]:
        """
        针对文本块的BM25重排序
        
        使用text chunk的content字段作为BM25计算源数据
        最终分数 = 70% similarity_score + 30% bm25_score
        
        Args:
            results: 搜索结果列表
            query: 查询字符串
            top_k: 最终返回数量
            
        Returns:
            重排序后的结果列表
        """
        logger.info(f"🔄 应用文本BM25重排序，输入 {len(results)} 个结果，输出 top{top_k}")
        
        if not results:
            return []
        
        query_terms = query.lower().split()
        
        # BM25参数
        k1 = 1.2
        b = 0.75
        
        for result in results:
            # 使用text chunk的content字段进行BM25计算
            text_content = result.get("content", "").lower()
            
            if not text_content:
                result["bm25_score"] = 0.0
                continue
            
            # 文档长度归一化
            doc_length = len(text_content.split())
            avgdl = 100  # 假设平均文档长度为100词
            
            bm25_score = 0.0
            
            for term in query_terms:
                if term in text_content:
                    # 词频
                    tf = text_content.count(term)
                    
                    # BM25 TF部分
                    tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avgdl)))
                    
                    # 简化的IDF
                    idf = 1.0
                    
                    bm25_score += tf_component * idf
            
            # 归一化分数 (0-1范围)
            max_possible_score = len(query_terms) * (k1 + 1) if query_terms else 1
            normalized_bm25 = bm25_score / max_possible_score
            result["bm25_score"] = min(normalized_bm25, 1.0)
            
            # 计算最终分数：70%向量相似性 + 30%BM25关键词匹配
            similarity_score = result.get("similarity_score", 0.0)
            final_score = 0.7 * similarity_score + 0.3 * result["bm25_score"]
            result["final_score"] = final_score
        
        # 按最终分数重排序并取top_k
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        top_results = results[:top_k]
        
        logger.info(f"✅ BM25重排序完成，返回top{len(top_results)}，最高分数: {top_results[0].get('final_score', 0):.3f}")
        return top_results
    
    def _use_multiple_chapter_contents(self, chapters_info: List[Dict], query: str) -> List[Dict]:
        """
        处理所有章节都没有text_chunks的情况，返回章节raw_content
        
        Args:
            chapters_info: 章节信息列表
            query: 搜索查询
            
        Returns:
            格式化的搜索结果列表
        """
        logger.info(f"📖 使用多个章节摘要内容: {len(chapters_info)}个章节")
        
        results = []
        for chapter_info in chapters_info:
            chapter_result = chapter_info["result"]
            chapter_id = chapter_info["chapter_id"]
            chapter_title = chapter_info["chapter_title"]
            
                    # 获取章节内容 - 优先使用raw_content
        chapter_metadata = chapter_result.get("metadata", {})
        raw_content = chapter_metadata.get("raw_content", "")
        
        # 如果metadata中没有raw_content，尝试从结果的content中获取
        if not raw_content:
            raw_content = chapter_result.get("content", "")
        
        # 最后才使用ai_summary作为备选
        if not raw_content:
            raw_content = chapter_metadata.get("ai_summary", "")
            
            if raw_content:
                # 计算BM25分数
                bm25_score = self._calculate_content_bm25_score(raw_content, query)
                
                # 构造结果
                formatted_result = {
                    "content": raw_content,
                    "metadata": {
                        "content_id": f"{chapter_id}_summary",
                        "chapter_id": chapter_id,
                        "chapter_title": chapter_title,
                        "content_type": "chapter_content",
                        "source": "chapter_summary"
                    },
                    "similarity_score": chapter_result.get("similarity_score", 0.0),
                    "bm25_score": bm25_score,
                    "final_score": 0.7 * chapter_result.get("similarity_score", 0.0) + 0.3 * bm25_score,
                    "content_type": "text",
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title,
                    "source": "chapter_summary"
                }
                results.append(formatted_result)
        
        # 按最终分数排序，取前5个
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        final_results = results[:5]
        
        logger.info(f"✅ 多章节内容结果生成完成，返回 {len(final_results)} 个结果")
        return final_results
    
    def _perform_hybrid_chapter_search(self, chapters_with_chunks: List[Dict], chapters_without_chunks: List[Dict], query: str, project_name: str) -> List[Dict]:
        """
        执行混合章节搜索：将有chunks的章节的text_chunks和无chunks章节的raw_content合并搜索
        
        Args:
            chapters_with_chunks: 有text_chunks的章节信息
            chapters_without_chunks: 没有text_chunks的章节信息
            query: 搜索查询
            project_name: 项目名称
            
        Returns:
            搜索结果列表
        """
        logger.info(f"🔄 执行混合章节搜索")
        
        try:
            all_candidates = []
            
            # 1. 收集有chunks的章节的所有text_chunks
            if chapters_with_chunks:
                logger.info(f"📚 收集有chunks章节的text_chunks: {[info['chapter_id'] for info in chapters_with_chunks]}")
                
                # 构建多章节的过滤条件
                chapter_ids = [info["chapter_id"] for info in chapters_with_chunks]
                
                # 根据章节数量构建不同的过滤条件
                if len(chapter_ids) == 1:
                    # 只有一个章节，使用简单条件
                    text_filter = {
                        "$and": [
                            {"type": "text_chunk"},
                            {"chapter_id": chapter_ids[0]}
                        ]
                    }
                else:
                    # 多个章节，使用$or条件
                    text_filter = {
                        "$and": [
                            {"type": "text_chunk"},
                            {"$or": [{"chapter_id": chapter_id} for chapter_id in chapter_ids]}
                        ]
                    }
                
                if project_name and project_name != "all":
                    text_filter["$and"].append({"project_name": project_name})
                
                # 搜索所有相关的text_chunks
                text_chunks = self.rag_tool.vector_store.search_documents(
                    query=query,
                    n_results=50,  # 收集更多候选，稍后会筛选
                    where_filter=text_filter
                )
                
                logger.info(f"  📝 找到 {len(text_chunks)} 个text_chunks")
                all_candidates.extend(text_chunks)
            
            # 2. 将无chunks章节的raw_content转换为虚拟text_chunk
            if chapters_without_chunks:
                logger.info(f"📄 转换无chunks章节为虚拟text_chunk: {[info['chapter_id'] for info in chapters_without_chunks]}")
                
                for chapter_info in chapters_without_chunks:
                    virtual_chunk = self._create_virtual_text_chunk(chapter_info, query)
                    if virtual_chunk:
                        all_candidates.append(virtual_chunk)
                        logger.info(f"  ✅ 创建虚拟chunk: {chapter_info['chapter_id']}")
            
            # 3. 如果没有候选结果，回退
            if not all_candidates:
                logger.warning("⚠️ 混合搜索无候选结果，回退到全局搜索")
                return self._fallback_text_search(project_name, query, 5)
            
            logger.info(f"📊 混合搜索总候选: {len(all_candidates)}个")
            
            # 4. 对所有候选进行重新排序，选择top10
            for candidate in all_candidates:
                # 如果没有similarity_score，给一个默认值
                if "similarity_score" not in candidate:
                    candidate["similarity_score"] = 0.5
            
            # 按相似度排序，取top10
            all_candidates.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            top_candidates = all_candidates[:10]
            
            # 5. 对top10进行BM25重排序，返回top5
            logger.info("🔄 第三阶段：BM25重排序")
            final_results = self._apply_text_bm25_reranking(top_candidates, query, 5)
            
            # 6. 转换为标准格式
            formatted_results = []
            for result in final_results:
                # 从metadata或直接从result中获取章节信息
                chapter_id = result.get("metadata", {}).get("chapter_id") or result.get("chapter_id", "unknown")
                chapter_title = result.get("metadata", {}).get("chapter_title") or result.get("chapter_title", "未知章节")
                
                formatted_result = {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "similarity_score": result.get("similarity_score", 0.0),
                    "bm25_score": result.get("bm25_score", 0.0),
                    "final_score": result.get("final_score", 0.0),
                    "content_type": "text",
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title
                }
                formatted_results.append(formatted_result)
            
            logger.info(f"✅ 混合章节搜索完成，返回 {len(formatted_results)} 个结果")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ 混合章节搜索失败: {e}")
            return self._fallback_text_search(project_name, query, 5)
    
    def _create_virtual_text_chunk(self, chapter_info: Dict, query: str) -> Dict:
        """
        将章节raw_content转换为虚拟text_chunk
        
        Args:
            chapter_info: 章节信息
            query: 搜索查询
            
        Returns:
            虚拟text_chunk字典
        """
        chapter_result = chapter_info["result"]
        chapter_id = chapter_info["chapter_id"]
        chapter_title = chapter_info["chapter_title"]
        
        # 获取章节内容 - 优先使用raw_content
        chapter_metadata = chapter_result.get("metadata", {})
        raw_content = chapter_metadata.get("raw_content", "")
        
        # 如果metadata中没有raw_content，尝试从结果的content中获取
        if not raw_content:
            raw_content = chapter_result.get("content", "")
        
        # 最后才使用ai_summary作为备选
        if not raw_content:
            raw_content = chapter_metadata.get("ai_summary", "")
        
        if not raw_content:
            return None
        
        # 计算BM25分数
        bm25_score = self._calculate_content_bm25_score(raw_content, query)
        
        # 创建虚拟text_chunk
        virtual_chunk = {
            "content": raw_content,
            "metadata": {
                "content_id": f"{chapter_id}_virtual_chunk",
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "content_type": "virtual_text_chunk",
                "source": "chapter_summary",
                "document_id": chapter_metadata.get("document_id", ""),
                "chunk_type": "virtual",
                "paragraph_index": 0,
                "position_in_chapter": 0,
                "word_count": len(raw_content)
            },
            "similarity_score": chapter_result.get("similarity_score", 0.5),  # 使用章节的相似度
            "bm25_score": bm25_score,
            "final_score": 0.7 * chapter_result.get("similarity_score", 0.5) + 0.3 * bm25_score,
            "chapter_id": chapter_id,
            "chapter_title": chapter_title
        }
        
        return virtual_chunk
    
    def _use_chapter_content_as_result(self, chapter_result: Dict, chapter_id: str, chapter_title: str, query: str) -> List[Dict]:
        """
        当章节内没有text_chunks时，使用章节摘要的raw_content作为搜索结果
        
        Args:
            chapter_result: 章节搜索结果
            chapter_id: 章节ID
            chapter_title: 章节标题
            query: 搜索查询
            
        Returns:
            格式化的搜索结果列表
        """
        logger.info(f"📖 使用章节摘要内容作为搜索结果: {chapter_id}")
        
        try:
            # 获取章节内容 - 优先使用raw_content
            chapter_metadata = chapter_result.get("metadata", {})
            raw_content = chapter_metadata.get("raw_content", "")
            
            # 如果metadata中没有raw_content，尝试从结果的content中获取
            if not raw_content:
                raw_content = chapter_result.get("content", "")
            
            # 最后才使用ai_summary作为备选
            if not raw_content:
                raw_content = chapter_metadata.get("ai_summary", "")
            
            if not raw_content:
                logger.warning(f"⚠️ 章节 {chapter_id} 没有可用内容，回退到全局搜索")
                return self._fallback_text_search("", query, 3)  # 使用空project_name避免重复过滤
            
            # 计算BM25分数
            bm25_score = self._calculate_content_bm25_score(raw_content, query)
            
            # 构造结果
            chapter_content_result = {
                "content": raw_content,
                "metadata": {
                    "content_id": f"{chapter_id}_summary",
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title,
                    "content_type": "chapter_content",
                    "source": "chapter_summary"
                },
                "similarity_score": chapter_result.get("similarity_score", 0.0),
                "bm25_score": bm25_score,
                "final_score": 0.7 * chapter_result.get("similarity_score", 0.0) + 0.3 * bm25_score
            }
            
            # 转换为标准格式
            formatted_result = {
                "content": raw_content,
                "metadata": chapter_content_result["metadata"],
                "similarity_score": chapter_content_result["similarity_score"],
                "bm25_score": chapter_content_result["bm25_score"],
                "final_score": chapter_content_result["final_score"],
                "content_type": "text",
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "source": "chapter_summary"  # 明确标记来源
            }
            
            logger.info(f"✅ 章节内容结果生成完成: 相似度={formatted_result['similarity_score']:.3f}, "
                       f"BM25={formatted_result['bm25_score']:.3f}, 最终={formatted_result['final_score']:.3f}")
            
            return [formatted_result]
            
        except Exception as e:
            logger.error(f"❌ 章节内容结果生成失败: {e}")
            # 最终回退到全局搜索
            return self._fallback_text_search("", query, 3)
    
    def _calculate_content_bm25_score(self, content: str, query: str) -> float:
        """
        计算内容的BM25分数
        
        Args:
            content: 文本内容
            query: 查询字符串
            
        Returns:
            BM25分数
        """
        if not content or not query:
            return 0.0
        
        query_terms = query.lower().split()
        text_content = content.lower()
        
        # BM25参数
        k1 = 1.2
        b = 0.75
        
        # 文档长度归一化
        doc_length = len(text_content.split())
        avgdl = 200  # 章节内容通常比较长，调整平均长度
        
        bm25_score = 0.0
        
        for term in query_terms:
            if term in text_content:
                # 词频
                tf = text_content.count(term)
                
                # BM25 TF部分
                tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avgdl)))
                
                # 简化的IDF
                idf = 1.0
                
                bm25_score += tf_component * idf
        
        # 归一化分数 (0-1范围)
        max_possible_score = len(query_terms) * (k1 + 1) if query_terms else 1
        normalized_bm25 = bm25_score / max_possible_score
        return min(normalized_bm25, 1.0)
    
    def _format_text_chunk(self, result: Dict) -> Dict[str, Any]:
        """格式化文本块数据"""
        metadata = result.get("metadata", {})
        
        # 构造content_id：如果metadata中没有，则根据chapter_id和chunk_index构造
        content_id = metadata.get("content_id", "")
        if not content_id:
            chapter_id = metadata.get("chapter_id", "") or result.get("chapter_id", "")
            chunk_index = metadata.get("chunk_index", 0)
            if chapter_id and chunk_index is not None:
                content_id = f"{chapter_id}_{chunk_index}"
        
        return {
            "content_id": content_id,
            "content": result.get("content", ""),
            "chunk_type": metadata.get("chunk_type", "paragraph"),
            "document_id": metadata.get("document_id", ""),
            "chapter_id": metadata.get("chapter_id", "") or result.get("chapter_id", ""),
            "chapter_title": metadata.get("chapter_title", "") or result.get("chapter_title", ""),
            "paragraph_index": metadata.get("paragraph_index", 0),
            "position_in_chapter": metadata.get("position_in_chapter", 0),
            "word_count": metadata.get("word_count", len(result.get("content", ""))),
            "similarity_score": result.get("similarity_score", 0.0),
            "bm25_score": result.get("bm25_score", 0.0),
            "final_score": result.get("final_score", 0.0),
            "source": metadata.get("source", result.get("source", "text_chunk"))  # 添加source字段
        }
    
    def _format_image_chunk(self, result: Dict) -> Dict[str, Any]:
        """格式化图片块数据"""
        metadata = result.get("metadata", {})
        image_path = result.get("image_path", "") or metadata.get("image_path", "")
        
        # 构造content_id：如果metadata中没有，则根据document_id和image编号构造
        content_id = metadata.get("content_id", "")
        if not content_id:
            document_id = metadata.get("document_id", "")
            # 尝试从现有content_id模式中提取，或使用其他字段构造
            image_index = metadata.get("image_index", "") or metadata.get("chunk_index", "")
            if document_id and image_index:
                content_id = f"{document_id}_image_{image_index}"
        
        return {
            "content_id": content_id,
            "image_url": self._generate_minio_url(image_path),
            "image_path": image_path,
            "caption": result.get("caption", "") or metadata.get("caption", ""),
            "ai_description": metadata.get("ai_description", ""),
            "detailed_description": result.get("detailed_description", "") or metadata.get("detailed_description", ""),
            "page_number": metadata.get("page_number", 0),
            "page_context": result.get("page_context", "") or metadata.get("page_context", ""),
            "document_id": metadata.get("document_id", ""),
            "chapter_id": metadata.get("chapter_id", ""),
            "chapter_title": metadata.get("chapter_title", ""),
            "width": metadata.get("width", 0),
            "height": metadata.get("height", 0),
            "aspect_ratio": metadata.get("aspect_ratio", 0.0),
            "similarity_score": result.get("similarity_score", 0.0),
            "bm25_score": result.get("bm25_score", 0.0),
            "final_score": result.get("final_score", 0.0)
        }
    
    def _format_table_chunk(self, result: Dict) -> Dict[str, Any]:
        """格式化表格块数据"""
        metadata = result.get("metadata", {})
        table_path = result.get("table_path", "") or metadata.get("table_path", "")
        
        # 构造content_id：如果metadata中没有，则根据document_id和table编号构造
        content_id = metadata.get("content_id", "")
        if not content_id:
            document_id = metadata.get("document_id", "")
            # 尝试从现有content_id模式中提取，或使用其他字段构造
            table_index = metadata.get("table_index", "") or metadata.get("chunk_index", "")
            if document_id and table_index:
                content_id = f"{document_id}_table_{table_index}"
        
        return {
            "content_id": content_id,
            "table_url": self._generate_minio_url(table_path),
            "table_path": table_path,
            "caption": result.get("caption", "") or metadata.get("caption", ""),
            "ai_description": metadata.get("ai_description", ""),
            "detailed_description": result.get("detailed_description", "") or metadata.get("detailed_description", ""),
            "page_number": metadata.get("page_number", 0),
            "page_context": result.get("page_context", "") or metadata.get("page_context", ""),
            "document_id": metadata.get("document_id", ""),
            "chapter_id": metadata.get("chapter_id", ""),
            "chapter_title": metadata.get("chapter_title", ""),
            "similarity_score": result.get("similarity_score", 0.0),
            "bm25_score": result.get("bm25_score", 0.0),
            "final_score": result.get("final_score", 0.0)
        }
    
    def _generate_minio_url(self, file_path: str) -> str:
        """
        生成MinIO访问URL
        
        Args:
            file_path: 文件路径
            
        Returns:
            完整的MinIO访问URL
        """
        if not file_path:
            return ""
            
        # 从环境变量获取MinIO配置
        minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        minio_bucket = os.getenv("MINIO_BUCKET", "document-storage")
        
        # 确保路径格式正确
        clean_path = file_path.lstrip("/")
        
        return f"{minio_endpoint}/{minio_bucket}/{clean_path}" 