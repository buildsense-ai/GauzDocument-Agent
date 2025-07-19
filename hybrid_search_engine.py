"""
混合搜索引擎 - 结合向量相似性、元数据过滤和BM25关键词匹配
"""
import os
import json
import logging
import math
from typing import Dict, List, Any, Optional, Union, Tuple
from collections import defaultdict, Counter
import jieba
import numpy as np
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """搜索结果数据类"""
    content: str
    metadata: Dict[str, Any]
    vector_score: float = 0.0
    bm25_score: float = 0.0
    metadata_score: float = 0.0
    final_score: float = 0.0
    ranking_factors: Dict[str, float] = None
    
    def __post_init__(self):
        if self.ranking_factors is None:
            self.ranking_factors = {}

class BM25Scorer:
    """BM25评分器"""
    
    def __init__(self, k1: float = None, b: float = None):
        self.k1 = k1 or float(os.getenv("BM25_K1", "1.2"))
        self.b = b or float(os.getenv("BM25_B", "0.75"))
        self.doc_freqs = {}
        self.idf = {}
        self.doc_len = {}
        self.avgdl = 0
        self.corpus = []
        
    def fit(self, corpus: List[str]):
        """训练BM25模型"""
        self.corpus = corpus
        doc_lengths = []
        term_freqs = []
        
        # 分词和统计
        for doc in corpus:
            tokens = list(jieba.cut(doc.lower()))
            doc_lengths.append(len(tokens))
            term_freq = Counter(tokens)
            term_freqs.append(term_freq)
            
        self.avgdl = sum(doc_lengths) / len(doc_lengths)
        
        # 计算文档频率
        for term_freq in term_freqs:
            for term in term_freq:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
        
        # 计算IDF
        n_docs = len(corpus)
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5))
        
        # 存储文档长度
        self.doc_len = {i: length for i, length in enumerate(doc_lengths)}
        
    def score(self, query: str, doc_id: int) -> float:
        """计算BM25得分"""
        if doc_id >= len(self.corpus):
            return 0.0
            
        doc = self.corpus[doc_id]
        doc_tokens = list(jieba.cut(doc.lower()))
        doc_term_freq = Counter(doc_tokens)
        
        query_tokens = list(jieba.cut(query.lower()))
        score = 0.0
        
        for term in query_tokens:
            if term in doc_term_freq:
                tf = doc_term_freq[term]
                idf = self.idf.get(term, 0)
                doc_length = self.doc_len.get(doc_id, 0)
                
                # BM25公式
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avgdl))
                score += idf * (numerator / denominator)
                
        return score
        
    def batch_score(self, query: str, doc_ids: List[int]) -> List[float]:
        """批量计算BM25得分"""
        return [self.score(query, doc_id) for doc_id in doc_ids]

class MetadataFilter:
    """元数据过滤器"""
    
    def __init__(self):
        self.filter_weights = {
            "exact_match": 1.0,
            "partial_match": 0.7,
            "type_match": 0.5,
            "project_match": 0.9,
            "time_match": 0.6
        }
    
    def apply_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """应用元数据过滤"""
        if not filters:
            return results
            
        filtered_results = []
        
        for result in results:
            metadata = result.get("metadata", {})
            score = self._calculate_metadata_score(metadata, filters)
            
            if score > 0:  # 只保留有匹配度的结果
                result["metadata_score"] = score
                filtered_results.append(result)
                
        return filtered_results
    
    def _calculate_metadata_score(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> float:
        """计算元数据匹配得分"""
        total_score = 0.0
        total_weight = 0.0
        
        for filter_key, filter_value in filters.items():
            if filter_key in metadata:
                metadata_value = metadata[filter_key]
                weight = self.filter_weights.get(filter_key, 0.5)
                
                if isinstance(filter_value, str) and isinstance(metadata_value, str):
                    # 字符串匹配
                    if filter_value.lower() == metadata_value.lower():
                        total_score += weight * self.filter_weights["exact_match"]
                    elif filter_value.lower() in metadata_value.lower() or metadata_value.lower() in filter_value.lower():
                        total_score += weight * self.filter_weights["partial_match"]
                        
                elif isinstance(filter_value, list) and isinstance(metadata_value, str):
                    # 列表匹配
                    if metadata_value in filter_value:
                        total_score += weight * self.filter_weights["exact_match"]
                    else:
                        for item in filter_value:
                            if item.lower() in metadata_value.lower():
                                total_score += weight * self.filter_weights["partial_match"]
                                break
                                
                elif filter_value == metadata_value:
                    # 精确匹配
                    total_score += weight * self.filter_weights["exact_match"]
                    
                total_weight += weight
                
        return total_score / total_weight if total_weight > 0 else 0.0

class HybridSearchEngine:
    """混合搜索引擎"""
    
    def __init__(self, vector_store, llm_client):
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.bm25_scorer = BM25Scorer()
        self.metadata_filter = MetadataFilter()
        
        # 设置搜索权重配置：70% 向量相似性 + 30% BM25关键词匹配
        self.search_weights = {
            "vector_similarity": float(os.getenv("VECTOR_SIMILARITY_WEIGHT", "0.7")),  # 70%
            "bm25_score": float(os.getenv("BM25_SCORE_WEIGHT", "0.3")),              # 30%
            "metadata_match": float(os.getenv("METADATA_MATCH_WEIGHT", "0.0"))       # 0% (不使用)
        }
        
        # 初始化BM25模型
        self._initialize_bm25()
        
    def _initialize_bm25(self):
        """初始化BM25模型"""
        try:
            # 检查vector_store和collection是否可用
            if not self.vector_store or not self.vector_store.collection:
                logger.warning("Vector store或collection不可用，使用默认文档初始化BM25")
                self.bm25_scorer.fit(["default document"])
                return
                
            # 获取所有文档内容
            all_docs = self.vector_store.collection.get()
            if all_docs and "documents" in all_docs and len(all_docs["documents"]) > 0:
                corpus = all_docs["documents"]
                # 过滤空文档
                corpus = [doc for doc in corpus if doc and doc.strip()]
                if len(corpus) > 0:
                    self.bm25_scorer.fit(corpus)
                    logger.info(f"BM25模型初始化完成，文档数量: {len(corpus)}")
                else:
                    logger.warning("没有有效文档，使用空BM25模型")
                    self.bm25_scorer.fit(["default document"])
            else:
                logger.warning("没有找到文档，使用空BM25模型")
                self.bm25_scorer.fit(["default document"])
        except Exception as e:
            logger.error(f"BM25模型初始化失败: {e}")
            # 使用默认文档初始化
            try:
                self.bm25_scorer.fit(["default document"])
                logger.info("使用默认文档初始化BM25模型")
            except Exception as e2:
                logger.error(f"默认BM25模型初始化也失败: {e2}")
    
    def search(self, query: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None, 
               search_strategy: str = "hybrid") -> List[SearchResult]:
        """
        执行混合搜索
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            filters: 元数据过滤器
            search_strategy: 搜索策略 ("vector", "bm25", "hybrid")
            
        Returns:
            搜索结果列表
        """
        try:
            logger.info(f"开始混合搜索: query='{query}', strategy={search_strategy}")
            
            if search_strategy == "vector":
                return self._vector_search(query, top_k, filters)
            elif search_strategy == "bm25":
                return self._bm25_search(query, top_k, filters)
            else:
                return self._hybrid_search(query, top_k, filters)
                
        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            return []
    
    def _vector_search(self, query: str, top_k: int, filters: Optional[Dict[str, Any]]) -> List[SearchResult]:
        """纯向量搜索"""
        try:
            # 使用现有的向量搜索功能
            results = self.vector_store.search_documents(
                query=query,
                n_results=top_k,
                where_filter=filters
            )
            
            search_results = []
            for result in results:
                search_result = SearchResult(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    vector_score=1.0 - result.get("distance", 0.0),  # 转换为相似性得分
                    bm25_score=0.0,
                    metadata_score=0.0,
                    final_score=1.0 - result.get("distance", 0.0)
                )
                search_results.append(search_result)
                
            return search_results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    def _bm25_search(self, query: str, top_k: int, filters: Optional[Dict[str, Any]]) -> List[SearchResult]:
        """纯BM25搜索"""
        try:
            # 获取所有文档
            all_docs = self.vector_store.collection.get()
            if not all_docs or "documents" not in all_docs:
                return []
                
            documents = all_docs["documents"]
            metadatas = all_docs.get("metadatas", [{}] * len(documents))
            
            # 计算BM25得分
            bm25_scores = self.bm25_scorer.batch_score(query, list(range(len(documents))))
            
            # 创建结果列表
            results = []
            for i, (doc, metadata, score) in enumerate(zip(documents, metadatas, bm25_scores)):
                result = {
                    "content": doc,
                    "metadata": metadata,
                    "bm25_score": score
                }
                results.append(result)
            
            # 应用元数据过滤
            if filters:
                results = self.metadata_filter.apply_filters(results, filters)
            
            # 按BM25得分排序
            results.sort(key=lambda x: x.get("bm25_score", 0), reverse=True)
            
            # 转换为SearchResult对象
            search_results = []
            for result in results[:top_k]:
                search_result = SearchResult(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    vector_score=0.0,
                    bm25_score=result.get("bm25_score", 0.0),
                    metadata_score=result.get("metadata_score", 0.0),
                    final_score=result.get("bm25_score", 0.0)
                )
                search_results.append(search_result)
                
            return search_results
            
        except Exception as e:
            logger.error(f"BM25搜索失败: {e}")
            return []
    
    def _hybrid_search(self, query: str, top_k: int, filters: Optional[Dict[str, Any]]) -> List[SearchResult]:
        """混合搜索"""
        try:
            # 1. 向量搜索
            vector_results = self.vector_store.search_documents(
                query=query,
                n_results=top_k * 2,  # 获取更多结果用于融合
                where_filter=filters
            )
            
            # 2. 如果向量搜索有结果，直接使用（因为已经包含BM25重排序）
            if vector_results:
                # 转换为SearchResult格式
                search_results = []
                for result in vector_results:
                    search_result = SearchResult(
                        content=result.get("content", ""),
                        metadata=result.get("metadata", {}),
                        vector_score=result.get("similarity_score", 0.0),
                        bm25_score=result.get("bm25_score", 0.0),
                        metadata_score=0.0,
                        final_score=result.get("final_score", 0.0)
                    )
                    search_results.append(search_result)
                
                # 排序并返回top_k结果
                search_results.sort(key=lambda x: x.final_score, reverse=True)
                return search_results[:top_k]
            
            # 3. 如果向量搜索无结果，回退到纯BM25搜索
            else:
                return self._bm25_search(query, top_k, filters)
                
        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            return []
    
    def search_with_expansion(self, query: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        使用查询扩展的混合搜索
        
        Args:
            query: 原始查询
            top_k: 返回结果数量
            filters: 元数据过滤器
            
        Returns:
            搜索结果列表
        """
        try:
            # 1. 分析查询意图
            intent = self.llm_client.analyze_query_intent(query)
            
            # 2. 生成扩展查询
            expanded_queries = self.llm_client.generate_search_queries(query, intent)
            
            # 3. 对每个查询进行搜索
            all_results = []
            query_weights = [1.0] + [0.7] * (len(expanded_queries) - 1)  # 原始查询权重更高
            
            for i, expanded_query in enumerate(expanded_queries):
                results = self._hybrid_search(expanded_query, top_k, filters)
                
                # 调整得分权重
                for result in results:
                    result.final_score *= query_weights[i]
                    
                all_results.extend(results)
            
            # 4. 去重和合并
            unique_results = {}
            for result in all_results:
                key = result.content[:100]
                if key not in unique_results or result.final_score > unique_results[key].final_score:
                    unique_results[key] = result
            
            # 5. 排序并返回
            final_results = sorted(unique_results.values(), key=lambda x: x.final_score, reverse=True)
            
            # 6. 使用LLM进行最终排序优化
            if len(final_results) > 1:
                # 转换为dict格式用于LLM排序
                dict_results = []
                for result in final_results:
                    dict_results.append({
                        "content": result.content,
                        "metadata": result.metadata,
                        "distance": 1.0 - result.vector_score
                    })
                
                ranked_results = self.llm_client.rank_and_filter_results(query, dict_results)
                
                # 重新组织结果
                if ranked_results:
                    final_results = []
                    for ranked_result in ranked_results:
                        # 找到对应的SearchResult
                        for result in unique_results.values():
                            if result.content == ranked_result.get("content"):
                                result.final_score = ranked_result.get("relevance_score", result.final_score)
                                final_results.append(result)
                                break
            
            return final_results[:top_k]
            
        except Exception as e:
            logger.error(f"扩展搜索失败: {e}")
            return self._hybrid_search(query, top_k, filters)
    
    def update_weights(self, new_weights: Dict[str, float]):
        """更新搜索权重"""
        total_weight = sum(new_weights.values())
        if total_weight > 0:
            self.search_weights = {k: v/total_weight for k, v in new_weights.items()}
            logger.info(f"搜索权重已更新: {self.search_weights}")
    
    def get_search_stats(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        try:
            all_docs = self.vector_store.collection.get()
            total_docs = len(all_docs.get("documents", []))
            
            return {
                "total_documents": total_docs,
                "search_weights": self.search_weights,
                "bm25_vocabulary_size": len(self.bm25_scorer.doc_freqs),
                "average_document_length": self.bm25_scorer.avgdl
            }
        except Exception as e:
            logger.error(f"获取搜索统计信息失败: {e}")
            return {} 