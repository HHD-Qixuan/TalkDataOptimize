import os
import json
import shutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'data/uploaded'
app.config['ANNOTATION_FOLDER'] = 'data/annotations'
app.config['TEMP_FOLDER'] = 'data/temp'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['ANNOTATION_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)


class AnnotationManager:
    def __init__(self):
        self.current_index = 0
        self.dataset = []
        self.dataset_name = None
        self.is_modified = False  # 标注界面中当前样本是否被修改

    def load_dataset(self, filename):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = [data]

        self.dataset = []
        for i, item in enumerate(data):
            self.dataset.append({
                'id': i,
                'history': item.get('history', []),
                'instruction': item.get('instruction', ''),
                'input': item.get('input', ''),
                'output': item.get('output', ''),
                'original_output': item.get('output', ''),
                'quality': 'unannotated',
                'is_modified': False,
                'is_annotated': False,
                'timestamp': None,
                'modify_timestamp': None,
                'annotate_timestamp': None
            })

        self.dataset_name = filename
        self.current_index = 0
        self.is_modified = False

        # 加载临时数据
        temp_file = os.path.join(app.config['TEMP_FOLDER'], f"{filename}_temp.json")
        if os.path.exists(temp_file):
            with open(temp_file, 'r', encoding='utf-8') as f:
                temp_data = json.load(f)
                for item_data in temp_data:
                    idx = item_data['id']
                    if idx < len(self.dataset):
                        item = self.dataset[idx]
                        if 'quality' in item_data:
                            item['quality'] = item_data['quality']
                            item['is_annotated'] = True
                            item['annotate_timestamp'] = item_data.get('annotate_timestamp')
                        if 'output' in item_data:
                            item['output'] = item_data['output']
                            item['is_modified'] = item_data.get('is_modified', False)
                            item['modify_timestamp'] = item_data.get('modify_timestamp')

        return len(self.dataset)

    # ============ 标注界面API ============
    def get_current_item(self):
        """获取标注界面的当前样本"""
        if self.dataset and 0 <= self.current_index < len(self.dataset):
            item = self.dataset[self.current_index]
            return {
                'id': item['id'],
                'history': item['history'],
                'instruction': item['instruction'],
                'input': item['input'],
                'output': item['output'],
                'original_output': item['original_output'],
                'quality': item['quality'],
                'is_modified': item['is_modified'],
                'is_annotated': item['is_annotated'],
                'current_index': self.current_index,
                'total': len(self.dataset)
            }
        return None

    def annotate_current(self, quality_type):
        """标注当前样本"""
        if not self.dataset or self.current_index >= len(self.dataset):
            return False

        item = self.dataset[self.current_index]
        item['quality'] = quality_type
        item['is_annotated'] = True
        item['annotate_timestamp'] = datetime.now().isoformat()

        # 如果是废弃，重置修改
        if quality_type == 'discarded':
            item['output'] = item['original_output']
            item['is_modified'] = False

        self._save_temp()
        return True

    def update_current_output(self, new_output):
        """更新当前样本的输出"""
        if not self.dataset or self.current_index >= len(self.dataset):
            return False

        item = self.dataset[self.current_index]
        item['output'] = new_output
        item['is_modified'] = True
        item['modify_timestamp'] = datetime.now().isoformat()
        self.is_modified = True

        self._save_temp()
        return True

    def reset_current_output(self):
        """重置当前样本的输出"""
        if not self.dataset or self.current_index >= len(self.dataset):
            return False

        item = self.dataset[self.current_index]
        item['output'] = item['original_output']
        item['is_modified'] = False
        self.is_modified = False

        self._save_temp()
        return item['output']

    def navigate(self, direction):
        """标注界面导航"""
        if direction == 'next':
            if self.current_index < len(self.dataset) - 1:
                self.current_index += 1
        elif direction == 'prev':
            if self.current_index > 0:
                self.current_index -= 1
        else:
            try:
                idx = int(direction)
                if 0 <= idx < len(self.dataset):
                    self.current_index = idx
            except:
                pass

        # 重置修改状态
        if self.current_index < len(self.dataset):
            self.is_modified = self.dataset[self.current_index]['is_modified']

        return self.get_current_item()

    def export_annotations(self, export_type='all'):
        """导出标注结果"""
        if not self.dataset_name:
            return None

        export_data = []
        for item in self.dataset:
            if export_type == 'all' or item['quality'] == export_type:
                if item['quality'] != 'discarded':  # 废弃的不导出
                    export_item = {
                        'history': item['history'],
                        'instruction': item['instruction'],
                        'input': item['input'],
                        'output': item['output'],
                        'quality': item['quality'],
                        'is_modified': item['is_modified'],
                        'original_output': item['original_output']
                    }
                    export_data.append(export_item)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_filename = f"{self.dataset_name.split('.')[0]}_annotated_{timestamp}.json"
        export_path = os.path.join(app.config['ANNOTATION_FOLDER'], export_filename)

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return export_path

    # ============ 预览界面API ============
    def annotate_item(self, item_id, quality_type):
        """标注单个项目"""
        if item_id < 0 or item_id >= len(self.dataset):
            return False

        item = self.dataset[item_id]
        item['quality'] = quality_type
        item['is_annotated'] = True
        item['annotate_timestamp'] = datetime.now().isoformat()

        # 如果是废弃，重置修改
        if quality_type == 'discarded':
            item['output'] = item['original_output']
            item['is_modified'] = False

        self._save_temp()
        return {
            'id': item['id'],
            'quality': item['quality'],
            'is_modified': item['is_modified'],
            'is_annotated': item['is_annotated'],
            'output': item['output'],
            'annotate_timestamp': item['annotate_timestamp']
        }

    def update_item_output(self, item_id, new_output):
        """更新单个项目的输出"""
        if item_id < 0 or item_id >= len(self.dataset):
            return False

        item = self.dataset[item_id]
        item['output'] = new_output
        item['is_modified'] = True
        item['modify_timestamp'] = datetime.now().isoformat()

        self._save_temp()
        return {
            'id': item['id'],
            'output': item['output'],
            'is_modified': item['is_modified'],
            'modify_timestamp': item['modify_timestamp']
        }

    def reset_item_output(self, item_id):
        """重置单个项目的输出"""
        if item_id < 0 or item_id >= len(self.dataset):
            return False

        item = self.dataset[item_id]
        item['output'] = item['original_output']
        item['is_modified'] = False

        self._save_temp()
        return {
            'id': item['id'],
            'output': item['output'],
            'is_modified': item['is_modified']
        }

    def get_item_details(self, item_id):
        """获取项目详情"""
        if item_id < 0 or item_id >= len(self.dataset):
            return None

        item = self.dataset[item_id]
        return {
            'id': item['id'],
            'history': item['history'],
            'instruction': item['instruction'],
            'input': item['input'],
            'output': item['output'],
            'original_output': item['original_output'],
            'quality': item['quality'],
            'is_modified': item['is_modified'],
            'is_annotated': item['is_annotated'],
            'modify_timestamp': item['modify_timestamp'],
            'annotate_timestamp': item['annotate_timestamp']
        }

    def get_filtered_items(self, filter_type='all', start=0, limit=100):
        """获取过滤后的项目（分页）"""
        filtered_items = []

        for item in self.dataset:
            if self._match_filter(item, filter_type):
                filtered_items.append({
                    'id': item['id'],
                    'history': item['history'],
                    'instruction': item['instruction'],
                    'input': item['input'],
                    'output': item['output'],
                    'quality': item['quality'],
                    'is_modified': item['is_modified'],
                    'is_annotated': item['is_annotated'],
                    'modify_timestamp': item['modify_timestamp'],
                    'annotate_timestamp': item['annotate_timestamp']
                })

        # 应用分页
        end = start + limit
        return filtered_items[start:end], len(filtered_items)

    def _match_filter(self, item, filter_type):
        """检查项目是否匹配过滤器"""
        if filter_type == 'all':
            return True
        elif filter_type == 'unannotated':
            return not item['is_annotated']
        elif filter_type == 'excellent':
            return item['quality'] == 'excellent'
        elif filter_type == 'good':
            return item['quality'] == 'good'
        elif filter_type == 'poor':
            return item['quality'] == 'poor'
        elif filter_type == 'discarded':
            return item['quality'] == 'discarded'
        elif filter_type == 'modified':
            return item['is_modified']
        elif filter_type == 'annotated':
            return item['is_annotated']
        return False

    def _save_temp(self):
        """保存临时数据"""
        if not self.dataset_name:
            return

        temp_data = []
        for item in self.dataset:
            if item['is_annotated'] or item['is_modified']:
                temp_data.append({
                    'id': item['id'],
                    'quality': item['quality'],
                    'output': item['output'],
                    'is_modified': item['is_modified'],
                    'is_annotated': item['is_annotated'],
                    'modify_timestamp': item['modify_timestamp'],
                    'annotate_timestamp': item['annotate_timestamp']
                })

        temp_file = os.path.join(app.config['TEMP_FOLDER'], f"{self.dataset_name}_temp.json")
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(temp_data, f, ensure_ascii=False, indent=2)

    def get_statistics(self):
        """获取统计信息"""
        if not self.dataset:
            return {}

        total = len(self.dataset)
        annotated = sum(1 for item in self.dataset if item['is_annotated'])
        modified = sum(1 for item in self.dataset if item['is_modified'])

        quality_counts = {
            'unannotated': 0,
            'excellent': 0,
            'good': 0,
            'poor': 0,
            'discarded': 0
        }

        for item in self.dataset:
            quality_counts[item['quality']] += 1

        return {
            'total': total,
            'annotated': annotated,
            'modified': modified,
            'quality_counts': quality_counts,
            'progress': (annotated / total * 100) if total > 0 else 0
        }


# 全局标注管理器
annotation_manager = AnnotationManager()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload')
def upload_page():
    return render_template('upload.html')


@app.route('/preview')
def preview_page():
    return render_template('preview.html')


@app.route('/api/upload', methods=['POST'])
def upload_dataset():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files are allowed'}), 400

    filename = f"{uuid.uuid4().hex}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        count = annotation_manager.load_dataset(filename)
        return jsonify({
            'success': True,
            'filename': filename,
            'count': count,
            'message': f'Successfully loaded {count} samples'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ 标注界面API ============
@app.route('/api/current')
def get_current():
    """获取标注界面的当前样本"""
    item = annotation_manager.get_current_item()
    if item:
        return jsonify(item)
    return jsonify({'error': 'No dataset loaded'}), 404


@app.route('/api/annotate', methods=['POST'])
def annotate():
    """标注当前样本"""
    data = request.json
    quality_type = data.get('quality_type')

    if not quality_type:
        return jsonify({'error': 'Quality type is required'}), 400

    success = annotation_manager.annotate_current(quality_type)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to annotate'}), 500


@app.route('/api/update_output', methods=['POST'])
def update_output():
    """更新当前样本的输出"""
    data = request.json
    new_output = data.get('output')

    if new_output is None:
        return jsonify({'error': 'Output content is required'}), 400

    success = annotation_manager.update_current_output(new_output)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to update output'}), 500


@app.route('/api/reset_output', methods=['POST'])
def reset_output():
    """重置当前样本的输出"""
    result = annotation_manager.reset_current_output()
    if result is not False:
        return jsonify({
            'success': True,
            'output': result
        })
    return jsonify({'error': 'Failed to reset output'}), 500


@app.route('/api/navigate', methods=['POST'])
def navigate():
    """标注界面导航"""
    data = request.json
    direction = data.get('direction')

    if not direction:
        return jsonify({'error': 'Direction is required'}), 400

    item = annotation_manager.navigate(direction)
    if item:
        return jsonify(item)
    return jsonify({'error': 'Navigation failed'}), 500


@app.route('/api/export', methods=['POST'])
def export_annotations():
    """导出标注结果"""
    data = request.json
    export_type = data.get('export_type', 'all')

    export_path = annotation_manager.export_annotations(export_type)
    if export_path:
        return jsonify({
            'success': True,
            'filename': os.path.basename(export_path),
            'path': export_path
        })
    return jsonify({'error': 'Export failed'}), 500


# ============ 预览界面API ============
@app.route('/api/preview/filter', methods=['GET'])
def get_filtered_preview():
    """获取过滤后的预览数据（分页）"""
    filter_type = request.args.get('filter', 'all')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    start = (page - 1) * per_page
    items, total_count = annotation_manager.get_filtered_items(filter_type, start, per_page)

    return jsonify({
        'items': items,
        'page': page,
        'per_page': per_page,
        'total': total_count,
        'total_pages': (total_count + per_page - 1) // per_page
    })


@app.route('/api/preview/item/<int:item_id>')
def get_preview_item(item_id):
    """获取单个预览项目详情"""
    item = annotation_manager.get_item_details(item_id)
    if item:
        return jsonify(item)
    return jsonify({'error': 'Item not found'}), 404


@app.route('/api/preview/annotate', methods=['POST'])
def preview_annotate():
    """预览界面标注"""
    data = request.json
    item_id = data.get('item_id')
    quality_type = data.get('quality_type')

    if item_id is None or quality_type is None:
        return jsonify({'error': 'Missing parameters'}), 400

    item = annotation_manager.annotate_item(item_id, quality_type)
    if item:
        return jsonify({
            'success': True,
            'item': item
        })
    return jsonify({'error': 'Failed to annotate'}), 500


@app.route('/api/preview/save_output', methods=['POST'])
def preview_save_output():
    """预览界面保存输出"""
    data = request.json
    item_id = data.get('item_id')
    output = data.get('output')

    if item_id is None or output is None:
        return jsonify({'error': 'Missing parameters'}), 400

    item = annotation_manager.update_item_output(item_id, output)
    if item:
        return jsonify({
            'success': True,
            'item': item
        })
    return jsonify({'error': 'Failed to save output'}), 500


@app.route('/api/preview/reset_output', methods=['POST'])
def preview_reset_output():
    """预览界面重置输出"""
    data = request.json
    item_id = data.get('item_id')

    if item_id is None:
        return jsonify({'error': 'Missing item_id'}), 400

    item = annotation_manager.reset_item_output(item_id)
    if item:
        return jsonify({
            'success': True,
            'item': item
        })
    return jsonify({'error': 'Failed to reset output'}), 500


# ============ 通用API ============
@app.route('/api/download/<path:filename>')
def download_file(filename):
    """下载导出的文件"""
    return send_from_directory(app.config['ANNOTATION_FOLDER'], filename, as_attachment=True)


@app.route('/api/statistics')
def get_statistics():
    """获取统计信息"""
    stats = annotation_manager.get_statistics()
    if stats:
        return jsonify(stats)
    return jsonify({'error': 'No dataset loaded'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)