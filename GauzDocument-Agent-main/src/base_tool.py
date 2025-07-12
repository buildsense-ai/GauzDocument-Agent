#!/usr/bin/env python3
"""
工具基类定义
提供所有工具的基础类，避免循环导入问题
"""

class Tool:
    """工具基类"""
    
    def __init__(self, name: str = "", description: str = ""):
        self.name = name
        self.description = description
    
    def execute(self, **kwargs) -> str:
        """
        执行工具操作的基础方法
        子类需要重写此方法实现具体功能
        """
        raise NotImplementedError("子类必须实现execute方法")
    
    def get_name(self) -> str:
        """获取工具名称"""
        return self.name
    
    def get_description(self) -> str:
        """获取工具描述"""
        return self.description
    
    def __str__(self) -> str:
        return f"Tool({self.name}): {self.description}"
    
    def __repr__(self) -> str:
        return f"Tool(name='{self.name}', description='{self.description[:50]}...')" 