from flask import current_app, send_file, Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from flask_sqlalchemy import SQLAlchemy
from flask_mysqldb import MySQL
from config import Config
from urllib.parse import unquote
from datetime import datetime
import json
import cv2
import shutil
from werkzeug.utils import secure_filename

#初始化flask
db = SQLAlchemy()
mysql = MySQL()

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] ='mysql+pymysql://root:lcc145@localhost/defect_sql'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 通常建议关闭这个选项

# 初始化插件
db.init_app(app)  # 这里初始化db
mysql.init_app(app)  # 这里初始化mysql

with app.app_context():
    # 导入路由
    #import routes

    # 创建数据库表
    db.create_all()

    # # 创建默认项目（如果需要）
    # from models import Project
    # if Project.query.count() == 0:
    #     from utils import create_default_data
    #     create_default_data()

# 导入模型
#from models import Project, Inspection, Image, Label, ImageLabelInfo, DetectResult
#models.py
class Project(db.Model):
    __tablename__ = 'project'
    id = db.Column(db.Integer, primary_key=True)
    project_short_name = db.Column(db.String(100), nullable=False)
    project_full_name = db.Column(db.String(100), nullable=False)
    builder_name = db.Column(db.String(100), nullable=False)
    total_area = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    advance_rate = db.Column(db.Integer, nullable=False)

class Inspection(db.Model):
    __tablename__ = 'inspection'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    inspection_name = db.Column(db.String(100), nullable=False)
    img_num = db.Column(db.Integer, nullable=False)
    #class_num = db.Column(db.Integer, nullable=False)
    project = db.relationship('Project', backref='inspections')

class Image(db.Model):
    __tablename__ = 'image'
    id = db.Column(db.Integer, primary_key=True)
    image_name = db.Column(db.String(100), nullable=False)
    image_absolute_path = db.Column(db.Text)
    image_relative_path = db.Column(db.Text)
    image_type = db.Column(db.String(100), nullable=False)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspection.id'))
    inspection = db.relationship('Inspection', backref='images')

class Label(db.Model):
    __tablename__ = 'label'
    id = db.Column(db.Integer, primary_key=True)
    label_name = db.Column(db.String(100), nullable=False)

class DetectResult(db.Model):
    __tablename__ = 'detect_result'
    id = db.Column(db.Integer, primary_key=True)
    detect_result = db.Column(db.Text, nullable=False)
    detect_result_image_name = db.Column(db.String(100), nullable=False)
    detect_time = db.Column(db.DateTime)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspection.id'))
    inspection = db.relationship('Inspection', backref='defects')

class ImageLabelInfo(db.Model):
    __tablename__ = 'image_label_info'
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey('image.id'))
    label_id = db.Column(db.Integer, db.ForeignKey('label.id'))
    image = db.relationship('Image', backref='labels')
    label = db.relationship('Label', backref='images')


def parse_project_overview(file_path):
    """解析project_overview.txt文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    if len(lines) < 5:
        raise ValueError(f"文件 {file_path} 格式不正确，至少需要5行数据")

    return {
        'project_full_name': lines[0],
        'builder_name': lines[1],
        'total_area': int(lines[2]),
        'duration': int(lines[3]),
        'advance_rate': int(lines[4])
    }

def process_projects_folder(base_path='Projects'):
    """处理Projects文件夹"""
    # 首先添加预定义的标签
    predefined_labels = [
        'Refineforcement exposure',
        'Missing edge corner',
        'Connection defect',
        'Crack leak',
        'Slag defect',
        'Hole defect'
    ]

    for label_name in predefined_labels:
        if not Label.query.filter_by(label_name=label_name).first():
            db.session.add(Label(label_name=label_name))

    db.session.commit()

    # 遍历Projects文件夹
    for project_dir in os.listdir(base_path):
        project_path = os.path.join(base_path, project_dir)
        if not os.path.isdir(project_path):
            continue

        # 获取项目简称（文件夹名）
        project_short_name = project_dir

        # 解析project_overview.txt
        overview_file = os.path.join(project_path, 'project_overview.txt')
        if not os.path.exists(overview_file):
            print(f"警告：项目 {project_dir} 缺少 project_overview.txt 文件")
            continue

        try:
            overview = parse_project_overview(overview_file)
        except Exception as e:
            print(f"解析 {overview_file} 失败: {e}")
            continue

        # 检查项目是否已存在
        project = Project.query.filter_by(project_short_name=project_short_name).first()
        if not project:
            project = Project(
                project_short_name=project_short_name,
                project_full_name=overview['project_full_name'],
                builder_name=overview['builder_name'],
                total_area=overview['total_area'],
                duration=overview['duration'],
                advance_rate=overview['advance_rate']
            )
            db.session.add(project)
            db.session.commit()
            print(f"添加新项目: {project_short_name}")

        # 处理inspection文件夹
        inspection_dir = os.path.join(project_path, 'inspection')
        if not os.path.exists(inspection_dir):
            print(f"警告：项目 {project_dir} 缺少 inspection 文件夹")
            continue

        # 遍历inspection文件夹中的时间目录
        for inspection_time_dir in os.listdir(inspection_dir):
            inspection_time_path = os.path.join(inspection_dir, inspection_time_dir)
            if not os.path.isdir(inspection_time_path):
                continue

            # 检查images文件夹是否存在
            images_dir = os.path.join(inspection_time_path, 'images')
            if not os.path.exists(images_dir):
                print(f"警告：巡检 {inspection_time_dir} 缺少 images 文件夹")
                continue

            # 使用时间目录名作为inspection_name
            inspection_name = inspection_time_dir

            # 检查巡检是否已存在
            inspection = Inspection.query.filter_by(
                project_id=project.id,
                inspection_name=inspection_name
            ).first()

            if not inspection:
                # 计算图片数量
                img_count = 0
                for root, dirs, files in os.walk(images_dir):
                    img_count += len([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))])

                if img_count == 0:
                    print(f"警告：巡检 {inspection_name} 没有图片，跳过")
                    continue

                inspection = Inspection(
                    project_id=project.id,
                    inspection_name=inspection_name,
                    img_num=img_count
                )
                db.session.add(inspection)
                db.session.commit()
                print(f"添加新巡检: {inspection_name} (图片数量: {img_count})")

            # 处理巡检中的图片
            for root, dirs, files in os.walk(images_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        image_path = os.path.join(root, file)
                        relative_path = os.path.relpath(image_path, os.path.join(base_path, project_dir))

                        # 检查图片是否已存在
                        if not Image.query.filter_by(
                                inspection_id=inspection.id,
                                image_name=file
                        ).first():
                            image = Image(
                                image_name=file,
                                image_absolute_path=os.path.abspath(image_path),
                                image_relative_path=relative_path,  # 存储相对于项目目录的路径
                                image_type=os.path.splitext(file)[1][1:].lower(),
                                inspection_id=inspection.id
                            )
                            db.session.add(image)
                            db.session.add(image)

            db.session.commit()

def create_default_data():
    # Projects are already created via SQL script
    pass

def run_yolov8_detection(image_path):
    import sys
    sys.path.append('app/yolov8')
    from detect import detect_defects

    result = detect_defects(image_path)
    return result

def save_detection_result(result, image_name, inspection_id):
    try:
        # 定义英文标签到中文的映射
        label_mapping = {
            'Reinforcement exposure': '钢筋暴露',
            'Missing edges and corners': '缺棱掉角',
            'Faulted slabs': '错台',
            'Grout leakage': '拼缝漏浆',
            'Crack or leakage': '裂缝渗漏',
            'Honeycomb': '蜂窝',
            'Blowhole': '气泡'
        }

        # 定义不同标签对应的颜色 (BGR格式)
        label_colors = {
            '钢筋暴露': (0, 255, 0),  # 绿色
            '缺棱掉角': (0, 0, 255),  # 红色
            '错台': (255, 0, 0),  # 蓝色
            '拼缝漏浆': (10, 255, 255),  # 黄色
            '裂缝渗漏': (255, 0, 255),  # 紫色
            '蜂窝': (255, 255, 0),  # 青色
            '气泡': (50, 0, 50),  # 深紫色
        }

        default_color = (255, 255, 255)  # 白色

        # 获取图片记录
        image = Image.query.filter_by(image_name=image_name, inspection_id=inspection_id).first()
        if not image:
            print(f"警告: 找不到图片记录 {image_name}")
            return

        # 获取巡检和项目信息
        inspection = Inspection.query.get(inspection_id)
        if not inspection:
            print(f"警告: 找不到巡检记录 {inspection_id}")
            return

        # 构建结果存储路径
        image_dir = os.path.dirname(image.image_absolute_path)
        inspection_dir = os.path.dirname(image_dir)
        project_dir = os.path.dirname(os.path.dirname(inspection_dir))
        project_short_name = os.path.basename(project_dir)

        # 创建results目录（如果不存在）
        results_dir = os.path.join(inspection_dir, 'results')
        os.makedirs(results_dir, exist_ok=True)

        # 原始图片路径和结果图片路径
        original_img_path = image.image_absolute_path
        result_img_path = os.path.join(results_dir, f"result_{image_name}")

        # 读取图片并绘制检测框
        img = cv2.imread(original_img_path)
        if img is not None:
            for label_info in result['labels']:
                # 获取原始标签并映射为中文
                original_label = label_info['label']
                chinese_label = label_mapping.get(original_label, original_label)

                # 更新标签信息中的标签为中文
                #label_info['label'] = chinese_label

                # 获取坐标
                x1, y1, x2, y2 = map(int, [
                    label_info['xmin'],
                    label_info['ymin'],
                    label_info['xmax'],
                    label_info['ymax']
                ])

                # 选择颜色
                color = label_colors.get(chinese_label, default_color)

                # 绘制矩形框
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                cv2.putText(img, label_info['label'], (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # # 绘制标签背景和文字
                # text = f"{chinese_label}"
                # font = cv2.FONT_HERSHEY_SIMPLEX
                # font_scale = 0.5
                # thickness = 1
                #
                # # 获取文本大小
                # (text_width, text_height), baseline = cv2.getTextSize(
                #     text, font, font_scale, thickness)
                #
                # # 绘制背景矩形
                # cv2.rectangle(img,
                #               (x1, y1 - text_height - 5),
                #               (x1 + text_width, y1),
                #               color,
                #               -1)
                #
                # # 绘制文本（白色）
                # cv2.putText(img, text, (x1, y1 - 5),
                #             font, font_scale, (255, 255, 255), thickness)

            # 保存带标注的图片
            cv2.imwrite(result_img_path, img)
        else:
            print(f"警告: 无法读取图片 {original_img_path}")
            shutil.copy2(original_img_path, result_img_path)

        # 构建相对路径用于数据库存储
        relative_path = os.path.join(
            'inspection',
            inspection.inspection_name,
            'results',
            f"result_{image_name}"
        )

        # 保存检测结果到数据库（使用中文标签）
        detect_result = DetectResult(
            detect_result=json.dumps(result['labels'], ensure_ascii=False),  # 确保中文正常保存
            detect_result_image_name=relative_path,
            detect_time=datetime.now(),
            inspection_id=inspection_id
        )
        db.session.add(detect_result)
        db.session.commit()

        # 处理图片标签关系
        ImageLabelInfo.query.filter_by(image_id=image.id).delete()
        for label_info in result['labels']:
            # 使用中文标签
            chinese_label = label_mapping.get(label_info['label'], label_info['label'])
            label = Label.query.filter_by(label_name=chinese_label).first()
            if not label:
                label = Label(label_name=chinese_label)
                db.session.add(label)
                db.session.commit()

            ili = ImageLabelInfo(image_id=image.id, label_id=label.id)
            db.session.add(ili)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"保存检测结果时出错: {str(e)}")
        raise

@app.route('/')
def index():
    try:
        process_projects_folder()
        print("项目数据导入成功！")
        projects = Project.query.with_entities(
            Project.id,
            Project.project_short_name
        ).all()
        return render_template('index_std.html', projects=projects)
    except Exception as e:
        return f"导入失败: {str(e)}", 500


@app.route('/api/project/<int:project_id>')
def get_project(project_id):
    project = Project.query.get(project_id)
    inspections = Inspection.query.filter_by(project_id=project_id).all()

    if not project:
        return jsonify({'success': False, 'message': '项目不存在'})

    inspections_data = []
    for inspection in inspections:
        # 检查该巡检是否有检测结果
        has_detection = DetectResult.query.filter_by(inspection_id=inspection.id).first() is not None

        inspections_data.append({
            'id': inspection.id,
            'inspection_name': inspection.inspection_name,
            'inspection_time': inspection.inspection_name,
            'total_images': inspection.img_num,
            'has_detection': has_detection
        })

    return jsonify({
        'success': True,
        'data': {
            'project_info': {
                'project_full_name': project.project_full_name,
                'builder_name': project.builder_name,
                'total_area': project.total_area,
                'duration': project.duration,
                'advance_rate': project.advance_rate
            },
            'inspections': inspections_data
        }
    })


@app.route('/api/start-detection/<int:inspection_id>', methods=['POST'])
def start_detection(inspection_id):
    try:
        # 获取巡检记录
        inspection = Inspection.query.get(inspection_id)
        if not inspection:
            return jsonify({'success': False, 'message': '巡检记录不存在'})

        # 获取该巡检下的所有图片
        images = Image.query.filter_by(inspection_id=inspection.id).all()
        if not images:
            return jsonify({'success': False, 'message': '该巡检记录下没有图片'})

        # 对每张图片进行检测
        for image in images:
            if not os.path.exists(image.image_absolute_path):
                print(f"警告: 图片文件不存在 {image.image_absolute_path}")
                continue

            # 运行YOLO检测
            detection_result = run_yolov8_detection(image.image_absolute_path)

            # 保存检测结果
            save_detection_result(detection_result, image.image_name, inspection_id)

        # 创建与巡检记录的关联
        # detect_result = DetectResult(
        #     detect_result="检测完成",  # 简单标记
        #     detect_result_image_name="",  # 不需要特定图片名
        #     detect_time=datetime.now(),
        #     inspection_id=inspection_id
        # )
        #db.session.add(detect_result)
        db.session.commit()

        return jsonify({'success': True, 'message': '检测完成'})

    except Exception as e:
        db.session.rollback()
        print(f"检测过程中出错: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

# 修改get_inspection_results函数
@app.route('/api/inspection/<int:inspection_id>/results')
def get_inspection_results(inspection_id):
    try:
        inspection = Inspection.query.get(inspection_id)
        if not inspection:
            return jsonify({'success': False, 'message': '巡检记录不存在'})

        project = Project.query.get(inspection.project_id)
        if not project:
            return jsonify({'success': False, 'message': '关联项目不存在'})

        # 获取所有检测结果
        detect_results = DetectResult.query.filter_by(inspection_id=inspection_id).all()

        # 使用数据库中存储的图片总数
        total_images = inspection.img_num
        defect_images = len(detect_results)
        total_defects = sum(len(json.loads(r.detect_result)) for r in detect_results)

        images = Image.query.filter_by(inspection_id=inspection_id).all()

        records = []
        for result in detect_results:
            try:
                labels = json.loads(result.detect_result)
                result_image_name = os.path.basename(result.detect_result_image_name)
                original_image_name = result_image_name.replace('result_', '')
                image = next(
                    (img for img in images if img.image_name == original_image_name),
                    None
                )

                if not image:
                    continue

                gps_data = read_gps_from_image(image.image_absolute_path)

                for label in labels:
                    records.append({
                        'time': result.detect_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'location': f"{gps_data['latitude'] if gps_data else '未知'}, {gps_data['longitude'] if gps_data else '未知'}",
                        'image_name': original_image_name,
                        'result_image_name': result_image_name,
                        'defect_type': label['label'],  # 这里已经是中文了
                        'image_path': result.detect_result_image_name,
                        'original_image_path': image.image_relative_path,
                        'project_short_name': project.project_short_name,
                        'inspection_name': inspection.inspection_name
                    })
            except Exception as e:
                print(f"处理检测结果时出错: {str(e)}")
                continue

        return jsonify({
            'success': True,
            'data': {
                'total_images': total_images,
                'defect_images': defect_images,
                'total_defects': total_defects,
                'records': records,
                'inspection_name': inspection.inspection_name,
                'project_short_name': project.project_short_name
            }
        })
    except Exception as e:
        print(f"获取检测结果时出错: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


# 新增API用于获取图片
@app.route('/api/image/<path:filename>')
def get_image(filename):
    try:
        # 这里需要根据实际情况修改，找到图片的实际存储路径
        # 假设图片存储在Projects目录下

        # 1. 尝试直接查找
        image_path = None
        for root, dirs, files in os.walk('Projects'):
            if filename in files:
                image_path = os.path.join(root, filename)
                break

        if not image_path:
            # 2. 尝试通过数据库查找
            image = Image.query.filter_by(image_name=filename).first()
            if image:
                image_path = image.image_absolute_path

        if not image_path or not os.path.exists(image_path):
            return jsonify({'success': False, 'message': '图片不存在'}), 404

        # 处理中文路径
        from urllib.parse import quote
        safe_path = quote(image_path)

        # 返回文件内容
        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        print(f"获取图片时出错: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

def read_gps_from_image(image_path):
    try:
        import piexif
        exif_dict = piexif.load(image_path)

        if "GPS" in exif_dict:
            gps_data = exif_dict["GPS"]
            # 解析GPS信息（这里简化处理，实际需要更复杂的转换）
            lat = gps_data.get(piexif.GPSIFD.GPSLatitude, [0, 0, 0])
            lon = gps_data.get(piexif.GPSIFD.GPSLongitude, [0, 0, 0])

            # 转换为十进制
            def to_decimal(coord):
                return coord[0] + coord[1] / 60 + coord[2] / 3600

            return {
                'latitude': to_decimal(lat),
                'longitude': to_decimal(lon)
            }
        return None
    except:
        return None


















@app.route('/project/<int:project_id>')
def project_inspections(project_id):
    """显示指定项目的巡检列表"""
    project = Project.query.get_or_404(project_id)
    inspections = Inspection.query.filter_by(project_id=project_id).all()
    return render_template('inspections.html', project=project, inspections=inspections)

@app.route('/inspection/<int:inspection_id>')
def inspection_images(inspection_id):
    """显示指定巡检的图片轮播"""
    inspection = Inspection.query.get_or_404(inspection_id)
    images = Image.query.filter_by(inspection_id=inspection_id).all()
    return render_template('carousel.html', inspection=inspection, images=images)

@app.route('/api/images/<int:inspection_id>')
def get_images(inspection_id):
    """API接口，获取指定巡检的图片数据(JSON格式)"""
    images = Image.query.filter_by(inspection_id=inspection_id).all()
    image_list = [{
        'id': img.id,
        'name': img.image_name,
        'path': img.image_relative_path.replace('\\', '/')  # 统一使用斜杠
    } for img in images]
    return jsonify(image_list)

@app.route('/projects/<path:filename>')
def project_files(filename):
    """处理项目文件请求"""
    try:
        # 解码URL中的特殊字符（如中文和空格）
        filename = unquote(filename)

        # 替换所有反斜杠为正斜杠（兼容Windows路径）
        filename = filename.replace('\\', '/')

        # 获取项目根目录
        base_dir = os.path.abspath(os.path.dirname(__file__))

        # 构建完整的文件路径（从Projects目录开始）
        file_path = os.path.join(base_dir, 'Projects', filename)

        # 标准化路径（解决./和../等问题）
        file_path = os.path.normpath(file_path)

        # 安全检查：确保路径仍在Projects目录内
        projects_dir = os.path.join(base_dir, 'Projects')
        if not os.path.abspath(file_path).startswith(os.path.abspath(projects_dir)):
            return "禁止访问", 403

        # 检查文件是否存在
        if not os.path.isfile(file_path):
            app.logger.error(f"文件未找到: {file_path}")
            return "文件未找到", 404

        # 使用send_file发送文件，并设置缓存
        return send_file(file_path, max_age=3600)  # 缓存1小时

    except Exception as e:
        app.logger.error(f"处理文件请求时出错: {str(e)}")
        return "服务器错误", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)