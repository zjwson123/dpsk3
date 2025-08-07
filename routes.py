import os
import json
from flask import Blueprint, render_template, jsonify, request, send_file, current_app
from urllib.parse import unquote
from models import db, Project, Inspection, Image, DetectResult
from services import (
    process_projects_folder,
    run_yolov8_detection,
    save_detection_result,
    read_gps_from_image
)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Note: process_projects_folder is removed from here as per the plan.
    # It will be a CLI command.
    try:
        projects = Project.query.with_entities(
            Project.id,
            Project.project_short_name
        ).all()
        return render_template('index_std.html', projects=projects)
    except Exception as e:
        # If the database is empty, it might throw an error.
        # This can happen if the app is run before the initial data import.
        current_app.logger.error(f"Error loading index page: {e}")
        return render_template('index_std.html', projects=[], error="数据库可能尚未初始化。请运行数据导入命令。")


@main_bp.route('/api/project/<int:project_id>')
def get_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'success': False, 'message': '项目不存在'})

    inspections = Inspection.query.filter_by(project_id=project_id).all()
    inspections_data = []
    for inspection in inspections:
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

@main_bp.route('/api/start-detection/<int:inspection_id>', methods=['POST'])
def start_detection(inspection_id):
    # This is still synchronous. The plan is to make it async later.
    try:
        inspection = Inspection.query.get(inspection_id)
        if not inspection:
            return jsonify({'success': False, 'message': '巡检记录不存在'})

        images = Image.query.filter_by(inspection_id=inspection.id).all()
        if not images:
            return jsonify({'success': False, 'message': '该巡检记录下没有图片'})

        for image in images:
            if not os.path.exists(image.image_absolute_path):
                print(f"警告: 图片文件不存在 {image.image_absolute_path}")
                continue

            detection_result = run_yolov8_detection(image.image_absolute_path)
            save_detection_result(detection_result, image.image_name, inspection_id)

        db.session.commit()
        return jsonify({'success': True, 'message': '检测完成'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"检测过程中出错: {e}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/inspection/<int:inspection_id>/results')
def get_inspection_results(inspection_id):
    try:
        inspection = Inspection.query.get(inspection_id)
        if not inspection:
            return jsonify({'success': False, 'message': '巡检记录不存在'})

        project = Project.query.get(inspection.project_id)
        if not project:
            return jsonify({'success': False, 'message': '关联项目不存在'})

        detect_results = DetectResult.query.filter_by(inspection_id=inspection_id).all()
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
                image = next((img for img in images if img.image_name == original_image_name), None)

                if not image:
                    continue

                gps_data = read_gps_from_image(image.image_absolute_path)
                location = f"{gps_data['latitude'] if gps_data else '未知'}, {gps_data['longitude'] if gps_data else '未知'}"

                for label in labels:
                    records.append({
                        'time': result.detect_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'location': location,
                        'image_name': original_image_name,
                        'result_image_name': result_image_name,
                        'defect_type': label['label'],
                        'image_path': result.detect_result_image_name,
                        'original_image_path': image.image_relative_path,
                        'project_short_name': project.project_short_name,
                        'inspection_name': inspection.inspection_name
                    })
            except Exception as e:
                current_app.logger.error(f"处理检测结果时出错: {e}")
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
        current_app.logger.error(f"获取检测结果时出错: {e}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/image/<path:filename>')
def get_image(filename):
    """
    Optimized route to get an image by its filename.
    It directly queries the database instead of walking the filesystem.
    """
    try:
        # Query the database for the image record.
        # We assume the filename is unique for simplicity, as the old code did.
        image_record = Image.query.filter_by(image_name=filename).first()

        if not image_record:
            return jsonify({'success': False, 'message': '图片在数据库中未找到'}), 404

        image_path = image_record.image_absolute_path

        if not os.path.exists(image_path):
            current_app.logger.error(f"数据库中的图片路径不存在: {image_path}")
            return jsonify({'success': False, 'message': '图片文件不存在'}), 404

        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        current_app.logger.error(f"获取图片时出错: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/projects/<path:filename>')
def project_files(filename):
    """More robust file serving for project files."""
    try:
        filename = unquote(filename).replace('\\', '/')
        base_dir = current_app.root_path
        file_path = os.path.normpath(os.path.join(base_dir, 'Projects', filename))

        projects_dir = os.path.join(base_dir, 'Projects')
        if not os.path.abspath(file_path).startswith(os.path.abspath(projects_dir)):
            return "禁止访问", 403

        if not os.path.isfile(file_path):
            current_app.logger.error(f"文件未找到: {file_path}")
            return "文件未找到", 404

        return send_file(file_path)
    except Exception as e:
        current_app.logger.error(f"处理文件请求时出错: {e}")
        return "服务器错误", 500
