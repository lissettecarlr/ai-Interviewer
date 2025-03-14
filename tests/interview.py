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

def process_file(file_path, analyzer, analysis_type="interview"):
    """处理单个文件"""
    print(f"开始分析简历: {file_path}")
    analyzer.analyze_resume(file_path=file_path, analysis_type=analysis_type)

def process_directory(dir_path, analyzer, analysis_type="interview"):
    """批量处理目录中的所有PDF文件"""
    pdf_files = glob.glob(os.path.join(dir_path, "*.pdf"))
    if not pdf_files:
        print(f"在目录 {dir_path} 中未找到PDF文件")
        return
    
    print(f"在目录 {dir_path} 中找到 {len(pdf_files)} 个PDF文件")
    for file_path in pdf_files:
        process_file(file_path, analyzer, analysis_type)

if __name__ == "__main__":
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="简历分析工具")
    parser.add_argument("path", help="文件路径或目录路径")
    parser.add_argument("--type", choices=["interview", "analysis"], 
                        default="interview", help="分析类型: interview或analysis")
    args = parser.parse_args()
    
    # 初始化分析器
    ai_interviewer = ResumeAnalyzer()
    
    # 获取绝对路径
    target_path = os.path.abspath(args.path)
    
    # 判断是文件还是目录
    if os.path.isfile(target_path):
        process_file(target_path, ai_interviewer, args.type)
    elif os.path.isdir(target_path):
        process_directory(target_path, ai_interviewer, args.type)
    else:
        print(f"错误: {args.path} 不是有效的文件或目录")

# python tests/interview.py 你的简历文件路径.pdf
# python tests/interview.py 目录路径