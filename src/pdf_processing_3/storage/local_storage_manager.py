"""
Local Storage Manager for PDF Processing V3

本地存储管理器，负责：
- 项目隔离的目录管理
- JSON文件的读写
- 媒体文件的保存
- 数据清理和维护
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging

from ..models.final_schema_v3 import FinalMetadataSchemaV3

logger = logging.getLogger(__name__)


class LocalStorageManager:
    """
    本地存储管理器
    
    目录结构:
    project_data/
    ├── {project_id}/
    │   ├── {document_id}/
    │   │   ├── v3_final_metadata.json      # 最终Schema
    │   │   ├── mineru_raw_output.json      # Mineru原始输出
    │   │   ├── process_data.json           # 过程数据
    │   │   └── media/                      # 图片、表格文件
    │   │       ├── images/
    │   │       └── tables/
    │   └── project_metadata.json          # 项目级元数据
    """
    
    def __init__(self, base_path: str = "./project_data"):
        """
        初始化存储管理器
        
        Args:
            base_path: 项目数据根目录路径
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        # 创建必要的子目录结构
        self._ensure_base_structure()
        
        logger.info(f"LocalStorageManager初始化完成，存储路径: {self.base_path}")
    
    def _ensure_base_structure(self):
        """确保基础目录结构存在"""
        # 创建示例项目目录（如果不存在）
        readme_path = self.base_path / "README.md"
        if not readme_path.exists():
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write("""# PDF Processing V3 项目数据存储

此目录存储所有V3版本处理的PDF数据：

## 目录结构
```
project_data/
├── {project_id}/
│   ├── {document_id}/
│   │   ├── v3_final_metadata.json      # 最终Schema
│   │   ├── mineru_raw_output.json      # Mineru原始输出
│   │   ├── process_data.json           # 过程数据
│   │   └── media/                      # 图片、表格文件
│   │       ├── images/
│   │       └── tables/
│   └── project_metadata.json          # 项目级元数据
```

## 项目隔离
每个项目ID对应一个独立的目录，确保数据隔离和组织清晰。
""")
    
    def get_project_path(self, project_id: str) -> Path:
        """获取项目根目录路径"""
        return self.base_path / project_id
    
    def get_document_path(self, project_id: str, document_id: str) -> Path:
        """获取文档目录路径"""
        return self.get_project_path(project_id) / document_id
    
    def get_media_path(self, project_id: str, document_id: str, media_type: str = "images") -> Path:
        """
        获取媒体文件目录路径
        
        Args:
            project_id: 项目ID
            document_id: 文档ID
            media_type: 媒体类型 ("images" 或 "tables")
        """
        return self.get_document_path(project_id, document_id) / "media" / media_type
    
    async def save_final_metadata(self, schema: FinalMetadataSchemaV3) -> str:
        """
        保存最终metadata到JSON文件
        
        Args:
            schema: V3版本的最终Schema对象
            
        Returns:
            保存文件的完整路径
        """
        if not schema.document_summary:
            raise ValueError("Schema缺少document_summary")
            
        project_id = schema.document_summary.rtr_project_id
        document_id = schema.document_summary.rtr_document_id
        
        if not project_id or not document_id:
            raise ValueError("Schema缺少必要的项目ID或文档ID")
        
        # 确保目录存在
        doc_path = self.get_document_path(project_id, document_id)
        doc_path.mkdir(parents=True, exist_ok=True)
        
        # 更新最后修改时间
        schema.sys_last_updated = datetime.now().isoformat()
        
        # 保存JSON文件
        file_path = doc_path / "v3_final_metadata.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(schema.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存最终metadata: {file_path}")
        return str(file_path)
    
    async def load_final_metadata(self, project_id: str, document_id: str) -> Optional[FinalMetadataSchemaV3]:
        """
        从JSON文件加载最终metadata
        
        Args:
            project_id: 项目ID
            document_id: 文档ID
            
        Returns:
            加载的Schema对象，如果文件不存在返回None
        """
        file_path = self.get_document_path(project_id, document_id) / "v3_final_metadata.json"
        
        if not file_path.exists():
            logger.warning(f"Metadata文件不存在: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 这里可以添加数据验证和版本兼容性处理
            logger.info(f"加载metadata成功: {file_path}")
            return data  # 暂时返回原始dict，后续可以转换为Schema对象
            
        except Exception as e:
            logger.error(f"加载metadata失败: {file_path}, 错误: {e}")
            return None
    
    async def save_mineru_raw_output(self, raw_output: Dict[str, Any], project_id: str, document_id: str) -> str:
        """
        保存Mineru原始输出
        
        Args:
            raw_output: Mineru返回的原始JSON数据
            project_id: 项目ID
            document_id: 文档ID
            
        Returns:
            保存文件的完整路径
        """
        doc_path = self.get_document_path(project_id, document_id)
        doc_path.mkdir(parents=True, exist_ok=True)
        
        file_path = doc_path / "mineru_raw_output.json"
        
        # 添加保存时间戳
        output_with_meta = {
            "saved_at": datetime.now().isoformat(),
            "project_id": project_id,
            "document_id": document_id,
            "raw_output": raw_output
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(output_with_meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存Mineru原始输出: {file_path}")
        return str(file_path)
    
    async def save_process_data(self, process_data: Dict[str, Any], project_id: str, document_id: str) -> str:
        """
        保存过程数据
        
        Args:
            process_data: 过程处理数据
            project_id: 项目ID  
            document_id: 文档ID
            
        Returns:
            保存文件的完整路径
        """
        doc_path = self.get_document_path(project_id, document_id)
        doc_path.mkdir(parents=True, exist_ok=True)
        
        file_path = doc_path / "process_data.json"
        
        # 添加保存时间戳
        data_with_meta = {
            "saved_at": datetime.now().isoformat(),
            "project_id": project_id,
            "document_id": document_id,
            "process_data": process_data
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_with_meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存过程数据: {file_path}")
        return str(file_path)
    
    async def save_media_file(self, 
                              file_data: bytes, 
                              file_name: str, 
                              project_id: str, 
                              document_id: str, 
                              media_type: str = "images") -> str:
        """
        保存媒体文件（图片、表格等）
        
        Args:
            file_data: 文件的二进制数据
            file_name: 文件名
            project_id: 项目ID
            document_id: 文档ID
            media_type: 媒体类型 ("images" 或 "tables")
            
        Returns:
            保存文件的相对路径（相对于项目根目录）
        """
        media_path = self.get_media_path(project_id, document_id, media_type)
        media_path.mkdir(parents=True, exist_ok=True)
        
        file_path = media_path / file_name
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # 返回相对路径，用于存储在Schema中
        relative_path = f"media/{media_type}/{file_name}"
        logger.info(f"保存媒体文件: {file_path}")
        return relative_path
    
    async def save_media_files_batch(self, 
                                     media_items: List[Dict[str, Any]], 
                                     project_id: str, 
                                     document_id: str) -> Dict[str, str]:
        """
        批量保存媒体文件
        
        Args:
            media_items: 媒体文件列表，每个元素包含 {data, name, type}
            project_id: 项目ID
            document_id: 文档ID
            
        Returns:
            文件名到相对路径的映射
        """
        saved_files = {}
        
        for item in media_items:
            file_data = item.get('data')
            file_name = item.get('name') 
            media_type = item.get('type', 'images')
            
            if file_data and file_name:
                relative_path = await self.save_media_file(
                    file_data, file_name, project_id, document_id, media_type
                )
                saved_files[file_name] = relative_path
        
        logger.info(f"批量保存媒体文件完成，共{len(saved_files)}个文件")
        return saved_files
    
    def list_projects(self) -> List[str]:
        """获取所有项目ID列表"""
        projects = []
        for path in self.base_path.iterdir():
            if path.is_dir() and not path.name.startswith('.'):
                projects.append(path.name)
        return sorted(projects)
    
    def list_documents(self, project_id: str) -> List[str]:
        """获取指定项目下的所有文档ID列表"""
        project_path = self.get_project_path(project_id)
        if not project_path.exists():
            return []
        
        documents = []
        for path in project_path.iterdir():
            if path.is_dir() and not path.name.startswith('.'):
                documents.append(path.name)
        return sorted(documents)
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        stats = {
            "total_projects": 0,
            "total_documents": 0,
            "total_size_mb": 0.0,
            "projects": {}
        }
        
        total_size = 0
        for project_path in self.base_path.iterdir():
            if not project_path.is_dir() or project_path.name.startswith('.'):
                continue
                
            project_id = project_path.name
            stats["total_projects"] += 1
            
            documents = self.list_documents(project_id)
            project_size = sum(f.stat().st_size for f in project_path.rglob('*') if f.is_file())
            
            stats["projects"][project_id] = {
                "document_count": len(documents),
                "size_mb": round(project_size / (1024 * 1024), 2),
                "documents": documents
            }
            
            stats["total_documents"] += len(documents)
            total_size += project_size
        
        stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
        return stats
    
    async def cleanup_project(self, project_id: str, confirm: bool = False) -> bool:
        """
        清理指定项目的所有数据
        
        Args:
            project_id: 要清理的项目ID
            confirm: 确认标志，防止误删
            
        Returns:
            是否成功清理
        """
        if not confirm:
            logger.warning(f"项目清理需要确认标志: {project_id}")
            return False
        
        project_path = self.get_project_path(project_id)
        if not project_path.exists():
            logger.warning(f"项目目录不存在: {project_id}")
            return False
        
        try:
            shutil.rmtree(project_path)
            logger.info(f"项目清理完成: {project_id}")
            return True
        except Exception as e:
            logger.error(f"项目清理失败: {project_id}, 错误: {e}")
            return False
    
    def get_document_full_path(self, project_id: str, document_id: str, relative_path: str) -> Path:
        """
        根据相对路径获取文件的完整路径
        
        Args:
            project_id: 项目ID
            document_id: 文档ID
            relative_path: 相对路径（如 "media/images/image1.png"）
            
        Returns:
            完整的文件路径
        """
        doc_path = self.get_document_path(project_id, document_id)
        return doc_path / relative_path 