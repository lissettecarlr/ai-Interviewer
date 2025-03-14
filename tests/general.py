import sys
import os
import argparse
import glob
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from resume_analysis import ResumeAnalyzer
from dotenv import load_dotenv

load_dotenv()
os.environ["ONEAPI_KEY"] = os.getenv("ONEAPI_KEY")
os.environ["ALIYUN_KEY"] = os.getenv("ALIYUN_KEY")

job_requirements = """
经验丰富的嵌入式软件开发工程师
"""

def process_single_file(file_path, analyzer, stream=True):
    """处理单个文件，使用流式输出"""
    print(f"开始分析简历: {file_path}")
    if stream:
        for chunk in analyzer.analyze_resume(file_path=file_path, analysis_type="general", stream=True, job_requirements=job_requirements):
            print(chunk, end="", flush=True)
    else:
        # 创建输出目录
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取分析结果
        analyzer.analyze_resume(file_path=file_path, output_path=output_dir, analysis_type="general", stream=False, job_requirements=job_requirements)
        

def process_directory(dir_path, analyzer):
    """批量处理目录中的所有PDF文件，结果保存为文件"""
    pdf_files = glob.glob(os.path.join(dir_path, "*.pdf"))
    if not pdf_files:
        print(f"在目录 {dir_path} 中未找到PDF文件")
        return
    
    print(f"在目录 {dir_path} 中找到 {len(pdf_files)} 个PDF文件")
    for file_path in pdf_files:
        process_single_file(file_path, analyzer, stream=False)

if __name__ == "__main__":
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="简历通用分析工具")
    parser.add_argument("path", help="文件路径或目录路径")
    args = parser.parse_args()
    
    # 初始化分析器
    ai_interviewer = ResumeAnalyzer()
    
    # 获取绝对路径
    target_path = os.path.abspath(args.path)
    
    # 判断是文件还是目录
    if os.path.isfile(target_path):
        process_single_file(target_path, ai_interviewer, stream=True)
    elif os.path.isdir(target_path):
        process_directory(target_path, ai_interviewer)
    else:
        print(f"错误: {args.path} 不是有效的文件或目录")

# 使用示例:
# 单个文件分析(流式输出): python tests/general.py 你的简历文件路径.pdf
# 批量分析目录中的文件(保存到文件): python tests/general.py 目录路径

