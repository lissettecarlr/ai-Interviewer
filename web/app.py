from flask import Flask, request, render_template, send_file, jsonify, Response, stream_with_context
import os
from werkzeug.utils import secure_filename
import time
import shutil
import json

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from resume_analysis import ResumeAnalyzer

app = Flask(__name__)

# 添加可用模型配置
app.config['AVAILABLE_MODELS'] = [
    {"id": "gpt-4o", "name": "GPT-4o (默认)", "default": True},
    {"id": "o1-preview", "name": "o1-preview (贵且慢，但是更准确)", "default": False},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "default": False},
    # 可以在这里添加更多模型
]

# 文件结构优化
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'results')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 限制

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    return render_template('upload.html', models=app.config['AVAILABLE_MODELS'])

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': '没有文件被上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '没有选择文件'}), 400
    
    # 获取分析类型
    analysis_type = request.form.get('analysis_type', 'general')
    stream_output = request.form.get('stream_output', 'false').lower() == 'true'
    # 获取模型参数
    model_name = request.form.get('model_name', 'gpt-4o')
    
    if file and allowed_file(file.filename):
        # 使用时间戳确保文件名唯一
        timestamp = int(time.time())
        
        # 保存原始文件名用于显示
        display_filename = file.filename
        
        # 对文件系统使用安全的文件名
        safe_filename = secure_filename(file.filename)
        if not safe_filename:  # 如果安全化后文件名为空
            safe_filename = f"file_{timestamp}"
        
        filename_base, file_extension = os.path.splitext(safe_filename)
        
        # 保留安全的文件名，只添加时间戳
        unique_filename = f"{filename_base}_{timestamp}{file_extension}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # 处理简历
        job_requirements = request.form.get('job_requirements', '')
        
        if stream_output:
            # 流式输出模式，返回一个标识符以用于获取流式结果
            stream_id = f"{filename_base}_{timestamp}"
            return jsonify({
                'status': 'success',
                'message': '开始分析',
                'stream_id': stream_id,
                'original_name': display_filename,
                'analysis_type': analysis_type
            })
        else:
            # 普通模式，分析完毕后返回结果
            output_filename = f"{filename_base}_{timestamp}.md"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            
            try:
                analyzer = ResumeAnalyzer()
                analyzer.analyze_resume(
                    file_path=filepath, 
                    analysis_type=analysis_type, 
                    output_path=output_path,
                    job_requirements=job_requirements
                )
                
                # 保存文件名映射
                map_file = os.path.join(app.config['OUTPUT_FOLDER'], 'filename_map.json')
                filename_map = {}
                if os.path.exists(map_file):
                    try:
                        with open(map_file, 'r', encoding='utf-8') as f:
                            filename_map = json.load(f)
                    except:
                        pass
                
                # 保存不带扩展名的输出文件名到原始文件名的映射
                output_base = output_filename.rsplit('.', 1)[0]
                filename_map[output_base] = display_filename.rsplit('.', 1)[0]  # 不带扩展名
                
                with open(map_file, 'w', encoding='utf-8') as f:
                    json.dump(filename_map, f, ensure_ascii=False)
                
                return jsonify({
                    'status': 'success',
                    'message': '分析完成',
                    'filename': output_filename,
                    'original_name': display_filename
                })
            except Exception as e:
                return jsonify({'status': 'error', 'message': f'分析失败: {str(e)}'}), 500
    
    return jsonify({'status': 'error', 'message': '不支持的文件类型'}), 400

@app.route('/stream/<stream_id>', methods=['GET'])
def stream_analysis(stream_id):
    """流式输出分析结果"""
    if not stream_id or '_' not in stream_id:
        return jsonify({'status': 'error', 'message': '无效的流ID'}), 400
    
    # 从stream_id解析需要的信息
    filename_base, timestamp = stream_id.rsplit('_', 1)
    
    # 查找上传的文件
    uploaded_files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
                     if f.startswith(f"{filename_base}_{timestamp}")]
    
    if not uploaded_files:
        return jsonify({'status': 'error', 'message': '找不到上传的文件'}), 404
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_files[0])
    analysis_type = request.args.get('analysis_type', 'general')
    job_requirements = request.args.get('job_requirements', '')
    
    # 生成输出文件名
    output_filename = f"{filename_base}_{timestamp}.md"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
    
    # 创建流式生成器
    def generate():
        analyzer = ResumeAnalyzer()
        full_content = ""
        
        try:
            # 启动流式分析
            for chunk in analyzer.analyze_resume(
                file_path=filepath,
                analysis_type=analysis_type,
                stream=True,
                job_requirements=job_requirements
            ):
                full_content += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            
            # 分析完成后，保存结果
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            # 保存文件名映射
            map_file = os.path.join(app.config['OUTPUT_FOLDER'], 'filename_map.json')
            filename_map = {}
            if os.path.exists(map_file):
                try:
                    with open(map_file, 'r', encoding='utf-8') as f:
                        filename_map = json.load(f)
                except:
                    pass
            
            # 查找原始显示文件名
            display_filename = ""
            for f in uploaded_files:
                if f.startswith(f"{filename_base}_{timestamp}"):
                    display_filename = f.rsplit('_', 1)[0]
                    if '.' in display_filename:
                        display_filename = display_filename.rsplit('.', 1)[0]
                    break
            
            # 保存不带扩展名的输出文件名到原始文件名的映射
            output_base = output_filename.rsplit('.', 1)[0]
            filename_map[output_base] = display_filename
            
            with open(map_file, 'w', encoding='utf-8') as f:
                json.dump(filename_map, f, ensure_ascii=False)
            
            # 发送完成信号
            yield f"data: {json.dumps({'status': 'complete', 'filename': output_filename})}\n\n"
        
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route('/result/<filename>')
def show_result(filename):
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    
    if not os.path.exists(output_path):
        return render_template('error.html', message='文件不存在')
    
    with open(output_path, 'r', encoding='utf-8') as f:
        result = f.read()
    
    # 使用ensure_ascii=False确保中文正确显示，并处理特殊字符
    result_json = json.dumps(result, ensure_ascii=False)
    
    # 从文件名中提取原始文件名（去掉时间戳和扩展名）
    original_name = filename.rsplit('_', 1)[0]
    return render_template('result.html', result_json=result_json, filename=filename, original_name=original_name)

@app.route('/download/<filename>')
def download_file(filename):
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    
    if not os.path.exists(output_path):
        return render_template('error.html', message='文件不存在')
    
    # 提供更友好的下载文件名 - 保持与原始文件名一致
    original_name = filename.rsplit('_', 1)[0] + '.md'
    return send_file(output_path, as_attachment=True, download_name=original_name)

@app.route('/api/recent-results', methods=['GET'])
def get_recent_results():
    results = []
    
    # 尝试从文件中读取原始文件名映射
    filename_map = {}
    map_file = os.path.join(app.config['OUTPUT_FOLDER'], 'filename_map.json')
    if os.path.exists(map_file):
        try:
            with open(map_file, 'r', encoding='utf-8') as f:
                filename_map = json.load(f)
        except:
            pass
    
    for filename in os.listdir(app.config['OUTPUT_FOLDER']):
        if filename.endswith('.md'):
            file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            
            # 尝试从映射中获取原始文件名
            base_name = filename.rsplit('.', 1)[0]  # 不带扩展名
            if base_name in filename_map:
                original_name = filename_map[base_name]
            else:
                # 如果没有映射，则使用文件名的第一部分
                original_name = filename.rsplit('_', 1)[0]
            
            results.append({
                'filename': filename,
                'modified_time': os.path.getmtime(file_path),
                'original_name': original_name
            })
    
    # 按修改时间排序，最新的在前
    results.sort(key=lambda x: x['modified_time'], reverse=True)
    return jsonify(results[:10])  # 只返回最近10个

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/api/clear-files', methods=['POST'])
def clear_files():
    try:
        # 清空上传文件夹
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
        
        # 清空结果文件夹，但保留 filename_map.json
        for filename in os.listdir(app.config['OUTPUT_FOLDER']):
            if filename != 'filename_map.json':
                file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        
        # 清空文件名映射
        map_file = os.path.join(app.config['OUTPUT_FOLDER'], 'filename_map.json')
        if os.path.exists(map_file):
            with open(map_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        
        return jsonify({'status': 'success', 'message': '所有文件已清空'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'清空文件失败: {str(e)}'}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('error.html', message='文件太大，请上传小于16MB的文件'), 413

@app.route('/stream-result')
def stream_result_page():
    """显示流式分析结果页面"""
    return render_template('stream-result.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=23333, debug=True)