from .enhanced_openai import EnhancedOpenAI
import time
import os
import yaml
from typing import Dict, Any
import re
from typing import Optional
from docx import Document
from PyPDF2 import PdfReader
from dotenv import load_dotenv


class ResumeAnalyzer:
    def __init__(self):
        load_dotenv()
        self.ai = None
        try:
            base_url = os.getenv("OPENAI_BASE_URL")
            api_key = os.getenv("OPENAI_KEY")
            self.set_ai_config(base_url, api_key)
        except Exception as e:
            raise ValueError(f"AI初始化失败，请调用set_ai_config方法设置: {str(e)}")
        

    def set_ai_config(self, base_url, api_key, model_name="gpt-4o"):
        self.ai = EnhancedOpenAI(model_name, base_url, api_key)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "config", "config.yaml")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        self.config = self._load_yaml_config(config_path)
        self.prompts = self.config["prompts"]
    
    def _load_yaml_config(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML格式错误: {str(e)}")
        
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF文件中提取文本"""
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

    def _extract_text_from_docx(self, file_path: str) -> str:
        """从Word文档中提取文本"""
        doc = Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])


    def _remove_sensitive_info(self, text: str) -> str:
        """移除敏感信息（电话、手机、邮箱、微信等）"""
        patterns = {
            # 电话/手机号
            'phone': r'(?:电话|手机|联系方式|tel|phone|mobile|[电话\s:：])+\s*(?:\+?86)?\s*1[3-9][\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d',
            
            # 邮箱
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            
            # 微信号（字母、数字、-、_的组合，6-20位）
            'wechat': r'(?:微信|WeChat|wx|wechat|vx)[:：]?\s*[a-zA-Z0-9_-]{6,20}',
            
            # QQ号（5-11位数字）
            'qq': r'(?:QQ|qq)[:：]?\s*[1-9][0-9]{4,10}',
              
            # 通用社交媒体账号格式
            'social_media': r'(?:抖音|快手|小红书|ins|Instagram|Facebook|fb|Twitter|推特)[:：]?\s*[a-zA-Z0-9._-]{3,30}'
        }
        
        # 替换所有匹配到的敏感信息
        for info_type, pattern in patterns.items():
            text = re.sub(pattern, f'[{info_type}已移除]', text, flags=re.IGNORECASE)
        
        return text
    
    def analyze_resume(self, file_path: str, analysis_type: str = "general", output_path: Optional[str] = None, stream: bool = False, job_requirements: Optional[str] = None,model_name: str = None):
        """
        分析简历并保存结果或流式返回分析内容
        
        Args:
            file_path: 简历文件路径
            analysis_type: 分析类型，可选值: "general"(一般分析), 
                                            "interview"(面试题生成), 
            output_path: 输出文件路径，为None时自动生成
            stream: 是否流式返回结果，为True时直接返回AI生成的内容，不保存文件
            job_requirements: 岗位需求描述，为None时不包含岗位需求信息
        
        Returns:
            str 或 generator: 当stream=False时返回输出文件路径，stream=True时返回结果生成器
        """
        # 确定文件类型并提取文本
        if file_path.lower().endswith('.pdf'):
            text = self._extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            text = self._extract_text_from_docx(file_path)
        else:
            raise ValueError("不支持的文件格式，仅支持PDF和DOCX格式")
        
        # 移除敏感信息
        text = self._remove_sensitive_info(text)

        # 选择对应的提示词
        if analysis_type not in self.prompts:
            raise ValueError(f"不支持的分析类型：{analysis_type}，可用类型: {', '.join(self.prompts.keys())}")
        
        system_prompt = self.prompts[analysis_type]
        
        # 使用AI进行分析
        input_text = f"简历内容：{text}"
        if job_requirements:
            input_text = f"岗位需求：{job_requirements}\n\n{input_text}"

        # 根据stream参数选择输出方式
        if stream:
            # 流式返回结果
            return self.ai.stream_chat(user_message=input_text, system_prompt=system_prompt,model_name=model_name)
        else:
            # 保存到文件并返回文件路径
            output_text = self.ai.chat(user_message=input_text, system_prompt=system_prompt,model_name=model_name)
            
            # 生成输出路径
            output_path = self._generate_output_path(file_path, output_path, analysis_type)
                
            # 保存结果
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_text)
                
            return output_path
    
    def generate_interview_questions(self, file_path: str, output_path: Optional[str] = None, stream: bool = False, job_requirements: Optional[str] = None):
        """
        根据简历生成面试问题
        
        Args:
            file_path: 简历文件路径
            output_path: 输出文件路径，为None时自动生成
            stream: 是否流式返回结果
            job_requirements: 岗位需求描述，为None时不包含岗位需求信息
            
        Returns:
            str 或 generator: 当stream=False时返回输出文件路径，stream=True时返回结果生成器
        """
        return self.analyze_resume(file_path, "interview", output_path, stream, job_requirements)
    

    def _generate_output_path(self, file_path: str, output_path: Optional[str], analysis_type: str) -> str:
        """生成输出文件路径"""
        if output_path is None:
            output_folder = os.path.join(os.path.dirname(file_path), "output")
            os.makedirs(output_folder, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(output_folder, f"{base_name}_{analysis_type}.md")
        else:
            output_path = os.path.abspath(output_path)
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            
            if os.path.isdir(output_path):
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(output_path, f"{base_name}_{analysis_type}.md")
            else:
                output_dir = os.path.dirname(output_path)
                base_name = os.path.splitext(os.path.basename(output_path))[0]
                output_path = os.path.join(output_dir, f"{base_name}.md")
            
        # 处理文件已存在的情况
        base = os.path.splitext(output_path)[0]
        counter = 1
        while os.path.exists(output_path):
            output_path = f"{base}_{counter}.md"
            counter += 1
            
        return output_path
  
