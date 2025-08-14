"""
数据库模型定义
优化设计支持快速加载和Markdown内容
"""

import uuid
import json
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Index, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import LONGTEXT, JSON as MySQL_JSON
from .database import Base

class User(Base):
    """用户账号模型"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255))
    status = Column(String(50), default="active", index=True)  # active/disabled/admin

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Project(Base):
    """项目模型 - 支持快速列表显示"""
    __tablename__ = "projects"
    
    # 基础字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(100), index=True)                    # 项目类型
    description = Column(Text)                                # 项目描述
    
    # 统计字段 - 用于快速显示
    message_count = Column(Integer, default=0)               # 消息总数
    file_count = Column(Integer, default=0)                  # 文件总数
    last_message_preview = Column(String(200))               # 最后消息预览
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow, index=True)  # 最后活跃时间
    
    # 状态字段
    status = Column(String(20), default="active", index=True)  # active/completed/archived
    
    # 关联关系
    sessions = relationship("ChatSession", back_populates="project", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="project", cascade="all, delete-orphan")
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "message_count": self.message_count,
            "file_count": self.file_count,
            "last_message_preview": self.last_message_preview,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "status": self.status
        }

class ChatSession(Base):
    """对话会话模型 - 组织对话历史"""
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    # 会话信息
    title = Column(String(255))                              # 会话标题，自动生成或用户设置
    message_count = Column(Integer, default=0)              # 该会话的消息数量
    
    # 状态字段
    is_current = Column(Boolean, default=True, index=True)   # 是否为当前活跃会话
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_message_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 关联关系
    project = relationship("Project", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "message_count": self.message_count,
            "is_current": self.is_current,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None
        }

class ChatMessage(Base):
    """对话消息模型 - 支持Markdown和思考过程"""
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    # 消息内容
    role = Column(String(20), nullable=False, index=True)    # user/assistant/system
    content = Column(LONGTEXT, nullable=False)               # 原始内容（Markdown）
    content_type = Column(String(20), default="text")       # text/markdown/html
    
    # 渲染内容 - 支持快速显示
    rendered_html = Column(LONGTEXT)                         # 预渲染的HTML
    content_summary = Column(String(500))                    # 内容摘要
    
    # 消息元数据
    has_thinking = Column(Boolean, default=False, index=True) # 是否包含思考过程
    thinking_data = Column(MySQL_JSON)                       # 思考过程数据
    word_count = Column(Integer, default=0)                  # 字数统计
    
    # 序号和时间
    message_index = Column(Integer, nullable=False)          # 会话内消息序号
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 额外数据
    extra_data = Column(MySQL_JSON)                         # 额外的元数据
    
    # 关联关系
    session = relationship("ChatSession", back_populates="messages")
    project = relationship("Project", back_populates="messages")
    
    def to_dict(self, include_content=True):
        """转换为字典，可选择是否包含完整内容"""
        data = {
            "id": self.id,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "role": self.role,
            "content_type": self.content_type,
            "has_thinking": self.has_thinking,
            "word_count": self.word_count,
            "message_index": self.message_index,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "content_summary": self.content_summary
        }
        
        if include_content:
            data.update({
                "content": self.content,
                "rendered_html": self.rendered_html,
                "thinking_data": self.thinking_data,
                "extra_data": self.extra_data
            })
        
        return data

class ProjectFile(Base):
    """项目文件模型 - 支持快速列表和MinIO集成"""
    __tablename__ = "project_files"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), index=True)  # 可选，关联到具体会话
    
    # 文件信息
    original_name = Column(String(255), nullable=False)      # 原始文件名
    display_name = Column(String(255))                       # 显示名称
    file_size = Column(Integer)                              # 文件大小
    file_type = Column(String(100), index=True)             # 文件类型
    mime_type = Column(String(200))                          # MIME类型
    
    # 存储路径
    local_path = Column(String(1000))                        # 本地临时路径
    minio_path = Column(String(1000))                        # MinIO存储路径
    thumbnail_path = Column(String(1000))                    # 缩略图路径
    
    # 文件状态
    status = Column(String(20), default="uploading", index=True)  # uploading/ready/error
    upload_progress = Column(Integer, default=0)            # 上传进度 0-100
    error_message = Column(Text)                             # 错误信息
    
    # 文件元数据
    extra_data = Column(MySQL_JSON)                         # 文件元数据
    
    # 时间字段
    uploaded_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime)                          # 处理完成时间
    
    # 关联关系
    project = relationship("Project", back_populates="files")
    session = relationship("ChatSession")
    
    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "original_name": self.original_name,
            "display_name": self.display_name or self.original_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "mime_type": self.mime_type,
            "local_path": self.local_path,
            "minio_path": self.minio_path,
            "thumbnail_path": self.thumbnail_path,
            "status": self.status,
            "upload_progress": self.upload_progress,
            "error_message": self.error_message,
            "extra_data": self.extra_data,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }

# 创建复合索引以优化查询
Index('idx_messages_project_session_time', ChatMessage.project_id, ChatMessage.session_id, ChatMessage.created_at)
Index('idx_messages_session_index', ChatMessage.session_id, ChatMessage.message_index)
Index('idx_files_project_time', ProjectFile.project_id, ProjectFile.uploaded_at)
Index('idx_sessions_project_active', ChatSession.project_id, ChatSession.last_message_at)
Index('idx_projects_active_time', Project.status, Project.last_active_at) 

class ProjectMember(Base):
    """项目成员模型 - 记录用户在项目中的角色"""
    __tablename__ = "project_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), default="viewer", index=True)  # owner/editor/viewer
    invited_by = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "role": self.role,
            "invited_by": self.invited_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }