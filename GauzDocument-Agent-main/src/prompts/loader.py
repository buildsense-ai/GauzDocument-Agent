import yaml
import os
from typing import Dict, Any
from pathlib import Path

class PromptLoader:
    """Prompt加载器 - 统一管理所有prompt模板"""
    
    def __init__(self, prompts_dir: str = None):
        if prompts_dir is None:
            # 默认使用相对于当前文件的prompts目录
            current_dir = Path(__file__).parent
            self.prompts_dir = current_dir
        else:
            self.prompts_dir = Path(prompts_dir)
        
        self._cache = {}
        self._ensure_prompts_dir()
    
    def _ensure_prompts_dir(self):
        """确保prompts目录存在"""
        if not self.prompts_dir.exists():
            raise FileNotFoundError(f"Prompts目录不存在: {self.prompts_dir}")
    
    def get_prompt(self, category: str, prompt_name: str) -> str:
        """
        获取指定的prompt
        
        Args:
            category: 分类名称 (system, document_generation, rag, pdf_processing)
            prompt_name: prompt名称
            
        Returns:
            str: prompt内容
        """
        cache_key = f"{category}.{prompt_name}"
        
        if cache_key not in self._cache:
            self._load_category_if_needed(category)
        
        category_data = self._cache.get(category, {})
        prompt_content = category_data.get(prompt_name, "")
        
        if not prompt_content:
            raise ValueError(f"未找到prompt: {category}.{prompt_name}")
        
        return prompt_content
    
    def get_category_prompts(self, category: str) -> Dict[str, str]:
        """
        获取整个分类的所有prompt
        
        Args:
            category: 分类名称
            
        Returns:
            Dict[str, str]: 该分类下的所有prompt
        """
        if category not in self._cache:
            self._load_category_if_needed(category)
        
        return self._cache.get(category, {})
    
    def _load_category_if_needed(self, category: str):
        """按需加载指定分类的prompt"""
        if category in self._cache:
            return
        
        # 支持的分类和对应的文件
        category_files = {
            'system': ['react_agent.yaml', 'system_functions.yaml'],
            'document_generation': ['brief_analysis.yaml', 'chapter_generation.yaml', 'intro_conclusion.yaml', 'short_report.yaml'],
            'rag': ['field_filling.yaml', 'image_description.yaml'],
            'pdf_processing': ['table_analysis.yaml', 'image_analysis.yaml', 'content_reorganization.yaml']
        }
        
        if category not in category_files:
            raise ValueError(f"不支持的分类: {category}")
        
        # 加载该分类下的所有文件
        category_data = {}
        category_dir = self.prompts_dir / category
        
        for file_name in category_files[category]:
            file_path = category_dir / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = yaml.safe_load(f)
                        if isinstance(file_data, dict):
                            category_data.update(file_data)
                except Exception as e:
                    print(f"警告：加载prompt文件失败 {file_path}: {e}")
        
        self._cache[category] = category_data
    
    def reload_category(self, category: str):
        """重新加载指定分类的prompt（用于开发时热更新）"""
        if category in self._cache:
            del self._cache[category]
        self._load_category_if_needed(category)
    
    def list_available_prompts(self) -> Dict[str, list]:
        """列出所有可用的prompt"""
        result = {}
        for category in ['system', 'document_generation', 'rag', 'pdf_processing']:
            try:
                category_prompts = self.get_category_prompts(category)
                result[category] = list(category_prompts.keys())
            except Exception as e:
                result[category] = f"加载失败: {e}"
        return result


# 全局单例实例
_prompt_loader = None

def get_prompt_loader() -> PromptLoader:
    """获取全局PromptLoader实例"""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader

def get_prompt(category: str, prompt_name: str) -> str:
    """便捷函数：获取prompt"""
    return get_prompt_loader().get_prompt(category, prompt_name) 