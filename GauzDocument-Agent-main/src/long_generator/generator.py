# 文件名: generator2.py
# -*- coding: utf-8 -*-

"""
generator2.py

[已更新] 这是一个高度定制化的版本，使用固定的大纲模板来生成专业的文物影响评估报告。
"""

import json
import os
import time
import uuid
from typing import Dict, Any, Optional, List

import docx
import base64
from io import BytesIO
from docx.shared import Inches, Pt
from docx.oxml.ns import qn

# --- 从其他模块导入依赖 ---
from config import Config
from services import call_ai_model, search_vectordata, get_info, get_summary
from upload_cloud import upload_to_minio
from process_image import get_image_info
from converter import convert_md_to_docx_with_images

# --- 导入prompt加载器 ---
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from prompts.loader import get_prompt_loader


# TaskState 类的代码保持不变
class TaskState:
    """管理单个生成任务的状态，负责JSON文件的读写和更新。"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.filepath = os.path.join(Config.TASKS_DIR, f"task_{self.task_id}.json")
        self.data: Dict[str, Any] = {}
        os.makedirs(Config.TASKS_DIR, exist_ok=True)

    def load(self) -> bool:
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        return False

    def save(self):
        self.data['lastUpdatedTimestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"--- 状态已保存: {self.filepath} ---")

    def initialize(self, initial_request: Dict[str, str], report_type: str):
        # [变更] 增加 report_type 和 docxPublicUrl 字段
        self.data = {
            "taskId": self.task_id, "status": "pending", "progressPercentage": 0,
            "currentStatusMessage": "任务已创建，等待初始化...", "initialRequest": initial_request,
            "reportType": report_type,
            "creativeBrief": "", "projectName": "",
            "introduction": "", "conclusion": "", "outline": {}, "finalDocument": "",
            "markdownPublicUrl": "", "docxPublicUrl": "", "errorLog": []
        }
        self.save()

    def update_status(self, status: str, message: str, progress: int):
        self.data['status'] = status
        self.data['currentStatusMessage'] = message
        self.data['progressPercentage'] = progress
        self.save()
        print(f"--- 进度更新: {progress}% - {message} ---")

    def log_error(self, stage: str, error_message: str):
        self.data['errorLog'].append({
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "stage": stage, "message": error_message
        })
        self.update_status("failed", f"在 {stage} 阶段发生错误。", self.data.get('progressPercentage', 0))


class LongDocumentGenerator:
    """负责执行整个长文生成任务的业务流程。"""

    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or str(uuid.uuid4())
        self.state = TaskState(self.task_id)

    def start_new_job(self, chathistory: str, request: str, report_type: str = 'long') -> str:
        """
        [已更新] 启动一个新任务，可以指定报告类型。
        """
        print(f"启动新任务: {self.task_id} (类型: {report_type})")
        self.state.initialize(initial_request={"chathistory": chathistory, "request": request}, report_type=report_type)
        self.run()
        return self.task_id

    def run(self):
        """
        [已更新] 主运行函数，现在会根据报告类型选择不同的工作流。
        """
        try:
            if not self.state.load():
                print(f"错误：无法加载任务 {self.task_id}。")
                return

            report_type = self.state.data.get('reportType', 'long')

            if report_type == 'short':
                self._run_short_report_workflow()
            else: # 默认为长报告流程
                self._run_long_report_workflow()

        except Exception as e:
            error_stage = self.state.data.get('status', 'unknown')
            print(f"!! 在 {error_stage} 阶段发生严重错误: {e}")
            self.state.log_error(error_stage, str(e))
            self.state.update_status("failed", "任务因意外错误而终止。", self.state.data.get('progressPercentage', 0))

    def _run_long_report_workflow(self):
        """[已更新] 执行高度定制化的长篇报告工作流，使用固定大纲。"""
        while self.state.data['status'] not in ['completed', 'failed']:
            current_status = self.state.data['status']
            if current_status == 'pending':
                self._prepare_creative_brief()
            elif current_status == 'brief_prepared':
                # [新增] 直接设置固定大纲，跳过AI生成和评审
                self._set_hardcoded_outline()
            elif current_status == 'outline_finalized':
                self._generate_all_chapters()
            elif current_status == 'chapters_generated':
                self._assemble_final_document()
            else:
                break 

        if self.state.data['status'] == 'completed':
            print(f"\n长篇报告任务 {self.task_id} 已成功完成！")

    def _run_short_report_workflow(self):
        """[新增] 执行精简的短篇报告生成工作流。"""
        while self.state.data['status'] not in ['completed', 'failed']:
            current_status = self.state.data['status']
            if current_status == 'pending':
                self._prepare_creative_brief()
            elif current_status == 'brief_prepared':
                self._generate_short_report_content()
            elif current_status == 'short_report_generated':
                # 短报告直接进入最终文件生成环节
                self._assemble_final_document(is_short_report=True)
            else:
                break

        if self.state.data['status'] == 'completed':
            print(f"\n短篇报告任务 {self.task_id} 已成功完成！")

    def _generate_short_report_content(self):
        """[新增] 为短报告直接生成全文内容。"""
        self.state.update_status("short_report_generation", "正在生成短篇报告内容...", 20)

        project_name = self.state.data.get('projectName', '')
        creative_brief = self.state.data.get('creativeBrief', '')

        print("--> 为短报告进行知识检索...")
        knowledge_pieces = search_vectordata(query=project_name, top_k=Config.SEARCH_DEFAULT_TOP_K)
        knowledge_context = ""
        if knowledge_pieces:
            knowledge_str = "\n\n---\n\n".join(knowledge_pieces)
            knowledge_context = f"\n请参考以下背景资料进行撰写：\n{knowledge_str}\n"

        try:
            # 使用prompt模板
            prompt_loader = get_prompt_loader()
            prompt_template = prompt_loader.get_prompt("document_generation", "short_report_generation_prompt")
            prompt = prompt_template.format(
                creative_brief=creative_brief,
                knowledge_context=knowledge_context
            )
        except Exception as e:
            # 如果加载失败，使用备用prompt
            print(f"警告：加载prompt模板失败，使用备用prompt: {e}")
            prompt = f"""你是一位专业的报告撰写人。请根据以下项目简介和背景资料，撰写一篇结构完整、内容流畅的通用短文或报告，总字数控制在2000字以内。
文章应有逻辑地分为几个部分，并使用Markdown的二级标题（##）来标记每个部分的标题。

【项目简介】
{creative_brief}

{knowledge_context}

请直接输出完整的Markdown格式报告全文。
"""
        response = call_ai_model(prompt)
        self.state.data['finalDocument'] = response.get('text', '')
        self.state.data['status'] = 'short_report_generated'
        self.state.save()

    def _prepare_creative_brief(self):
        """[已优化] 阶段1: 准备创作指令, 并提取核心项目主题"""
        self.state.update_status("brief_generation", "正在分析聊天记录和用户请求...", 5)
        chathistory = self.state.data['initialRequest']['chathistory']
        request = self.state.data['initialRequest']['request']

        # 注释：这里的Prompt也调整为文物评估的视角。
        try:
            prompt_loader = get_prompt_loader()
            prompt_template = prompt_loader.get_prompt("document_generation", "creative_brief_analysis_prompt")
            prompt_brief = prompt_template.format(
                chathistory=chathistory,
                request=request
            )
        except Exception as e:
            print(f"警告：加载prompt模板失败，使用备用prompt: {e}")
            prompt_brief = f"""你是一位资深的文物影响评估专家。请根据下面的对话记录和最终请求，为即将撰写的《文物影响评估报告》提炼一份核心的"创作指令"（Creative Brief）。
这份指令需要明确评估对象、项目性质和核心的评估要求。
【对话记录】
{chathistory}
【最终请求】
{request}
请以JSON格式返回你的分析结果，包含一个'creative_brief'字段。
重要提示：所有生成的文本内容都必须使用中文。
"""
        response_brief = call_ai_model(prompt_brief, expect_json=True)
        brief = response_brief.get("creative_brief")
        if not brief:
            raise ValueError("AI未能生成有效的创作指令（creative_brief）。")
        self.state.data['creativeBrief'] = brief

        self.state.update_status("brief_generation", "正在提炼项目主题以优化检索...", 7)
        try:
            prompt_loader = get_prompt_loader()
            prompt_template = prompt_loader.get_prompt("document_generation", "project_name_extraction_prompt")
            prompt_project_name = prompt_template.format(brief=brief)
        except Exception as e:
            print(f"警告：加载prompt模板失败，使用备用prompt: {e}")
            prompt_project_name = f"""从以下创作指令中，提取一个简短的核心项目名称或主题（例如，"xx路社文体中心建设项目"或"医灵古庙修缮工程"），用于优化后续的知识库检索。
请以JSON格式返回，只包含一个 'project_name' 字段。
重要提示：项目名称必须使用中文。
创作指令：{brief}
"""
        response_name = call_ai_model(prompt_project_name, expect_json=True)
        project_name = response_name.get("project_name", "")
        self.state.data['projectName'] = project_name
        print(f"--- 提炼出项目主题: {project_name} ---")

        self.state.data['status'] = 'brief_prepared'
        self.state.save()

    def _get_hardcoded_outline(self) -> List[Dict[str, Any]]:
        """[新增] 返回一个固定的、专业的文物影响评估报告大纲。"""
        print("--- 正在加载固定大纲模板... ---")
        return [
            {"chapterId": "ch_01", "title": "项目概况", "key_points": ["编制背景", "评估内容和范围", "项目编制依据", "评估目的", "评估原则和思想"]},
            {"chapterId": "ch_02", "title": "建设项目涉及文物情况", "key_points": ["文物概况", "历史沿革", "价值评估", "现状情况"]},
            {"chapterId": "ch_03", "title": "项目建设必要性", "key_points": []},
            {"chapterId": "ch_04", "title": "项目建设概况", "key_points": []},
            {"chapterId": "ch_05", "title": "支撑法律，法规及文件等", "key_points": []},
            {"chapterId": "ch_06", "title": "项目对文物影响评估", "key_points": ["对文物本体安全影响评估", "对文物保护范围内影响评估", "对文物建筑历史景观风貌影响评估", "对文物施工期影响评估"]},
            {"chapterId": "ch_07", "title": "项目监测方案", "key_points": []},
            {"chapterId": "ch_08", "title": "应急方案", "key_points": []},
            {"chapterId": "ch_09", "title": "结论及建议", "key_points": ["评估结论", "要求与建议"]},
        ]

    def _set_hardcoded_outline(self):
        """[新增] 将固定的模板大纲设置到任务状态中。"""
        self.state.update_status("outline_generation", "正在设置固定大纲...", 10)
        chapters = self._get_hardcoded_outline()
        self.state.data['outline'] = {"metadata": {"refinementCycles": 0}, "chapters": chapters}
        self.state.data['status'] = 'outline_finalized' # 直接标记为最终版
        self.state.save()

    def _generate_all_chapters(self):
        """
        [已更新] 阶段4: 为特定章节调用知识库并交由AI润色，其他章节由AI创作。
        """
        chapters = self.state.data['outline']['chapters']
        project_name = self.state.data.get('projectName', '')
        total_chapters = len(chapters)
        if total_chapters == 0:
            print("!! 警告：大纲为空，无法生成任何章节内容。")
            self.state.data['status'] = 'chapters_generated'
            self.state.save()
            return

        for i, chapter in enumerate(chapters):
            progress = 30 + int((i / total_chapters) * 60)
            chapter_title = chapter.get('title', '')
            self.state.update_status("content_generation", f"正在生成第 {i + 1}/{total_chapters} 章: '{chapter_title}'...",
                                     progress)

            # --- [已更新] 逻辑分叉：判断是否为特殊章节 ---
            if chapter_title in ["建设项目涉及文物情况", "项目对文物影响评估"]:
                print(f"--> 检测到特殊章节 '{chapter_title}'，从知识库获取原始数据并交由AI润色。")
                scoped_query = f"{project_name} {chapter_title}".strip()
                knowledge_pieces = search_vectordata(query=scoped_query, top_k=Config.SEARCH_DEFAULT_TOP_K)

                if not knowledge_pieces:
                    chapter['content'] = "根据现有资料，暂未找到关于本章节的详细信息。"
                else:
                    raw_info = "\n\n---\n\n".join(knowledge_pieces)
                    rewrite_prompt = f"""你是一位经验丰富的文物影响评估专家。
这里有一份关于“{chapter_title}”的原始资料。请你严格依据这些资料，并遵循所有专业报告的写作规范（客观语气、专业术语、标准格式等），将其改写和组织成一段格式严谨、文笔流畅的正式评估报告章节。

【原始资料】
{raw_info}

请直接输出改写后的正文内容，不要添加任何额外的解释或标题。
"""
                    response = call_ai_model(rewrite_prompt)
                    chapter['content'] = response.get('text', '')

            else:
                # --- 对于所有其他章节，执行标准的AI生成流程 ---
                print(f"--> 为章节 '{chapter_title}' 检索文本知识...")
                scoped_query = f"{project_name} {chapter_title}".strip()
                knowledge_pieces = search_vectordata(query=scoped_query, top_k=Config.SEARCH_DEFAULT_TOP_K)

                clean_outline_for_context = [
                    {"title": ch.get("title"), "key_points": ch.get("key_points")} 
                    for ch in chapters
                ]
                base_context = f"这是全文大纲的结构：{json.dumps(clean_outline_for_context, ensure_ascii=False)}\n"

                if i == 0:
                    print("--> 检测到为第一章，调用get_summary()获取开篇总结...")
                    initial_summary = get_summary()
                    if initial_summary:
                        base_context += f"\n请基于以下核心总结，为整个报告撰写一个强有力的开篇：\n“{initial_summary}”\n"
                else: 
                    previous_summary = chapters[i - 1].get('summary', '')
                    if previous_summary:
                        base_context += f"\n请注意：上一章的核心内容总结为：“{previous_summary}”。请确保本章的开头能与此形成自然过渡。\n"
                    else:
                        base_context += f"前一章是关于 '{chapters[i - 1].get('title', '')}' 的。\n"

                if knowledge_pieces:
                    knowledge_str = "\n\n---\n\n".join(knowledge_pieces)
                    base_context += f"\n在撰写本章时，请重点参考以下背景资料以确保内容的准确性和深度：{knowledge_str}\n"

                prompt = f"""你是一位经验丰富的文物影响评估专家...（省略以保持简洁）...
请直接输出“{chapter_title}”这一章节的正文内容，不要在开头重复章节标题。
"""
                response = call_ai_model(prompt, context=base_context)
                chapter['content'] = response.get('text', '')

            # --- 为所有章节都生成摘要，以确保连贯性 ---
            print(f"--> 正在为章节 '{chapter_title}' 生成摘要...")
            if chapter.get('content'):
                summary_prompt = f"请将以下文本内容总结成一到两句精炼的核心观点，用于章节间的承上启下。\n\n文本：\n{chapter['content']}"
                summary_response = call_ai_model(summary_prompt)
                chapter['summary'] = summary_response.get('text', '')
            else:
                chapter['summary'] = f"本章节（{chapter_title}）内容为空。"
            # --- 摘要生成结束 ---

            # --- 图片URL检索（对所有章节都执行） ---
            print(f"--> 为章节 '{chapter_title}' 检索图片链接...")
            image_query = f"{project_name} {chapter_title}".strip()
            image_urls = get_image_info(query=image_query)
            if image_urls:
                chapter['image_urls'] = image_urls
                print(f"--- 检索到 {len(image_urls)} 个图片链接 ---")
            else:
                print("!! [警告] 未能检索到相关图片链接。")

            self.state.save()

        self.state.data['status'] = 'chapters_generated'
        self.state.save()

    def _assemble_final_document(self, is_short_report: bool = False):
        """
        [已更新] 最终文件整合与生成，会根据报告类型进行适配。
        """
        if is_short_report:
            self.state.update_status("assembling", "正在准备短报告文件...", 95)
        else:
            self.state.update_status("assembling", "所有章节已生成，正在整合文档...", 95)
            chapters = self.state.data['outline']['chapters']
            clean_outline_for_context = [
                {"title": ch.get("title"), "key_points": ch.get("key_points")} 
                for ch in chapters
            ]
            final_context_str = json.dumps(clean_outline_for_context, ensure_ascii=False)

            if not chapters:
                print("!! 警告：大纲为空，将生成通用的引言和结论。")

            intro_prompt = """你是一位经验丰富的文物影响评估专家...（省略）..."""
            intro_response = call_ai_model(intro_prompt, context=final_context_str)
            introduction_text = intro_response.get('text', '')
            self.state.data['introduction'] = introduction_text

            conclusion_prompt = """你是一位经验丰富的文物影响评估专家...（省略）..."""
            conclusion_response = call_ai_model(conclusion_prompt, context=final_context_str)
            conclusion_text = conclusion_response.get('text', '')
            self.state.data['conclusion'] = conclusion_text

            full_text_parts = [f"## 引言\n\n{introduction_text}"]
            for chapter in chapters:
                full_text_parts.append(f"\n\n## {chapter.get('title', '')}\n\n")
                full_text_parts.append(chapter.get('content', ''))
                image_urls = chapter.get('image_urls', [])
                for url in image_urls:
                    full_text_parts.append(f"\n\n![{chapter.get('title', '章节配图')}]({url})\n")
            full_text_parts.append(f"\n\n## 结论与建议\n\n")
            full_text_parts.append(conclusion_text)

            self.state.data['finalDocument'] = "".join(full_text_parts)

        try:
            self._create_and_upload_markdown()
        except Exception as e:
            print(f"!! [警告] 创建或上传 .md 文件时发生错误: {e}")
            self.state.log_error("markdown_handling", str(e))

        try:
            self._convert_and_upload_docx()
        except Exception as e:
            print(f"!! [警告] 将Markdown转换为Docx或上传时发生错误: {e}")
            self.state.log_error("docx_conversion", str(e))

        self.state.update_status("completed", "文档已成功生成！", 100)

    def _create_and_upload_markdown(self):
        """
        生成并上传Markdown文档。
        """
        print("--- 正在生成 .md 文档... ---")
        final_text = self.state.data.get('finalDocument', '')
        if not final_text:
            print("!! [警告] finalDocument 为空，无法生成 .md 文件。")
            return None

        markdown_filename = f"task_{self.state.task_id}.md"
        markdown_filepath = os.path.join(Config.TASKS_DIR, markdown_filename)

        try:
            with open(markdown_filepath, 'w', encoding='utf-8') as f:
                f.write(final_text)
            print(f"--- .md 文档已成功保存至本地: {markdown_filepath} ---")
        except Exception as e:
            print(f"!! [错误] 写入 .md 文件时发生错误: {e}")
            return None

        public_url = upload_to_minio(
            file_path=markdown_filepath,
            object_name=markdown_filename
        )
        if public_url:
            self.state.data['markdownPublicUrl'] = public_url
            self.state.save()

        return markdown_filepath

    def _convert_and_upload_docx(self):
        """
        [新增] 将已生成的Markdown文件转换为Docx并上传。
        """
        print("--- 开始执行 Markdown 到 Docx 的转换流程 ---")
        markdown_filename = f"task_{self.state.task_id}.md"
        markdown_filepath = os.path.join(Config.TASKS_DIR, markdown_filename)

        if not os.path.exists(markdown_filepath):
            print(f"!! [错误] 找不到Markdown源文件: {markdown_filepath}，跳过Docx转换。")
            return

        docx_filename = f"task_{self.state.task_id}.docx"
        docx_filepath = os.path.join(Config.TASKS_DIR, docx_filename)

        # 调用转换器
        result_path = convert_md_to_docx_with_images(
            md_filepath=markdown_filepath,
            output_docx_path=docx_filepath
        )

        # 如果转换成功，则上传
        if result_path:
            public_url = upload_to_minio(
                file_path=result_path,
                object_name=docx_filename
            )
            if public_url:
                self.state.data['docxPublicUrl'] = public_url
                self.state.save()

    def _create_and_upload_docx(self):
        """
        [已弃用] 此函数原用于生成 .docx 文件，现已被 _create_and_upload_markdown 替代。
        保留此函数结构仅为历史参考。
        """
        pass