"""
数据库CRUD操作
支持快速加载、分页和Markdown内容处理
"""

import uuid
import markdown
import bleach
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func, and_, or_
from . import models
from .account_models import AccountUser
import logging
import re

logger = logging.getLogger(__name__)

# ======================== 账户相关操作 ========================

def create_user(db: Session, username: str, password_hash: str, email: Optional[str] = None) -> AccountUser:
    user = AccountUser(username=username, password_hash=password_hash, email=email, status="active")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_username(db: Session, username: str) -> Optional[AccountUser]:
    return db.query(AccountUser).filter(AccountUser.username == username).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[AccountUser]:
    return db.query(AccountUser).filter(AccountUser.id == user_id).first()

# ======================== 项目成员相关操作 ========================

def add_project_member(db: Session, project_id: str, user_id: str, role: str, invited_by: Optional[str] = None) -> models.ProjectMember:
    member = models.ProjectMember(project_id=project_id, user_id=user_id, role=role, invited_by=invited_by)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member

def get_project_member(db: Session, project_id: str, user_id: str) -> Optional[models.ProjectMember]:
    return db.query(models.ProjectMember).filter(
        and_(models.ProjectMember.project_id == project_id, models.ProjectMember.user_id == user_id)
    ).first()

def list_project_members(db: Session, project_id: str) -> List[models.ProjectMember]:
    return db.query(models.ProjectMember).filter(models.ProjectMember.project_id == project_id).order_by(models.ProjectMember.created_at.asc()).all()

def update_project_member_role(db: Session, project_id: str, user_id: str, role: str) -> bool:
    member = get_project_member(db, project_id, user_id)
    if not member:
        return False
    member.role = role
    db.commit()
    return True

def remove_project_member(db: Session, project_id: str, user_id: str) -> bool:
    member = get_project_member(db, project_id, user_id)
    if not member:
        return False
    db.delete(member)
    db.commit()
    return True

# ======================== 项目相关操作 ========================

def create_project(db: Session, name: str, project_type: str = None, description: str = None) -> models.Project:
    """创建新项目"""
    project = models.Project(
        name=name,
        type=project_type,
        description=description,
        status="active"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # 创建默认会话
    create_default_session(db, project.id)
    
    logger.info(f"✅ 创建项目成功: {name} ({project.id})")
    return project

def get_project(db: Session, project_id: str = None, project_name: str = None) -> Optional[models.Project]:
    """获取单个项目 - 支持按ID或名称查询"""
    query = db.query(models.Project)
    if project_id:
        return query.filter(models.Project.id == project_id).first()
    elif project_name:
        return query.filter(models.Project.name == project_name).first()
    else:
        return None

def get_project_by_name(db: Session, project_name: str) -> Optional[models.Project]:
    """按项目名称获取项目"""
    return db.query(models.Project).filter(models.Project.name == project_name).first()

def get_all_projects(db: Session, status: str = None) -> List[models.Project]:
    """获取所有项目，按最后活跃时间排序"""
    query = db.query(models.Project)
    if status:
        query = query.filter(models.Project.status == status)
    return query.order_by(desc(models.Project.last_active_at)).all()

def get_project_summary(db: Session, project_id: str = None, project_name: str = None) -> Optional[Dict[str, Any]]:
    """获取项目概要信息 - 用于快速加载，支持按ID或名称查询"""
    # 🆕 支持按项目名称或ID查询
    project = get_project(db, project_id=project_id, project_name=project_name)
    if not project:
        return None
    
    # 使用项目ID进行后续查询（保证性能）
    actual_project_id = project.id
    
    # 获取最近的会话
    recent_sessions = db.query(models.ChatSession)\
        .filter(models.ChatSession.project_id == actual_project_id)\
        .order_by(desc(models.ChatSession.last_message_at))\
        .limit(3).all()
    
    # 获取当前活跃会话
    current_session = db.query(models.ChatSession)\
        .filter(and_(
            models.ChatSession.project_id == actual_project_id,
            models.ChatSession.is_current == True
        )).first()
    
    return {
        "project": project.to_dict(),
        "stats": {
            "message_count": project.message_count,
            "file_count": project.file_count,
            "session_count": len(recent_sessions)
        },
        "recent_sessions": [session.to_dict() for session in recent_sessions],
        "current_session_id": current_session.id if current_session else None
    }

def update_project_stats(db: Session, project_id: str):
    """更新项目统计信息"""
    project = get_project(db, project_id)
    if not project:
        return
    
    # 计算消息数量
    message_count = db.query(func.count(models.ChatMessage.id))\
        .filter(models.ChatMessage.project_id == project_id).scalar()
    
    # 计算文件数量
    file_count = db.query(func.count(models.ProjectFile.id))\
        .filter(models.ProjectFile.project_id == project_id).scalar()
    
    # 获取最后一条消息预览
    last_message = db.query(models.ChatMessage)\
        .filter(models.ChatMessage.project_id == project_id)\
        .order_by(desc(models.ChatMessage.created_at))\
        .first()
    
    # 更新统计
    project.message_count = message_count or 0
    project.file_count = file_count or 0
    project.last_message_preview = last_message.content_summary[:200] if last_message else None
    project.last_active_at = datetime.utcnow()
    
    db.commit()
    logger.info(f"🔄 更新项目统计: {project.name} - {message_count}条消息, {file_count}个文件")

def delete_project(db: Session, project_id: str) -> bool:
    """删除项目（硬删除）- 删除项目及所有相关数据"""
    project = get_project(db, project_id)
    if not project:
        return False
    
    project_name = project.name
    
    try:
        # 由于设置了cascade="all, delete-orphan"，删除项目会自动删除相关的会话、消息和文件
        db.delete(project)
        db.commit()
        logger.info(f"🗑️ 已删除项目及所有相关数据: {project_name}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 删除项目失败: {project_name} - {e}")
        return False

# ======================== 会话相关操作 ========================

def create_default_session(db: Session, project_id: str) -> models.ChatSession:
    """为项目创建默认会话"""
    session = models.ChatSession(
        project_id=project_id,
        title="新对话",
        is_current=True
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_current_session(db: Session, project_id: str = None, project_name: str = None) -> Optional[models.ChatSession]:
    """获取项目的当前活跃会话 - 支持按ID或名称查询"""
    # 🆕 如果提供project_name，先获取project_id
    if project_name and not project_id:
        project = get_project_by_name(db, project_name)
        if not project:
            return None
        project_id = project.id
    
    return db.query(models.ChatSession)\
        .filter(and_(
            models.ChatSession.project_id == project_id,
            models.ChatSession.is_current == True
        )).first()

def create_new_session(db: Session, project_id: str = None, project_name: str = None, title: str = None) -> models.ChatSession:
    """创建新会话并设为当前会话 - 支持按ID或名称"""
    # 🆕 如果提供project_name，先获取project_id
    if project_name and not project_id:
        project = get_project_by_name(db, project_name)
        if not project:
            raise ValueError(f"项目不存在: {project_name}")
        project_id = project.id
    
    # 将其他会话设为非当前
    db.query(models.ChatSession)\
        .filter(models.ChatSession.project_id == project_id)\
        .update({"is_current": False})
    
    # 创建新会话
    session = models.ChatSession(
        project_id=project_id,
        title=title or f"对话 {datetime.now().strftime('%m-%d %H:%M')}",
        is_current=True
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_project_sessions(db: Session, project_id: str) -> List[models.ChatSession]:
    """获取项目的所有会话"""
    return db.query(models.ChatSession)\
        .filter(models.ChatSession.project_id == project_id)\
        .order_by(desc(models.ChatSession.last_message_at)).all()

# ======================== 消息相关操作 ========================

def render_markdown_content(content: str) -> Tuple[str, str]:
    """渲染Markdown内容"""
    try:
        # 配置markdown扩展
        md = markdown.Markdown(extensions=[
            'markdown.extensions.fenced_code',
            'markdown.extensions.tables',
            'markdown.extensions.toc',
            'markdown.extensions.nl2br'
        ])
        
        # 渲染HTML
        html = md.convert(content)
        
        # 清理HTML，防止XSS
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'table', 'thead', 'tbody',
            'tr', 'td', 'th', 'a', 'img', 'div', 'span'
        ]
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title'],
            'code': ['class'],
            'pre': ['class']
        }
        
        clean_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attributes)
        
        # 生成摘要（去除HTML标签）
        text_content = bleach.clean(html, tags=[], strip=True)
        summary = text_content[:300] + "..." if len(text_content) > 300 else text_content
        
        return clean_html, summary
    except Exception as e:
        logger.error(f"Markdown渲染失败: {e}")
        return content, content[:300]

def save_message(db: Session, project_id: str, session_id: str, role: str, content: str, 
                thinking_data: Dict = None, extra_data: Dict = None) -> models.ChatMessage:
    """保存对话消息"""
    # 获取会话内消息序号
    message_count = db.query(func.count(models.ChatMessage.id))\
        .filter(models.ChatMessage.session_id == session_id).scalar()
    
    # 处理内容
    content_type = "markdown" if role == "assistant" else "text"
    rendered_html = None
    content_summary = content[:200]
    
    if content_type == "markdown":
        rendered_html, content_summary = render_markdown_content(content)
    
    # 创建消息
    message = models.ChatMessage(
        session_id=session_id,
        project_id=project_id,
        role=role,
        content=content,
        content_type=content_type,
        rendered_html=rendered_html,
        content_summary=content_summary,
        has_thinking=bool(thinking_data),
        thinking_data=thinking_data,
        word_count=len(content),
        message_index=message_count + 1,
        extra_data=extra_data
    )
    
    db.add(message)
    
    # 更新会话统计
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if session:
        session.message_count = message_count + 1
        session.last_message_at = datetime.utcnow()
        
        # 自动生成会话标题
        if session.message_count <= 2 and role == "user":
            session.title = content[:50] + "..." if len(content) > 50 else content
    
    db.commit()
    db.refresh(message)
    
    # 异步更新项目统计
    update_project_stats(db, project_id)
    
    logger.info(f"💬 保存消息: {role} - {len(content)}字符")
    return message

def get_session_messages(db: Session, session_id: str, page: int = 1, limit: int = 50, 
                        include_content: bool = True) -> Tuple[List[models.ChatMessage], int]:
    """获取会话消息（分页）- 修复：按时间倒序获取最新消息"""
    # 🆕 修复：改为按创建时间降序排列，获取最新的消息
    query = db.query(models.ChatMessage)\
        .filter(models.ChatMessage.session_id == session_id)\
        .order_by(desc(models.ChatMessage.created_at))
    
    # 计算总数
    total = query.count()
    
    # 分页
    offset = (page - 1) * limit
    messages = query.offset(offset).limit(limit).all()
    
    # 🆕 不在后端reverse，让前端处理顺序
    # 直接返回按时间降序的消息列表（最新的在前面）
    
    return messages, total

def get_recent_messages(db: Session, project_id: str, limit: int = 10) -> List[models.ChatMessage]:
    """获取项目最近的消息"""
    return db.query(models.ChatMessage)\
        .filter(models.ChatMessage.project_id == project_id)\
        .order_by(desc(models.ChatMessage.created_at))\
        .limit(limit).all()

def search_messages(db: Session, project_id: str, query: str, limit: int = 20) -> List[models.ChatMessage]:
    """搜索项目内的消息"""
    return db.query(models.ChatMessage)\
        .filter(and_(
            models.ChatMessage.project_id == project_id,
            or_(
                models.ChatMessage.content.contains(query),
                models.ChatMessage.content_summary.contains(query)
            )
        ))\
        .order_by(desc(models.ChatMessage.created_at))\
        .limit(limit).all()

# ======================== 文件相关操作 ========================

def save_file_record(db: Session, project_id: str, session_id: str, original_name: str,
                    local_path: str, minio_path: str = None, file_size: int = None,
                    mime_type: str = None, extra_data: Dict = None) -> models.ProjectFile:
    """保存文件记录"""
    file_record = models.ProjectFile(
        project_id=project_id,
        session_id=session_id,
        original_name=original_name,
        local_path=local_path,
        minio_path=minio_path,
        file_size=file_size,
        mime_type=mime_type,
        status="ready" if minio_path else "uploading",
        upload_progress=100 if minio_path else 0,
        extra_data=extra_data
    )
    
    db.add(file_record)
    db.commit()
    db.refresh(file_record)
    
    # 更新项目统计
    update_project_stats(db, project_id)
    
    logger.info(f"📁 保存文件记录: {original_name}")
    return file_record

def get_project_files(db: Session, project_id: str = None, project_name: str = None, session_id: str = None) -> List[models.ProjectFile]:
    """获取项目文件列表 - 支持按ID或名称查询"""
    # 🆕 如果提供project_name，先获取project_id
    if project_name and not project_id:
        project = get_project_by_name(db, project_name)
        if not project:
            return []
        project_id = project.id
    
    query = db.query(models.ProjectFile)\
        .filter(models.ProjectFile.project_id == project_id)
    
    if session_id:
        query = query.filter(models.ProjectFile.session_id == session_id)
    
    return query.order_by(desc(models.ProjectFile.uploaded_at)).all()

def update_file_minio_path(db: Session, file_id: str, minio_path: str) -> bool:
    """更新文件的MinIO路径"""
    file_record = db.query(models.ProjectFile).filter(models.ProjectFile.id == file_id).first()
    if not file_record:
        return False
    
    file_record.minio_path = minio_path
    file_record.status = "ready"
    file_record.upload_progress = 100
    file_record.processed_at = datetime.utcnow()
    
    db.commit()
    return True

# ======================== 数据初始化 ========================

def create_test_project(db: Session) -> models.Project:
    """创建测试项目"""
    existing = db.query(models.Project).filter(models.Project.name == "测试项目").first()
    if existing:
        return existing
    
    return create_project(
        db=db,
        name="测试项目",
        project_type="测试",
        description="这是一个用于测试的默认项目，您可以在这里体验各种功能。"
    )

def init_default_data(db: Session):
    """初始化默认数据"""
    try:
        # 创建测试项目
        test_project = create_test_project(db)
        logger.info(f"✅ 初始化默认数据完成: 测试项目 ({test_project.id})")
        return test_project
    except Exception as e:
        logger.error(f"❌ 初始化默认数据失败: {e}")
        return None 