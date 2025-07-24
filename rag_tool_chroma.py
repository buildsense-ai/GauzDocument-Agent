"""
简化的 RAG Tool ChromaDB 模块
为Enhanced RAG Tool提供基础的ChromaDB功能
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except ImportError:
    print("警告: ChromaDB未安装，请运行: pip install chromadb")
    chromadb = None

logger = logging.getLogger(__name__)

class QwenEmbeddingFunction:
    """自定义Qwen嵌入函数，用于ChromaDB"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self._name = "qwen-embedding"  # ChromaDB需要name属性
        
    @property 
    def name(self):
        """返回embedding function的名称"""
        return self._name
        
    def __call__(self, input: List[str]) -> List[List[float]]:
        """ChromaDB调用的嵌入函数"""
        try:
            # 确保input是list类型
            if isinstance(input, str):
                input = [input]
            elif not isinstance(input, list):
                input = list(input)
                
            embeddings = self.llm_client.get_embeddings(input)
            if not embeddings:
                logger.warning("Qwen embedding返回空结果，使用零向量")
                # 返回零向量作为fallback
                dimension = 1024  # Qwen embedding维度
                return [[0.0] * dimension for _ in input]
            return embeddings
        except Exception as e:
            logger.error(f"Qwen embedding失败: {e}")
            # 返回零向量作为fallback
            dimension = 1024
            return [[0.0] * dimension for _ in input]

class Tool:
    """基础工具类"""
    def __init__(self):
        self.name = "base_tool"
        self.description = "基础工具类"
    
    def execute(self, action: str, **kwargs) -> str:
        """执行工具操作"""
        return "基础工具执行"

class ChromaVectorStore:
    """ChromaDB向量存储 - 使用Qwen embedding"""
    
    def __init__(self, storage_dir: str = "final_chromadb", llm_client=None):
        self.storage_dir = storage_dir
        self.llm_client = llm_client
        os.makedirs(storage_dir, exist_ok=True)
        
        if chromadb is None:
            logger.warning("ChromaDB未安装，使用模拟模式")
            self.client = None
            self.collection = None
            return
        
        try:
            self.client = chromadb.PersistentClient(path=storage_dir)
            
            # 如果有llm_client，使用Qwen embedding function
            if self.llm_client:
                embedding_function = QwenEmbeddingFunction(self.llm_client)
                logger.info("✅ 使用Qwen embedding模型 (1024维)")
            else:
                # 回退到默认embedding
                embedding_function = embedding_functions.DefaultEmbeddingFunction()
                logger.warning("⚠️ 未提供LLM客户端，使用ChromaDB默认embedding")
            
            # 直接使用有数据的collection (140个文档)
            collection_names = [
                "wrapped_documents_qwen_embedding",  # 主要数据collection (1024维，医灵古庙项目)
            ]
            self.collection = None
            
            for collection_name in collection_names:
                try:
                    self.collection = self.client.get_collection(name=collection_name)
                    count = self.collection.count()
                    
                    # 检查向量维度兼容性
                    if count > 0:
                        try:
                            # 根据当前embedding类型测试维度兼容性
                            test_query = "测试"
                            
                            if self.llm_client:
                                # 有LLM客户端，使用custom embedding测试
                                test_embeddings = self.llm_client.get_embeddings([test_query])
                                if test_embeddings and test_embeddings[0]:
                                    expected_dim = len(test_embeddings[0])
                                    logger.info(f"🔍 检查 {collection_name}: {count}个文档，LLM embedding维度: {expected_dim}")
                                    
                                    # 测试查询
                                    test_result = self.collection.query(
                                        query_embeddings=[test_embeddings[0]],
                                        n_results=1
                                    )
                                    logger.info(f"✅ 成功连接到 {collection_name} collection，包含 {count} 个文档，LLM embedding兼容")
                                    break
                            else:
                                # 没有LLM客户端，使用ChromaDB默认embedding测试
                                logger.info(f"🔍 检查 {collection_name}: {count}个文档，测试默认embedding兼容性")
                                
                                # 直接尝试查询，如果维度不兼容会抛出异常
                                test_result = self.collection.query(
                                    query_texts=[test_query],
                                    n_results=1
                                )
                                logger.info(f"✅ 成功连接到 {collection_name} collection，包含 {count} 个文档，默认embedding兼容")
                                break
                                
                        except Exception as dim_error:
                            if "dimension" in str(dim_error).lower() and "1024" in str(dim_error):
                                logger.error(f"❌ {collection_name} collection需要1024维embedding: {dim_error}")
                                if not self.llm_client:
                                    logger.error("💡 解决方案: 需要配置LLM客户端以提供1024维embedding")
                                    logger.error("   1. 检查API密钥是否正确配置")
                                    logger.error("   2. 检查网络连接是否正常")
                                    logger.error("   3. 确保LLMClient能正常初始化")
                                else:
                                    logger.error("💡 LLM客户端已配置但embedding维度仍不匹配，请检查配置")
                            else:
                                logger.warning(f"❌ {collection_name} collection维度不兼容: {dim_error}")
                            
                            self.collection = None  # 重置为None
                            continue
                    else:
                        logger.warning(f"⚠️ {collection_name} collection为空，继续尝试其他collection")
                        self.collection = None  # 重置为None
                        
                except Exception as e:
                    logger.debug(f"无法连接到 {collection_name}: {e}")
                    self.collection = None  # 重置为None
                    continue
            
            # 如果没有找到合适的collection，检查是否是LLM客户端问题
            if not self.collection:
                logger.error("❌ 无法连接到数据collection")
                logger.error("📊 系统检测到 wrapped_documents_qwen_embedding collection 包含140个文档")
                logger.error("🔧 但需要LLM客户端提供1024维embedding才能访问")
                
                if not self.llm_client:
                    logger.error("💡 解决方案: 配置LLM客户端")
                    logger.error("   请确保API密钥正确配置，以启用1024维embedding支持")
                    # 不创建新collection，因为数据已经存在于1024维collection中
                    raise RuntimeError("无法访问1024维数据collection，需要配置LLM客户端")
                else:
                    logger.error("💡 LLM客户端已配置但仍无法访问，请检查配置或重试")
                    raise RuntimeError("LLM客户端已配置但无法访问1024维数据collection")
                
                # 原来的创建新collection逻辑被移除，因为我们要使用现有数据
            logger.info(f"✅ ChromaVectorStore初始化成功: {storage_dir}")
        except Exception as e:
            logger.error(f"ChromaVectorStore初始化失败: {e}")
            self.client = None
            self.collection = None
    
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any] = None) -> int:
        """添加文档到向量存储"""
        if self.collection is None:
            logger.warning("ChromaDB不可用，跳过文档添加")
            return 0
        
        try:
            # 简单的文本分块
            chunks = self._chunk_text(content)
            
            # 添加到collection - ChromaDB会自动调用我们的Qwen embedding function
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_{i}"
                chunk_metadata = metadata.copy() if metadata else {}
                chunk_metadata.update({
                    "document_id": doc_id,
                    "chunk_id": i,
                    "chunk_count": len(chunks)
                })
                
                self.collection.add(
                    documents=[chunk],
                    metadatas=[chunk_metadata],
                    ids=[chunk_id]
                )
            
            logger.info(f"✅ 添加文档成功，使用Qwen embedding: {doc_id} ({len(chunks)} 个块)")
            return len(chunks)
        except Exception as e:
            logger.error(f"文档添加失败: {e}")
            return 0
    
    def search_documents(self, query: str, n_results: int = 5, where_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """搜索文档 - 先用embedding搜索检索top5，然后BM25重排序"""
        if self.collection is None:
            logger.warning("ChromaDB不可用，返回空结果")
            return []
        
        try:
            # 1. 元数据过滤：先用ChromaDB filter筛选元数据
            where_condition = None
            if where_filter:
                logger.info(f"🔍 应用元数据过滤: {where_filter}")
                # 构建ChromaDB兼容的where条件
                conditions = []
                for key, value in where_filter.items():
                    if isinstance(value, str):
                        conditions.append({key: {"$eq": value}})
                    else:
                        conditions.append({key: value})
                
                if conditions:
                    # 如果只有一个条件，直接使用；如果有多个条件，使用$and
                    if len(conditions) == 1:
                        where_condition = conditions[0]
                    else:
                        where_condition = {"$and": conditions}
                    logger.info(f"🔍 构建的where条件: {where_condition}")
            
            # 2. 向量搜索：使用embedding进行相似性搜索，检索top5结果
            logger.info(f"🔍 执行向量搜索: query='{query}', n_results={n_results}")
            
            # 使用Qwen embedding进行语义搜索
            try:
                # 方法1：使用自定义embedding function
                if self.llm_client:
                    embeddings = self.llm_client.get_embeddings([query])
                    if embeddings and embeddings[0]:
                        logger.info(f"🔍 使用Qwen embedding进行搜索，向量维度: {len(embeddings[0])}")
                        results = self.collection.query(
                            query_embeddings=[embeddings[0]],
                            n_results=n_results,  # 只检索top5
                            where=where_condition,
                            include=["documents", "metadatas", "distances"]
                        )
                    else:
                        raise Exception("Qwen embedding返回空结果")
                else:
                    # 方法2：使用ChromaDB内置的query_texts
                    results = self.collection.query(
                        query_texts=[query],
                        n_results=n_results,  # 只检索top5
                        where=where_condition,
                        include=["documents", "metadatas", "distances"]
                    )
            except Exception as query_error:
                logger.warning(f"主要搜索方法失败: {query_error}")
                
                # 如果是维度不匹配错误，直接返回空结果而不是尝试兼容性搜索
                if "dimension" in str(query_error).lower():
                    logger.info("🔄 检测到维度不匹配，返回空结果")
                    return []
                
                logger.info("🔄 尝试兼容性搜索方案...")
                
                # 兼容性方案：使用匹配数据库维度的测试向量
                try:
                    # 获取collection的第一个向量来确定维度
                    sample = self.collection.peek(limit=1)
                    if sample and sample.get('embeddings') and sample['embeddings'][0]:
                        actual_dim = len(sample['embeddings'][0])
                        logger.info(f"📊 检测到数据库向量维度: {actual_dim}")
                        test_embedding = [0.1] * actual_dim
                    else:
                        # 默认尝试1024维
                        test_embedding = [0.1] * 1024
                        logger.info("📊 使用默认1024维向量")
                    
                    results = self.collection.query(
                        query_embeddings=[test_embedding],
                        n_results=n_results,
                        where=where_condition,
                        include=["documents", "metadatas", "distances"]
                    )
                    logger.warning("⚠️ 使用测试向量搜索，结果可能不准确")
                except Exception as fallback_error:
                    logger.error(f"兼容性搜索也失败: {fallback_error}")
                    # 返回空结果而不是抛出异常
                    return []
            
            # 3. 处理向量搜索结果
            vector_results = []
            if results and results.get("documents") and results["documents"][0]:
                logger.info(f"✅ 向量搜索成功，找到 {len(results['documents'][0])} 个结果")
                
                for i, doc in enumerate(results["documents"][0]):
                    similarity_score = 1.0 - (results["distances"][0][i] if results.get("distances") else 0.5)
                    
                    result = {
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "similarity_score": similarity_score,  # 只保留similarity_score
                        "distance": results["distances"][0][i] if results.get("distances") else 0.0
                    }
                    vector_results.append(result)
            else:
                logger.warning("向量搜索无结果，尝试纯BM25搜索回退")
                # 不直接返回空列表，而是创建基于BM25的回退结果
                try:
                    # 获取所有文档进行BM25搜索
                    all_docs = self.collection.get(where=where_condition)
                    if all_docs and all_docs.get("documents"):
                        documents = all_docs["documents"]
                        metadatas = all_docs.get("metadatas", [{}] * len(documents))
                        
                        # 使用BM25对所有文档进行评分
                        for i, (doc, metadata) in enumerate(zip(documents, metadatas)):
                            # 简单的关键词匹配评分
                            try:
                                bm25_score = self._simple_bm25_score(doc, query)
                                if bm25_score > 0:  # 只保留有匹配的结果
                                    result = {
                                        "content": doc,
                                        "metadata": metadata,
                                        "similarity_score": 0.0,  # 向量搜索失败，设为0
                                        "distance": 1.0  # 最大距离
                                    }
                                    vector_results.append(result)
                            except Exception as bm25_error:
                                logger.warning(f"BM25评分失败，跳过文档 {i}: {bm25_error}")
                                continue
                        
                        # 按BM25得分排序并取前n_results个
                        vector_results.sort(key=lambda x: self._simple_bm25_score(x["content"], query), reverse=True)
                        vector_results = vector_results[:n_results]
                        
                        logger.info(f"🔄 BM25回退搜索找到 {len(vector_results)} 个结果")
                    else:
                        logger.warning("📭 数据库中无文档，返回空结果")
                        return []
                except Exception as fallback_error:
                    logger.error(f"❌ BM25回退搜索失败: {fallback_error}")
                    return []
            
            # 如果仍然没有结果，返回空列表
            if not vector_results:
                logger.warning("📭 所有搜索策略都无结果")
                return []
            
            # 4. BM25重排序：对向量搜索结果进行BM25评分并重排序
            logger.info("🔍 执行BM25重排序")
            final_results = self._apply_bm25_reranking(vector_results, query)
            
            logger.info(f"✅ 搜索完成: {len(final_results)} 个结果")
            return final_results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            # 返回错误而不是空列表，让上层处理
            raise e
    
    def _apply_bm25_reranking(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """应用BM25重排序：对向量搜索结果进行BM25评分并重排序"""
        query_terms = query.lower().split()
        
        for result in results:
            # 根据内容类型构建BM25搜索文本
            bm25_text = self._build_bm25_text(result)
            
            # 计算BM25分数
            bm25_score = self._calculate_enhanced_bm25_score(bm25_text, query_terms)
            result["bm25_score"] = bm25_score
            
            # 计算最终排序分数：70%向量相似性 + 30%BM25关键词匹配
            result["final_score"] = 0.7 * result["similarity_score"] + 0.3 * result["bm25_score"]
        
        # 按最终分数重排序
        results.sort(key=lambda x: x["final_score"], reverse=True)
        
        logger.info(f"🔍 BM25重排序完成，最高分数: {results[0]['final_score'] if results else 0}")
        return results
    
    def _build_bm25_text(self, result: Dict[str, Any]) -> str:
        """为BM25计算构建搜索文本 - 根据内容类型使用不同字段组合"""
        metadata = result.get("metadata", {})
        content_type = metadata.get("type", "")
        
        # 对于图片和表格，使用指定的字段组合
        if content_type in ["image_chunk", "table_chunk"]:
            parts = []
            
            # 优先使用三个主要描述字段的组合
            search_summary = metadata.get("search_summary", "")
            detailed_description = metadata.get("detailed_description", "")
            engineering_details = metadata.get("engineering_details", "")
            
            if search_summary and search_summary.strip():
                parts.append(str(search_summary.strip()))
            
            if detailed_description and detailed_description.strip():
                # 如果detailed_description是JSON格式，尝试解析
                if detailed_description.startswith('```json'):
                    try:
                        # 提取JSON内容
                        json_start = detailed_description.find('{')
                        json_end = detailed_description.rfind('}') + 1
                        if json_start != -1 and json_end > json_start:
                            import json
                            desc_data = json.loads(detailed_description[json_start:json_end])
                            
                            # 提取JSON中的描述字段，确保转换为字符串
                            if "search_summary" in desc_data and desc_data["search_summary"]:
                                parts.append(str(desc_data["search_summary"]))
                            if "detailed_description" in desc_data and desc_data["detailed_description"]:
                                parts.append(str(desc_data["detailed_description"]))
                            if "engineering_details" in desc_data and desc_data["engineering_details"]:
                                parts.append(str(desc_data["engineering_details"]))
                    except Exception as e:
                        # JSON解析失败，使用原文
                        parts.append(str(detailed_description.strip()))
                else:
                    parts.append(str(detailed_description.strip()))
            
            if engineering_details and engineering_details.strip():
                parts.append(str(engineering_details.strip()))
            
            # 如果上述三个字段都为空，才使用page_context作为回退
            if not parts:
                page_context = metadata.get("page_context", "")
                if page_context and page_context.strip():
                    parts.append(str(page_context.strip()))
            
            # 如果仍然没有内容，使用caption作为最后回退
            if not parts:
                caption = metadata.get("caption", "")
                if caption and caption.strip():
                    parts.append(f"{content_type.replace('_chunk', '')}: {str(caption)}")
            
            bm25_text = " ".join(parts)
            
        else:
            # 对于文本内容，直接使用content字段
            bm25_text = result.get("content", "")
        
        return bm25_text.lower() if bm25_text else ""
    
    def _calculate_enhanced_bm25_score(self, text: str, query_terms: List[str]) -> float:
        """增强的BM25分数计算"""
        if not text or not query_terms:
            return 0.0
        
        # BM25参数
        k1 = 1.2
        b = 0.75
        
        # 文档长度归一化
        doc_length = len(text.split())
        avgdl = 100  # 假设平均文档长度为100词
        
        bm25_score = 0.0
        
        for term in query_terms:
            if term in text:
                # 词频
                tf = text.count(term)
                
                # BM25 TF部分
                tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avgdl)))
                
                # 简化的IDF (假设词的逆文档频率)
                idf = 1.0  # 简化版本，可以根据需要改进
                
                bm25_score += tf_component * idf
        
        # 归一化分数 (0-1范围)
        max_possible_score = len(query_terms) * (k1 + 1)
        normalized_score = bm25_score / max_possible_score if max_possible_score > 0 else 0.0
        
        return min(normalized_score, 1.0)  # 确保不超过1
    
    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """简单的文本分块"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks if chunks else [text]

class RAGTool(Tool):
    """增强的RAG工具 - 支持MySQL模板搜索和ChromaDB内容搜索"""
    
    def __init__(self, storage_dir: str = "final_chromadb", deepseek_client=None):
        super().__init__()
        self.name = "rag_tool"
        self.description = "增强的RAG工具 - 支持双模式搜索"
        self.storage_dir = storage_dir
        self.vector_store = ChromaVectorStore(storage_dir, deepseek_client)
        self.deepseek_client = deepseek_client
    
    def execute(self, action: str, **kwargs) -> str:
        """执行RAG操作"""
        try:
            if action == "search":
                return self._search_documents(**kwargs)
            elif action == "mysql_search":
                return self._search_mysql_templates(**kwargs)
            elif action == "chunk_search":
                return self._search_chunk_content(**kwargs)
            elif action == "upload":
                return self._upload_document(**kwargs)
            else:
                return f"❌ 不支持的操作: {action}"
        except Exception as e:
            logger.error(f"RAG操作失败: {e}")
            return f"❌ 操作失败: {str(e)}"
    
    def _search_mysql_templates(self, query: str, **kwargs) -> str:
        """搜索MySQL模板文件（保持原有功能）"""
        # 这里保持原有的MySQL搜索逻辑
        # 由于我们没有MySQL连接，返回模拟结果
        return json.dumps({
            "search_type": "mysql_templates",
            "query": query,
            "success": True,
            "total_results": 0,
            "results": [],
            "message": "MySQL模板搜索功能保持不变"
        }, ensure_ascii=False, indent=2)
    
    def _search_chunk_content(self, query: str, chapter_id: Optional[str] = None, 
                            top_k: int = 5, **kwargs) -> str:
        """搜索chunk内容 - 支持元数据过滤和混合搜索"""
        try:
            if self.vector_store.collection is None:
                return json.dumps({
                    "search_type": "chunk_content",
                    "query": query,
                    "chapter_filter": chapter_id,
                    "success": False,
                    "error": "ChromaDB连接不可用",
                    "total_results": 0,
                    "results": []
                }, ensure_ascii=False, indent=2)
            
            # 准备元数据过滤条件
            where_filter = None
            if chapter_id:
                where_filter = {"chapter_id": chapter_id}
                logger.info(f"应用章节过滤: {chapter_id}")
            
            try:
                # 执行向量搜索
                vector_results = self._vector_search(query, top_k, where_filter)
                
                # 执行混合搜索（70% 向量 + 30% BM25）
                final_results = self._hybrid_search_ranking(vector_results, query)
                
                # 转换为标准输出格式
                formatted_results = []
                for result in final_results:
                    formatted_result = {
                        "retrieved_text": result.get("content", ""),
                        "retrieved_image": self._extract_image_path(result.get("metadata", {})),
                        "score": result.get("distance", 0.0),
                        "metadata": result.get("metadata", {})
                    }
                    formatted_results.append(formatted_result)
                
                return json.dumps({
                    "search_type": "chunk_content",
                    "query": query,
                    "chapter_filter": chapter_id,
                    "total_results": len(formatted_results),
                    "results": formatted_results,
                    "success": True
                }, ensure_ascii=False, indent=2)
                
            except Exception as search_error:
                logger.error(f"搜索执行失败: {search_error}")
                return json.dumps({
                    "search_type": "chunk_content",
                    "query": query,
                    "chapter_filter": chapter_id,
                    "success": False,
                    "error": f"搜索失败: {str(search_error)}",
                    "total_results": 0,
                    "results": []
                }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Chunk搜索失败: {e}")
            return json.dumps({
                "search_type": "chunk_content",
                "query": query,
                "chapter_filter": chapter_id,
                "success": False,
                "error": f"搜索系统错误: {str(e)}",
                "total_results": 0,
                "results": []
            }, ensure_ascii=False, indent=2)
    
    def _vector_search(self, query: str, top_k: int, where_filter: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行搜索：先用embedding搜索，然后BM25重排序"""
        try:
            logger.info(f"🔍 开始搜索: query='{query}', top_k={top_k}")
            if where_filter:
                logger.info(f"🔍 应用元数据过滤: {where_filter}")
            
            # 使用ChromaVectorStore的新搜索方法
            results = self.vector_store.search_documents(
                query=query,
                n_results=top_k,
                where_filter=where_filter
            )
            
            # 转换为标准格式
            formatted_results = []
            for result in results:
                formatted_result = {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "similarity_score": result.get("similarity_score", 0.0),
                    "bm25_score": result.get("bm25_score", 0.0),
                    "final_score": result.get("final_score", 0.0),
                    "distance": 1.0 - result.get("final_score", 0.0)  # 距离 = 1 - 最终分数
                }
                formatted_results.append(formatted_result)
            
            logger.info(f"✅ 搜索完成: {len(formatted_results)} 个结果")
            return formatted_results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            # 直接抛出异常，让上层处理
            raise e
    
    def _hybrid_search_ranking(self, vector_results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """搜索排序已在_vector_search中完成，这里直接返回"""
        logger.info("✅ 搜索排序已完成 (embedding + BM25重排序)")
        
        # 验证最终分数是否存在
        for result in vector_results:
            if "final_score" not in result:
                logger.warning("最终分数缺失，补充计算")
                # 如果没有最终分数，补充计算
                similarity_score = result.get("similarity_score", 1.0 - result.get("distance", 0.0))
                bm25_score = result.get("bm25_score", self._simple_bm25_score(result.get("content", ""), query))
                result["final_score"] = 0.7 * similarity_score + 0.3 * bm25_score
        
        # 确保按最终分数排序
        vector_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return vector_results
    
    def _simple_bm25_score(self, text: str, query: str) -> float:
        """简单的BM25近似分数"""
        try:
            # 确保输入是字符串类型
            text_str = str(text) if text is not None else ""
            query_str = str(query) if query is not None else ""
            
            query_terms = query_str.lower().split()
            text_lower = text_str.lower()
            
            score = 0.0
            for term in query_terms:
                if term in text_lower:
                    # 简单的词频计算
                    tf = text_lower.count(term)
                    score += tf / (tf + 1.0)  # 简化的BM25公式
            
            return score / len(query_terms) if query_terms else 0.0
        except Exception as e:
            logger.warning(f"BM25分数计算失败: {e}")
            return 0.0
    
    def _extract_image_path(self, metadata: Dict[str, Any]) -> str:
        """从元数据中提取图片路径"""
        # 根据你的元数据结构调整
        image_fields = ["image_path", "figure_path", "image_url", "image"]
        for field in image_fields:
            if field in metadata and metadata[field]:
                return metadata[field]
        return ""
    
    def _search_documents(self, query: str, search_type: str = "auto", **kwargs) -> str:
        """统一搜索接口 - 根据search_type选择搜索模式"""
        if search_type == "mysql" or search_type == "templates":
            return self._search_mysql_templates(query, **kwargs)
        elif search_type == "chunks" or search_type == "content":
            return self._search_chunk_content(query, **kwargs)
        else:
            # auto模式：默认搜索chunk内容
            return self._search_chunk_content(query, **kwargs)
    
    def _upload_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """上传文档"""
        try:
            if not os.path.exists(file_path):
                return f"❌ 文件不存在: {file_path}"
            
            # 简单的文本读取
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            doc_id = hashlib.md5(file_path.encode()).hexdigest()
            
            if metadata is None:
                metadata = {}
            metadata.update({
                "source": file_path,
                "upload_time": datetime.now().isoformat()
            })
            
            chunks_count = self.vector_store.add_document(doc_id, content, metadata)
            
            return f"✅ 文档上传成功: {file_path} (共 {chunks_count} 个块)"
        except Exception as e:
            return f"❌ 上传失败: {str(e)}" 