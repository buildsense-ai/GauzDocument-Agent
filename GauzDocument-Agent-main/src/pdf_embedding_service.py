#!/usr/bin/env python3
"""
PDF Embedding Service - PDF解析内容的向量化存储服务
处理parsed_content.json和images.json，将文本和图片进行embedding并存储到统一集合
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import uuid

# 导入torch检查
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch不可用，某些高级功能可能受限")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️ ChromaDB不可用，请安装: pip install chromadb")

# 尝试导入OpenRouter客户端用于图片描述
try:
    from src.openrouter_client import OpenRouterClient
    OPENROUTER_CLIENT_AVAILABLE = True
except ImportError:
    OPENROUTER_CLIENT_AVAILABLE = False
    print("⚠️ OpenRouter客户端不可用，图片VLM描述功能受限")

# 尝试导入MinIO客户端
try:
    from minio import Minio
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    print("⚠️ MinIO客户端不可用，图片上传功能受限")

# 导入prompt加载器
try:
    from src.prompts.loader import get_prompt_loader
    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False

class PDFEmbeddingService:
    """PDF内容向量化服务 - 统一存储文本和图片"""
    
    def __init__(self, 
                 model_name: str = "BAAI/bge-m3", 
                 chroma_db_path: str = "rag_storage",
                 collection_name: str = "documents",
                 enable_vlm_description: bool = True,
                 enable_minio_upload: bool = True,
                 minio_endpoint: str = "43.139.19.144:9000",
                 minio_access_key: str = "minioadmin",
                 minio_secret_key: str = "minioadmin",
                 minio_bucket: str = "images",
                 minio_secure: bool = False):
        """
        初始化PDF嵌入服务
        
        Args:
            model_name: BGE-M3模型名称
            chroma_db_path: ChromaDB存储路径
            collection_name: 集合名称，统一为"documents"
            enable_vlm_description: 是否启用VLM图片描述功能
            enable_minio_upload: 是否启用MinIO上传功能
            minio_endpoint: MinIO服务端点
            minio_access_key: MinIO访问密钥
            minio_secret_key: MinIO密钥
            minio_bucket: MinIO存储桶名称
            minio_secure: 是否使用HTTPS
        """
        self.model_name = model_name
        self.chroma_db_path = chroma_db_path
        self.collection_name = collection_name
        self.enable_vlm_description = enable_vlm_description
        self.device = "cuda" if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
        self.model = None
        
        # MinIO配置
        self.enable_minio_upload = enable_minio_upload
        self.minio_endpoint = minio_endpoint
        self.minio_access_key = minio_access_key
        self.minio_secret_key = minio_secret_key
        self.minio_bucket = minio_bucket
        self.minio_secure = minio_secure
        
        # 初始化VLM客户端
        self.vlm_client = None
        if self.enable_vlm_description and OPENROUTER_CLIENT_AVAILABLE:
            try:
                self.vlm_client = OpenRouterClient()
                print("✅ VLM客户端初始化成功，将对图片进行深度描述")
            except Exception as e:
                print(f"⚠️ VLM客户端初始化失败: {e}")
        
        # 初始化MinIO客户端
        self.minio_client = None
        if self.enable_minio_upload and MINIO_AVAILABLE:
            try:
                self.minio_client = Minio(
                    self.minio_endpoint,
                    access_key=self.minio_access_key,
                    secret_key=self.minio_secret_key,
                    secure=self.minio_secure
                )
                # 检查并创建存储桶
                if not self.minio_client.bucket_exists(self.minio_bucket):
                    self.minio_client.make_bucket(self.minio_bucket)
                print(f"✅ MinIO客户端初始化成功，存储桶: {self.minio_bucket}")
            except Exception as e:
                print(f"⚠️ MinIO客户端初始化失败: {e}")
                self.minio_client = None
        
        # 初始化ChromaDB
        self._init_chroma_db()
        
    def _init_chroma_db(self):
        """初始化ChromaDB客户端和集合"""
        if not CHROMADB_AVAILABLE:
            raise RuntimeError("ChromaDB不可用，无法初始化embedding服务")
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 创建存储目录
                os.makedirs(self.chroma_db_path, exist_ok=True)
                
                # 初始化ChromaDB客户端 - 添加更多设置来避免冲突
                self.chroma_client = chromadb.PersistentClient(
                    path=self.chroma_db_path,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                        is_persistent=True
                    )
                )
                
                # 获取或创建统一集合
                self.collection = self.chroma_client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "PDF文本和图片内容统一向量化存储"}
                )
                
                print(f"✅ ChromaDB初始化成功: {self.chroma_db_path}")
                print(f"📊 使用统一集合: {self.collection_name}")
                return
                
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg and "different settings" in error_msg:
                    print(f"⚠️ ChromaDB实例冲突，尝试重置... (尝试 {attempt + 1}/{max_retries})")
                    
                    # 尝试重置ChromaDB连接
                    try:
                        if hasattr(self, 'chroma_client') and self.chroma_client:
                            self.chroma_client.reset()
                    except:
                        pass
                    
                    # 等待一下再重试
                    import time
                    time.sleep(1)
                    
                    if attempt == max_retries - 1:
                        # 最后一次尝试：删除并重新创建
                        try:
                            import shutil
                            if os.path.exists(self.chroma_db_path):
                                print(f"🔄 清理ChromaDB目录: {self.chroma_db_path}")
                                shutil.rmtree(self.chroma_db_path)
                                os.makedirs(self.chroma_db_path, exist_ok=True)
                        except Exception as cleanup_error:
                            print(f"⚠️ 清理失败: {cleanup_error}")
                else:
                    print(f"❌ ChromaDB初始化失败: {e}")
                    if attempt == max_retries - 1:
                        raise
                    else:
                        import time
                        time.sleep(1)
        
        # 如果所有重试都失败了
        raise RuntimeError("ChromaDB初始化失败，已达到最大重试次数")
    
    def _upload_to_minio(self, file_path: str, object_name: str = None) -> Optional[str]:
        """
        上传文件到MinIO并返回公共URL
        
        Args:
            file_path: 本地文件路径
            object_name: MinIO中的对象名称，如果为None则使用文件名
            
        Returns:
            Optional[str]: 公共URL，失败时返回None
        """
        if not self.minio_client or not os.path.exists(file_path):
            return None
        
        try:
            # 生成对象名称
            if object_name is None:
                # 使用时间戳和原文件名生成唯一对象名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.basename(file_path)
                name, ext = os.path.splitext(filename)
                object_name = f"{timestamp}_{uuid.uuid4().hex[:8]}_{name}{ext}"
            
            # 上传文件
            self.minio_client.fput_object(
                self.minio_bucket,
                object_name,
                file_path
            )
            
            # 构造公共URL
            if self.minio_secure:
                protocol = "https"
            else:
                protocol = "http"
            
            public_url = f"{protocol}://{self.minio_endpoint}/{self.minio_bucket}/{object_name}"
            
            print(f"✅ 文件上传到MinIO成功: {object_name}")
            return public_url
            
        except Exception as e:
            print(f"❌ MinIO上传失败: {e}")
            return None
    
    def embed_parsed_pdf(self, 
                        parsed_content_path: str, 
                        images_json_path: str,
                        parser_output_dir: str) -> Dict:
        """
        对解析后的PDF内容进行embedding
        
        Args:
            parsed_content_path: parsed_content.json文件路径
            images_json_path: images.json文件路径  
            parser_output_dir: 解析器输出目录
            
        Returns:
            Dict: embedding结果统计
        """
        stats = {
            "text_embeddings": 0,
            "image_embeddings": 0,
            "table_embeddings": 0,
            "total_embeddings": 0,
            "errors": []
        }
        
        try:
            # 获取源文件信息
            source_file, title = self._get_source_info(parsed_content_path)
            
            # 准备批量数据
            documents = []
            metadatas = []
            ids = []
            
            # 1. 处理文本内容
            if os.path.exists(parsed_content_path):
                text_docs, text_metas, text_ids = self._prepare_text_embeddings(
                    parsed_content_path, source_file, title, parser_output_dir
                )
                documents.extend(text_docs)
                metadatas.extend(text_metas)
                ids.extend(text_ids)
                stats["text_embeddings"] = len(text_docs)
                
                if text_docs:
                    print(f"✅ 准备文本embedding: {len(text_docs)}个section")
            else:
                stats["errors"].append(f"文本文件不存在: {parsed_content_path}")
            
            # 2. 处理图片内容
            if os.path.exists(images_json_path):
                image_docs, image_metas, image_ids = self._prepare_image_embeddings(
                    images_json_path, source_file, title, parser_output_dir
                )
                documents.extend(image_docs)
                metadatas.extend(image_metas)
                ids.extend(image_ids)
                stats["image_embeddings"] = len(image_docs)
                
                if image_docs:
                    print(f"✅ 准备图片embedding: {len(image_docs)}个图片")
            else:
                stats["errors"].append(f"图片文件不存在: {images_json_path}")
            
            # 3. 处理表格内容
            tables_json_path = os.path.join(parser_output_dir, "tables.json")
            if os.path.exists(tables_json_path):
                table_docs, table_metas, table_ids = self._prepare_table_embeddings(
                    tables_json_path, source_file, title, parser_output_dir
                )
                documents.extend(table_docs)
                metadatas.extend(table_metas)
                ids.extend(table_ids)
                stats["table_embeddings"] = len(table_docs)
                
                if table_docs:
                    print(f"✅ 准备表格embedding: {len(table_docs)}个表格")
            else:
                stats["errors"].append(f"表格文件不存在: {tables_json_path}")
            
            # 4. 批量添加到ChromaDB
            if documents:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                stats["total_embeddings"] = len(documents)
                print(f"✅ 批量embedding完成: {len(documents)}个项目")
            else:
                stats["errors"].append("没有找到可嵌入的内容")
                
        except Exception as e:
            error_msg = f"PDF embedding失败: {e}"
            stats["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            
        return stats
    
    def _get_source_info(self, parsed_content_path: str) -> Tuple[str, str]:
        """获取源文件信息"""
        source_file = "unknown"
        title = "unknown"
        
        try:
            if os.path.exists(parsed_content_path):
                with open(parsed_content_path, 'r', encoding='utf-8') as f:
                    content_data = json.load(f)
                    metadata_info = content_data.get("metadata", {})
                    source_file = metadata_info.get("source_file", "unknown")
                    title = metadata_info.get("title", "unknown")
                    
                    # 修复文件名编码问题
                    source_file = self._fix_filename_encoding(source_file)
                    title = self._fix_filename_encoding(title)
                    
        except Exception as e:
            print(f"⚠️ 获取源文件信息失败: {e}")
            
        return source_file, title
    
    def embed_and_store_text(self, text_chunks: List[str], 
                            source_document: str = "unknown",
                            document_type: str = "Text",
                            metadatas: Optional[List[Dict]] = None,
                            project_name: Optional[str] = None) -> Dict:
        """
        兼容性方法：将文本块嵌入并存储到向量数据库
        
        Args:
            text_chunks: 文本块列表
            source_document: 源文档名称
            document_type: 文档类型
            metadatas: 元数据列表（可选）
            
        Returns:
            Dict: 包含嵌入结果的字典
        """
        if not text_chunks:
            return {"chunks_count": 0, "collection_name": self.collection_name}
        
        try:
            # 提取项目名称（如果没有提供）
            if project_name is None:
                project_name = self._extract_project_name(source_document)
            
            # 准备文档和元数据
            documents = text_chunks
            if metadatas:
                # 如果提供了元数据，使用它们，但确保包含project_name
                processed_metadatas = []
                for metadata in metadatas:
                    enhanced_metadata = metadata.copy()
                    if "project_name" not in enhanced_metadata:
                        enhanced_metadata["project_name"] = project_name
                    processed_metadatas.append(enhanced_metadata)
            else:
                # 否则创建默认元数据
                processed_metadatas = []
                for i, text in enumerate(text_chunks):
                    metadata = {
                        "source_file": source_document,
                        "document_type": document_type,
                        "project_name": project_name,  # 🆕 项目隔离字段
                        "chunk_index": i,
                        "content_type": "text" if document_type == "Text" else "image",
                        "embedding_time": datetime.now().isoformat(),
                        "content_length": len(text)
                    }
                    processed_metadatas.append(metadata)
            
            # 生成唯一ID
            ids = []
            for i, text in enumerate(text_chunks):
                chunk_id = f"{source_document}_{document_type}_{i}_{hashlib.md5(text.encode()).hexdigest()[:8]}"
                ids.append(chunk_id)
            
            # 添加到ChromaDB
            self.collection.add(
                documents=documents,
                metadatas=processed_metadatas,
                ids=ids
            )
            
            print(f"✅ 成功嵌入 {len(text_chunks)} 个文本块到 {self.collection_name}")
            return {
                "chunks_count": len(text_chunks),
                "collection_name": self.collection_name,
                "status": "success"
            }
            
        except Exception as e:
            print(f"❌ 文本嵌入失败: {e}")
            return {
                "chunks_count": 0,
                "collection_name": self.collection_name,
                "status": "error",
                "error": str(e)
            }
    
    def _extract_project_name(self, source_file: str) -> str:
        """
        从源文件名中提取项目名称
        
        Args:
            source_file: 源文件路径或名称
            
        Returns:
            str: 提取的项目名称
        """
        if not source_file or source_file == "unknown":
            return "default"
            
        # 获取文件名（去掉路径）
        filename = os.path.basename(source_file)
        
        # 去掉文件扩展名
        name_without_ext = os.path.splitext(filename)[0]
        
        # 常见的项目名称提取模式
        project_patterns = [
            # 1. 直接包含项目关键词的文件名
            r'([^_\-\s]+(?:宗祠|寺庙|古建|文物|保护|修缮|设计|方案))',
            r'([^_\-\s]+(?:村|镇|县|市|区))',
            
            # 2. 以特定分隔符分割的第一部分
            r'^([^_\-\s]+)',
            
            # 3. 中文项目名称模式
            r'([\u4e00-\u9fff]{2,8}(?:宗祠|寺庙|古建|文物))',
            
            # 4. 如果包含"刘氏宗祠"等具体名称
            r'(刘氏宗祠|欧村刘氏宗祠)',
        ]
        
        import re
        
        # 按优先级尝试不同的提取模式
        for pattern in project_patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                project_name = match.group(1).strip()
                # 清理项目名称
                project_name = re.sub(r'[^\u4e00-\u9fff\w]', '', project_name)
                if len(project_name) >= 2:  # 至少2个字符
                    return project_name
        
        # 如果没有匹配到模式，使用文件名的前几个字符
        clean_name = re.sub(r'[^\u4e00-\u9fff\w]', '', name_without_ext)
        if len(clean_name) >= 2:
            # 取前4-8个字符作为项目名
            return clean_name[:min(8, len(clean_name))]
        
        # 最后回退方案
        return "default"
    
    def _fix_filename_encoding(self, filename: str) -> str:
        """修复文件名编码问题"""
        if not filename or filename == "unknown":
            return filename
            
        try:
            # 尝试修复URL编码的中文字符
            import urllib.parse
            # 先尝试URL解码
            try:
                decoded = urllib.parse.unquote(filename, encoding='utf-8')
                if decoded != filename:
                    filename = decoded
            except:
                pass
            
            # 处理常见的编码问题
            # 如果包含特殊编码字符，尝试重新编码
            if 'å' in filename or 'ç' in filename or 'è' in filename:
                try:
                    # 尝试从latin-1解码为utf-8
                    fixed = filename.encode('latin-1').decode('utf-8')
                    filename = fixed
                except:
                    # 如果失败，尝试其他方法
                    try:
                        # 尝试从gbk解码
                        fixed = filename.encode('latin-1').decode('gbk')
                        filename = fixed
                    except:
                        pass
            
            # 提取文件名（去掉路径）
            filename = os.path.basename(filename)
            
            # 如果文件名仍然包含乱码，尝试从文件路径中提取
            if any(char in filename for char in ['å', 'ç', 'è', 'ã', 'â']):
                # 尝试使用时间戳作为标识
                import re
                timestamp_match = re.search(r'(\d{13})', filename)
                if timestamp_match:
                    timestamp = timestamp_match.group(1)
                    # 尝试找到PDF扩展名
                    if '.pdf' in filename.lower():
                        filename = f"文档_{timestamp}.pdf"
                    else:
                        filename = f"文档_{timestamp}"
                else:
                    # 如果没有时间戳，使用通用名称
                    if '.pdf' in filename.lower():
                        filename = "PDF文档.pdf"
                    else:
                        filename = "PDF文档"
            
        except Exception as e:
            print(f"⚠️ 修复文件名编码失败: {e}")
            # 如果所有方法都失败，使用通用名称
            filename = "PDF文档"
            
        return filename
    
    def _prepare_text_embeddings(self, parsed_content_path: str, source_file: str, 
                                title: str, parser_output_dir: str) -> Tuple[List[str], List[Dict], List[str]]:
        """准备文本内容的embedding数据"""
        documents = []
        metadatas = []
        ids = []
        
        try:
            # 提取项目名称
            project_name = self._extract_project_name(source_file)
            print(f"📋 文本内容项目名称: {project_name}")
            
            # 读取解析内容
            with open(parsed_content_path, 'r', encoding='utf-8') as f:
                content_data = json.load(f)
            
            # 处理每个section
            sections = content_data.get("sections", [])
            
            for i, section in enumerate(sections):
                content = section.get("content", "").strip()
                if not content:
                    continue
                    
                # 生成唯一ID
                section_id = self._generate_id(source_file, "text", i, content)
                
                # 构建元数据 - 添加项目名称
                section_metadata = {
                    "source_file": source_file,
                    "document_title": title,
                    "content_type": "text",  # 关键字段：区分文本和图片
                    "project_name": project_name,  # 🆕 项目隔离字段
                    "section_index": i,
                    "source_page": section.get("source_page", i),
                    "content_length": len(content),
                    "embedding_time": datetime.now().isoformat(),
                    "parser_output_path": parser_output_dir
                }
                
                documents.append(content)
                metadatas.append(section_metadata)
                ids.append(section_id)
                
        except Exception as e:
            print(f"❌ 文本embedding准备失败: {e}")
            
        return documents, metadatas, ids
    
    def _prepare_image_embeddings(self, images_json_path: str, source_file: str,
                                 title: str, parser_output_dir: str) -> Tuple[List[str], List[Dict], List[str]]:
        """准备图片内容的embedding数据 - 支持VLM深度分析"""
        documents = []
        metadatas = []
        ids = []
        
        try:
            # 提取项目名称
            project_name = self._extract_project_name(source_file)
            print(f"📸 图片内容项目名称: {project_name}")
            
            # 读取图片信息
            with open(images_json_path, 'r', encoding='utf-8') as f:
                images_data = json.load(f)
            
            print(f"📸 处理 {len(images_data)} 张图片，VLM描述启用: {self.enable_vlm_description}")
            
            for image_id, image_info in images_data.items():
                # 获取基本信息
                caption = image_info.get("caption", f"图片 {image_id}")
                # [已移除] context = image_info.get("context", "") - 不再使用context字段
                image_path = image_info.get("image_path", "")
                
                # 构建完整的图片路径
                if image_path and not os.path.isabs(image_path):
                    full_image_path = os.path.join(parser_output_dir, image_path)
                else:
                    full_image_path = image_path
                
                # 尝试通过VLM生成深度描述
                image_description = self._generate_image_description(
                    full_image_path, caption, image_id
                )
                
                # 如果生成的描述为空，使用基本信息
                if not image_description.strip():
                    image_description = f"{caption}"
                    # [已移除] 不再添加context信息
                
                # 🆕 上传图片到MinIO
                minio_url = None
                if self.enable_minio_upload and os.path.exists(full_image_path):
                    # 生成对象名称：项目_图片ID_原文件名
                    filename = os.path.basename(full_image_path)
                    name, ext = os.path.splitext(filename)
                    object_name = f"images/{source_file}_{image_id}_{name}{ext}"
                    minio_url = self._upload_to_minio(full_image_path, object_name)
                
                # 生成唯一ID
                img_id = self._generate_id(source_file, "image", image_id, image_path)
                
                # 构建元数据 - 添加项目名称
                image_metadata = {
                    "source_file": source_file,
                    "document_title": title,
                    "content_type": "image",  # 关键字段：区分文本和图片
                    "project_name": project_name,  # 🆕 项目隔离字段
                    "image_id": image_id,
                    "image_path": image_path,  # 保留原始本地路径
                    "minio_url": minio_url,    # 🆕 添加MinIO URL
                    "caption": caption,
                    # [已移除] "context": context, - 不再存储context字段
                    "vlm_description": image_description,  # 🆕 保存完整的VLM描述到元数据
                    "original_caption": caption,  # 🆕 保存原始标题
                    "width": image_info.get("width", 0),
                    "height": image_info.get("height", 0),
                    "figure_size": image_info.get("figure_size", 0),
                    "figure_aspect": image_info.get("figure_aspect", 1.0),
                    "embedding_time": datetime.now().isoformat(),
                    "parser_output_path": parser_output_dir,
                    "vlm_description_enabled": self.enable_vlm_description,
                    "has_vlm_description": self.vlm_client is not None,
                    "vlm_success": not image_description.startswith("Error:") and len(image_description) > len(caption),  # 🆕 VLM是否成功生成描述
                    "minio_upload_enabled": self.enable_minio_upload,
                    "has_minio_url": minio_url is not None
                }
                
                documents.append(image_description)
                metadatas.append(image_metadata)
                ids.append(img_id)
                
        except Exception as e:
            print(f"❌ 图片embedding准备失败: {e}")
            
        return documents, metadatas, ids
    
    def _prepare_table_embeddings(self, tables_json_path: str, source_file: str,
                                 title: str, parser_output_dir: str) -> Tuple[List[str], List[Dict], List[str]]:
        """准备表格内容的embedding数据 - 支持VLM深度分析"""
        documents = []
        metadatas = []
        ids = []
        
        try:
            # 提取项目名称
            project_name = self._extract_project_name(source_file)
            print(f"📊 表格内容项目名称: {project_name}")
            
            # 读取表格信息
            with open(tables_json_path, 'r', encoding='utf-8') as f:
                tables_data = json.load(f)
            
            print(f"📊 处理 {len(tables_data)} 个表格，VLM描述启用: {self.enable_vlm_description}")
            
            for table_id, table_info in tables_data.items():
                # 获取基本信息
                caption = table_info.get("caption", f"表格 {table_id}")
                table_path = table_info.get("table_path", "")
                
                # 构建完整的表格图片路径
                if table_path and not os.path.isabs(table_path):
                    full_table_path = os.path.join(parser_output_dir, table_path)
                else:
                    full_table_path = table_path
                
                # 尝试通过VLM生成表格描述
                table_description = self._generate_table_description(
                    full_table_path, caption, table_id
                )
                
                # 如果生成的描述为空，使用基本信息
                if not table_description.strip():
                    table_description = f"表格: {caption}"
                
                # 🆕 上传表格图片到MinIO
                minio_url = None
                if self.enable_minio_upload and os.path.exists(full_table_path):
                    # 生成对象名称：项目_表格ID_原文件名
                    filename = os.path.basename(full_table_path)
                    name, ext = os.path.splitext(filename)
                    object_name = f"tables/{source_file}_{table_id}_{name}{ext}"
                    minio_url = self._upload_to_minio(full_table_path, object_name)
                
                # 生成唯一ID
                table_id_str = self._generate_id(source_file, "table", table_id, table_path)
                
                # 构建元数据 - 添加项目名称
                table_metadata = {
                    "source_file": source_file,
                    "document_title": title,
                    "content_type": "table",  # 关键字段：区分文本、图片和表格
                    "project_name": project_name,  # 🆕 项目隔离字段
                    "table_id": table_id,
                    "table_path": table_path,  # 保留原始本地路径
                    "minio_url": minio_url,    # 🆕 添加MinIO URL
                    "caption": caption,
                    "vlm_description": table_description,  # 🆕 保存完整的VLM表格描述到元数据
                    "original_caption": caption,  # 🆕 保存原始标题
                    "width": table_info.get("width", 0),
                    "height": table_info.get("height", 0),
                    "figure_size": table_info.get("figure_size", 0),
                    "figure_aspect": table_info.get("figure_aspect", 1.0),
                    "embedding_time": datetime.now().isoformat(),
                    "parser_output_path": parser_output_dir,
                    "vlm_description_enabled": self.enable_vlm_description,
                    "has_vlm_description": self.vlm_client is not None,
                    "vlm_success": not table_description.startswith("Error:") and len(table_description) > len(caption),  # 🆕 VLM是否成功生成描述
                    "minio_upload_enabled": self.enable_minio_upload,
                    "has_minio_url": minio_url is not None
                }
                
                documents.append(table_description)
                metadatas.append(table_metadata)
                ids.append(table_id_str)
                
        except Exception as e:
            print(f"❌ 表格embedding准备失败: {e}")
            
        return documents, metadatas, ids
    
    def _generate_table_description(self, table_path: str, caption: str, table_id: str) -> str:
        """
        生成表格描述 - 使用VLM分析表格内容
        
        Args:
            table_path: 表格图片路径
            caption: 基本标题
            table_id: 表格ID
            
        Returns:
            str: 表格描述文本
        """
        # 如果VLM客户端可用且表格图片存在，使用VLM生成描述
        if self.vlm_client and os.path.exists(table_path):
            try:
                print(f"📊 对表格 {table_id} 进行VLM深度分析...")
                
                # 构建专门针对表格的VLM提示词
                try:
                    # 使用prompt模板
                    if PROMPT_LOADER_AVAILABLE:
                        prompt_loader = get_prompt_loader()
                        prompt = prompt_loader.get_prompt("pdf_processing", "table_analysis_prompt")
                    else:
                        prompt = """请作为专业的表格分析师，详细分析和描述这个表格的内容。请按以下结构回答：

1. 表格类型：确定这是数据表、对比表、统计表、时间表还是其他类型的表格
2. 表格结构：描述表格的行数、列数、表头和整体结构
3. 核心数据：详细列出表格中的关键数据、数值和信息
4. 文本内容：完整转录表格中的所有文字、数字、标题、单位等
5. 数据关系：分析表格数据之间的关系、趋势和模式
6. 关键信息：提炼表格要表达的核心信息和结论

请用中文回答，尽可能详细和准确地转录表格内容。"""
                except Exception as e:
                    print(f"警告：加载表格分析prompt模板失败，使用备用prompt: {e}")
                    prompt = """请作为专业的表格分析师，详细分析和描述这个表格的内容。请按以下结构回答：

1. 表格类型：确定这是数据表、对比表、统计表、时间表还是其他类型的表格
2. 表格结构：描述表格的行数、列数、表头和整体结构
3. 核心数据：详细列出表格中的关键数据、数值和信息
4. 文本内容：完整转录表格中的所有文字、数字、标题、单位等
5. 数据关系：分析表格数据之间的关系、趋势和模式
6. 关键信息：提炼表格要表达的核心信息和结论

请用中文回答，尽可能详细和准确地转录表格内容。"""
                
                # 调用VLM生成描述
                vlm_description = self.vlm_client.get_image_description_gemini(
                    table_path, prompt=prompt
                )
                
                # 检查VLM描述是否成功
                if vlm_description and not vlm_description.startswith("Error:"):
                    # 组合完整描述
                    full_description = f"表格标题: {caption}\n\n详细内容: {vlm_description}"
                    
                    print(f"✅ 表格VLM描述生成成功: {table_id}")
                    return full_description
                else:
                    print(f"⚠️ 表格VLM描述生成失败: {table_id}, 错误: {vlm_description}")
                    
            except Exception as e:
                print(f"⚠️ 表格VLM描述生成异常: {table_id}, 错误: {e}")
        
        # 如果VLM不可用或失败，使用基本信息
        basic_description = f"表格标题: {caption}"
        
        print(f"📝 使用基本描述: {table_id}")
        return basic_description
    
    def _generate_image_description(self, image_path: str, caption: str, image_id: str) -> str:
        """
        生成图片描述 - 优先使用VLM，失败时使用基本信息
        
        Args:
            image_path: 图片路径
            caption: 基本标题
            image_id: 图片ID
            
        Returns:
            str: 图片描述文本
        """
        # 如果VLM客户端可用且图片存在，使用VLM生成描述
        if self.vlm_client and os.path.exists(image_path):
            try:
                print(f"🔍 对图片 {image_id} 进行VLM深度分析...")
                
                # 构建针对Gemini 2.5 Flash优化的VLM提示词
                try:
                    # 使用prompt模板
                    if PROMPT_LOADER_AVAILABLE:
                        prompt_loader = get_prompt_loader()
                        prompt = prompt_loader.get_prompt("pdf_processing", "image_analysis_prompt")
                    else:
                        # 使用备用prompt
                        raise Exception("PromptLoader不可用")
                except Exception as e:
                    print(f"警告：加载图片分析prompt模板失败，使用备用prompt: {e}")
                    # 使用备用prompt
                prompt = """# 角色
你是一个精炼的图像分析引擎。

# 任务
为给定的图片生成一段极其精简的核心描述，该描述将用于语义搜索。你的目标是“索引”图片内容，而不是“解说”图片。

# 核心规则
1.  **专注于关键元素**：只识别和描述图片中最核心的1-3个主体、状态或概念。
2.  **提取关键词，而非完整叙述**：生成能够代表图片内容的关键词组合或短语，而不是一个故事性的段落。多使用名词和关键动词。
3.  **结构建议**：尽量使用“主体 + 状态/行为 + 关键对象”的结构。例如，“一张关于[主题]的[图表类型]”或“[主体]的[某种状态]特写”。
4.  **绝对简洁**：描述通常应在15到30字之间。剔除所有不必要的修饰词和引导语（例如不要用“这张图片显示了…”）。
5.  **忽略无关上下文**：如果图片附带的参考文字与图片内容不符，必须完全忽略该文字。

# 示例
- **输入图片**: 一张管道接口处严重生锈的照片。
- **合格输出**: “管道接口处的严重腐蚀与金属锈迹特写。”
- **不合格输出**: “这张图片向我们展示了一个看起来很旧的金属管道，它连接着另一个部分，连接处有很多棕色的锈迹，可能是因为长时间暴露在潮湿环境中导致的。”
"""
                
                # [已移除] 不再添加context信息到VLM提示词
                
                # 调用VLM生成描述
                vlm_description = self.vlm_client.get_image_description_gemini(
                    image_path, prompt=prompt
                )
                
                # 检查VLM描述是否成功
                if vlm_description and not vlm_description.startswith("Error:"):
                    # 组合完整描述
                    full_description = f"图片标题: {caption}\n\n详细描述: {vlm_description}"
                    # [已移除] 不再添加context信息到VLM描述
                    
                    print(f"✅ VLM描述生成成功: {image_id}")
                    return full_description
                else:
                    print(f"⚠️ VLM描述生成失败: {image_id}, 错误: {vlm_description}")
                    
            except Exception as e:
                print(f"⚠️ VLM描述生成异常: {image_id}, 错误: {e}")
        
        # 如果VLM不可用或失败，使用基本信息
        basic_description = f"图片标题: {caption}"
        # [已移除] 不再添加context信息到基本描述
        
        print(f"📝 使用基本描述: {image_id}")
        return basic_description
    
    def _generate_id(self, source_file: str, content_type: str, index_or_id: any, content: str) -> str:
        """生成内容的唯一ID"""
        # 使用源文件路径、内容类型、索引和内容hash生成唯一ID
        content_hash = hashlib.md5(str(content).encode('utf-8')).hexdigest()[:8]
        file_name = os.path.basename(source_file)
        return f"{content_type}_{file_name}_{index_or_id}_{content_hash}"
    
    def search(self, query: str, 
               content_type: Optional[str] = None,
               top_k: int = 5, 
               source_file_filter: Optional[str] = None,
               project_name: Optional[str] = None) -> List[Dict]:
        """
        统一搜索接口
        
        Args:
            query: 搜索查询
            content_type: 内容类型过滤 ("text", "image", "table", None表示搜索全部)
            top_k: 返回结果数量
            source_file_filter: 源文件过滤器
            project_name: 项目名称过滤器（实现项目隔离）
            
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            # 构建查询条件
            where_condition = {}
            
            if content_type:
                where_condition["content_type"] = content_type
                
            if source_file_filter:
                where_condition["source_file"] = source_file_filter
                
            if project_name:
                # 🔧 修复：确保完全的项目隔离
                # 严格匹配项目名称，只返回有project_name字段且值匹配的数据
                if where_condition:
                    # 如果已有其他条件，使用$and组合
                    where_condition = {
                        "$and": [
                            where_condition,  # 现有条件
                            {"project_name": {"$eq": project_name}}  # 严格匹配项目名称
                        ]
                    }
                else:
                    # 如果没有其他条件，直接使用项目条件
                    where_condition = {"project_name": {"$eq": project_name}}
                print(f"🔍 严格限定项目范围: {project_name}")
            
            # 执行搜索
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_condition if where_condition else None
            )
            
            # 格式化结果
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    result = {
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if results["distances"] else None,
                        "id": results["ids"][0][i],
                        "content_type": results["metadatas"][0][i].get("content_type", "unknown")
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            return []
    
    def search_similar_content(self, query: str, 
                              content_type: Optional[str] = None,
                              top_k: int = 5, 
                              source_file_filter: Optional[str] = None,
                              project_name: Optional[str] = None) -> List[Dict]:
        """
        搜索相似内容 - search方法的友好接口
        
        Args:
            query: 搜索查询
            content_type: 内容类型过滤 ("text", "image", "table", None表示搜索全部)
            top_k: 返回结果数量
            source_file_filter: 源文件过滤器
            project_name: 项目名称过滤器（实现项目隔离）
            
        Returns:
            List[Dict]: 搜索结果，每个结果包含内容、元数据和相似度
        """
        # 调用原始search方法
        results = self.search(query, content_type, top_k, source_file_filter, project_name)
        
        # 转换distance为similarity (distance越小，相似度越高)
        for result in results:
            if result.get("distance") is not None:
                # 将distance转换为similarity (0-1之间，1表示完全相似)
                result["similarity"] = 1 / (1 + result["distance"])
            else:
                result["similarity"] = 0
                
            # 添加一些用户友好的字段
            metadata = result.get("metadata", {})
            result["document_type"] = metadata.get("content_type", "unknown")
            result["source_document"] = metadata.get("source_file", "unknown")
            result["document_title"] = metadata.get("document_title", "unknown")
            
        return results
    
    def search_text_only(self, query: str, top_k: int = 5, source_file_filter: Optional[str] = None, project_name: Optional[str] = None) -> List[Dict]:
        """
        只搜索文本内容
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            source_file_filter: 源文件过滤器
            project_name: 项目名称过滤器（实现项目隔离）
            
        Returns:
            List[Dict]: 搜索结果
        """
        return self.search(query, content_type="text", top_k=top_k, source_file_filter=source_file_filter, project_name=project_name)
    
    def search_images_only(self, query: str, top_k: int = 5, source_file_filter: Optional[str] = None, project_name: Optional[str] = None) -> List[Dict]:
        """
        只搜索图片内容
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            source_file_filter: 源文件过滤器
            project_name: 项目名称过滤器（实现项目隔离）
            
        Returns:
            List[Dict]: 搜索结果
        """
        return self.search(query, content_type="image", top_k=top_k, source_file_filter=source_file_filter, project_name=project_name)
    
    def search_tables_only(self, query: str, top_k: int = 5, source_file_filter: Optional[str] = None, project_name: Optional[str] = None) -> List[Dict]:
        """
        只搜索表格内容
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            source_file_filter: 源文件过滤器
            project_name: 项目名称过滤器（实现项目隔离）
            
        Returns:
            List[Dict]: 搜索结果
        """
        return self.search(query, content_type="table", top_k=top_k, source_file_filter=source_file_filter, project_name=project_name)
    
    def search_by_project(self, query: str, project_name: str, top_k: int = 5, content_type: Optional[str] = None) -> List[Dict]:
        """
        按项目搜索 - 项目隔离的专用接口
        
        Args:
            query: 搜索查询
            project_name: 项目名称（必填）
            top_k: 返回结果数量
            content_type: 内容类型过滤 ("text", "image", "table", None表示搜索全部)
            
        Returns:
            List[Dict]: 搜索结果
        """
        print(f"🏢 项目限定搜索: '{project_name}' - 查询: '{query}'")
        return self.search(query, content_type=content_type, top_k=top_k, project_name=project_name)
    
    def get_available_projects(self) -> List[str]:
        """
        获取所有可用的项目名称
        
        Returns:
            List[str]: 项目名称列表
        """
        try:
            # 获取所有元数据
            all_results = self.collection.get()
            
            # 提取所有项目名称
            projects = set()
            for metadata in all_results["metadatas"]:
                project_name = metadata.get("project_name", "default")
                projects.add(project_name)
            
            project_list = sorted(list(projects))
            print(f"📋 发现 {len(project_list)} 个项目: {', '.join(project_list)}")
            return project_list
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}")
            return []
    
    def get_project_stats(self, project_name: str) -> Dict:
        """
        获取特定项目的统计信息
        
        Args:
            project_name: 项目名称
            
        Returns:
            Dict: 项目统计信息
        """
        try:
            # 获取项目的所有内容 - 使用严格匹配
            where_condition = {"project_name": {"$eq": project_name}}
            results = self.collection.get(where=where_condition)
            
            total_count = len(results["documents"])
            text_count = 0
            image_count = 0
            table_count = 0
            
            for metadata in results["metadatas"]:
                content_type = metadata.get("content_type", "unknown")
                if content_type == "text":
                    text_count += 1
                elif content_type == "image":
                    image_count += 1
                elif content_type == "table":
                    table_count += 1
            
            stats = {
                "project_name": project_name,
                "total_embeddings": total_count,
                "text_embeddings": text_count,
                "image_embeddings": image_count,
                "table_embeddings": table_count,
                "collection_name": self.collection_name
            }
            
            print(f"📊 项目 '{project_name}' 统计: 总计{total_count}条 (文本{text_count}, 图片{image_count}, 表格{table_count})")
            return stats
            
        except Exception as e:
            print(f"❌ 获取项目统计失败: {e}")
            return {"project_name": project_name, "error": str(e)}
    
    def migrate_legacy_data(self) -> Dict:
        """
        迁移老数据，为没有project_name字段的数据添加项目名称
        
        Returns:
            Dict: 迁移结果统计
        """
        try:
            print("🔄 开始迁移老数据，为缺少project_name的数据添加项目名称...")
            
            # 获取所有数据
            all_results = self.collection.get()
            
            migrated_count = 0
            total_count = len(all_results["documents"])
            
            print(f"📊 找到 {total_count} 条数据，检查哪些需要迁移...")
            
            # 批量更新没有project_name的数据
            ids_to_update = []
            metadatas_to_update = []
            
            for i, metadata in enumerate(all_results["metadatas"]):
                doc_id = all_results["ids"][i]
                
                # 如果没有project_name字段，添加它
                if "project_name" not in metadata:
                    source_file = metadata.get("source_file", "unknown")
                    project_name = self._extract_project_name(source_file)
                    
                    # 更新元数据
                    updated_metadata = metadata.copy()
                    updated_metadata["project_name"] = project_name
                    
                    ids_to_update.append(doc_id)
                    metadatas_to_update.append(updated_metadata)
                    migrated_count += 1
                    
                    if migrated_count <= 5:  # 只显示前5个示例
                        print(f"  📄 {source_file} → 项目: {project_name}")
            
            # 执行批量更新
            if ids_to_update:
                print(f"\n🔄 正在更新 {len(ids_to_update)} 条数据...")
                self.collection.update(
                    ids=ids_to_update,
                    metadatas=metadatas_to_update
                )
                print(f"✅ 数据迁移完成!")
            else:
                print("ℹ️ 所有数据都已包含project_name字段，无需迁移")
            
            # 返回迁移统计
            result = {
                "total_documents": total_count,
                "migrated_documents": migrated_count,
                "status": "success",
                "message": f"成功迁移 {migrated_count}/{total_count} 条数据"
            }
            
            print(f"\n📋 迁移结果: {result['message']}")
            return result
            
        except Exception as e:
            error_msg = f"数据迁移失败: {e}"
            print(f"❌ {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "migrated_documents": 0
            }
    
    def get_legacy_data_stats(self) -> Dict:
        """
        获取老数据统计（没有project_name字段的数据）
        
        Returns:
            Dict: 老数据统计信息
        """
        try:
            # 获取所有数据
            all_results = self.collection.get()
            
            total_count = len(all_results["documents"])
            legacy_count = 0
            projects_with_data = {}
            
            for metadata in all_results["metadatas"]:
                if "project_name" not in metadata:
                    legacy_count += 1
                    # 统计来源文件
                    source_file = metadata.get("source_file", "unknown")
                    if source_file not in projects_with_data:
                        projects_with_data[source_file] = 0
                    projects_with_data[source_file] += 1
            
            stats = {
                "total_documents": total_count,
                "legacy_documents": legacy_count,
                "modern_documents": total_count - legacy_count,
                "legacy_files": list(projects_with_data.keys()),
                "legacy_file_stats": projects_with_data
            }
            
            print(f"📊 老数据统计: {legacy_count}/{total_count} 条数据缺少project_name字段")
            if projects_with_data:
                print("📁 涉及的文件:")
                for file, count in list(projects_with_data.items())[:5]:  # 只显示前5个
                    print(f"  - {file}: {count} 条")
                if len(projects_with_data) > 5:
                    print(f"  - ... 还有 {len(projects_with_data) - 5} 个文件")
            
            return stats
            
        except Exception as e:
            print(f"❌ 获取老数据统计失败: {e}")
            return {"error": str(e)}
    
    def search_by_filename(self, filename: str, top_k: int = 10) -> List[Dict]:
        """
        按文件名搜索所有内容
        
        Args:
            filename: 文件名（支持部分匹配）
            top_k: 返回结果数量
            
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            # 使用where条件过滤文件名
            where_condition = {
                "source_file": {
                    "$contains": filename
                }
            }
            
            # 执行搜索（使用空查询获取所有匹配的文件）
            results = self.collection.query(
                query_texts=[""],  # 空查询
                n_results=top_k,
                where=where_condition
            )
            
            # 格式化结果
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i]
                    formatted_result = {
                        "content": doc[:200] + "..." if len(doc) > 200 else doc,
                        "metadata": metadata,
                        "distance": results["distances"][0][i] if results["distances"] and results["distances"][0] else 0.0,
                        "content_type": metadata.get("content_type", "unknown"),
                        "source_file": metadata.get("source_file", "unknown")
                    }
                    formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ 按文件名搜索失败: {e}")
            return []
    
    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        try:
            total_count = self.collection.count()
            
            # 获取按内容类型分组的统计
            stats = {
                "total_embeddings": total_count,
                "collection_name": self.collection_name
            }
            
            # 尝试获取分类统计（如果集合不为空）
            if total_count > 0:
                try:
                    # 获取所有元数据来统计类型分布
                    all_results = self.collection.get()
                    
                    text_count = 0
                    image_count = 0
                    table_count = 0
                    
                    for metadata in all_results["metadatas"]:
                        content_type = metadata.get("content_type", "unknown")
                        if content_type == "text":
                            text_count += 1
                        elif content_type == "image":
                            image_count += 1
                        elif content_type == "table":
                            table_count += 1
                    
                    stats["text_embeddings"] = text_count
                    stats["image_embeddings"] = image_count
                    stats["table_embeddings"] = table_count
                    
                except Exception as e:
                    print(f"⚠️ 获取详细统计失败: {e}")
                    stats["text_embeddings"] = "unknown"
                    stats["image_embeddings"] = "unknown"
                    stats["table_embeddings"] = "unknown"
            else:
                stats["text_embeddings"] = 0
                stats["image_embeddings"] = 0
                stats["table_embeddings"] = 0
            
            return stats
            
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
            return {"error": str(e)} 