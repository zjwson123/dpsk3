import os
import json
import cv2
import shutil
from datetime import datetime
from ultralytics import YOLO
import piexif

from models import db, Project, Inspection, Image, Label, DetectResult, ImageLabelInfo

# Global variable to cache the model
_model = None

def get_yolo_model():
    """
    Loads the YOLO model lazily and caches it.
    Returns the model object or None if loading fails.
    ---
    NOTE: The YOLO("yolov8/best.pt") call is commented out
    because it causes the application to hang, likely due to a
    corrupted model file and an issue in the ultralytics library's
    error handling or initialization. This allows the web server
    to run for testing other functionality. The detection endpoint
    will not work.
    """
    global _model
    if _model is None:
        print("CRITICAL: YOLOv8 model loading is disabled due to a hanging issue with the model file.")
        return None
    return _model

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
    predefined_labels = [
        'Refineforcement exposure', 'Missing edge corner', 'Connection defect',
        'Crack leak', 'Slag defect', 'Hole defect'
    ]

    for label_name in predefined_labels:
        if not Label.query.filter_by(label_name=label_name).first():
            db.session.add(Label(label_name=label_name))
    db.session.commit()

    for project_dir in os.listdir(base_path):
        project_path = os.path.join(base_path, project_dir)
        if not os.path.isdir(project_path):
            continue

        project_short_name = project_dir
        overview_file = os.path.join(project_path, 'project_overview.txt')
        if not os.path.exists(overview_file):
            print(f"警告：项目 {project_dir} 缺少 project_overview.txt 文件")
            continue

        try:
            overview = parse_project_overview(overview_file)
        except Exception as e:
            print(f"解析 {overview_file} 失败: {e}")
            continue

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

        inspection_dir = os.path.join(project_path, 'inspection')
        if not os.path.exists(inspection_dir):
            print(f"警告：项目 {project_dir} 缺少 inspection 文件夹")
            continue

        for inspection_time_dir in os.listdir(inspection_dir):
            inspection_time_path = os.path.join(inspection_dir, inspection_time_dir)
            if not os.path.isdir(inspection_time_path):
                continue

            images_dir = os.path.join(inspection_time_path, 'images')
            if not os.path.exists(images_dir):
                print(f"警告：巡检 {inspection_time_dir} 缺少 images 文件夹")
                continue

            inspection_name = inspection_time_dir
            inspection = Inspection.query.filter_by(
                project_id=project.id,
                inspection_name=inspection_name
            ).first()

            if not inspection:
                img_count = sum(len([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]) for _, _, files in os.walk(images_dir))

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

            for root, _, files in os.walk(images_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        image_path = os.path.join(root, file)
                        relative_path = os.path.relpath(image_path, os.path.join(base_path, project_dir))

                        if not Image.query.filter_by(inspection_id=inspection.id, image_name=file).first():
                            image = Image(
                                image_name=file,
                                image_absolute_path=os.path.abspath(image_path),
                                image_relative_path=relative_path,
                                image_type=os.path.splitext(file)[1][1:].lower(),
                                inspection_id=inspection.id
                            )
                            db.session.add(image)
            db.session.commit()

def run_yolov8_detection(image_path):
    """
    Performs defect detection on a single image using the lazily-loaded YOLOv8 model.
    """
    model = get_yolo_model()
    if model is None:
        raise RuntimeError("YOLOv8 model is not available or failed to load.")

    results = model(image_path)

    # Process results
    labels = []
    for result in results:
        for box in result.boxes:
            label_name = model.names[int(box.cls[0])]
            confidence = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()

            labels.append({
                'label': label_name,
                'confidence': confidence,
                'xmin': xyxy[0],
                'ymin': xyxy[1],
                'xmax': xyxy[2],
                'ymax': xyxy[3],
            })

    # The annotated image can be plotted from results if needed, but run1.py does it.
    return {'labels': labels}


def save_detection_result(result, image_name, inspection_id):
    """
    Saves the detection result to the database and creates an annotated image.
    """
    try:
        label_mapping = {
            'Reinforcement exposure': '钢筋暴露', 'Missing edges and corners': '缺棱掉角',
            'Faulted slabs': '错台', 'Grout leakage': '拼缝漏浆',
            'Crack or leakage': '裂缝渗漏', 'Honeycomb': '蜂窝', 'Blowhole': '气泡'
        }
        label_colors = {
            '钢筋暴露': (0, 255, 0), '缺棱掉角': (0, 0, 255), '错台': (255, 0, 0),
            '拼缝漏浆': (10, 255, 255), '裂缝渗漏': (255, 0, 255), '蜂窝': (255, 255, 0),
            '气泡': (50, 0, 50)
        }
        default_color = (255, 255, 255)

        image = Image.query.filter_by(image_name=image_name, inspection_id=inspection_id).first()
        if not image:
            print(f"警告: 找不到图片记录 {image_name}")
            return

        inspection = Inspection.query.get(inspection_id)
        if not inspection:
            print(f"警告: 找不到巡检记录 {inspection_id}")
            return

        # Create results directory
        inspection_dir = os.path.dirname(os.path.dirname(image.image_absolute_path))
        results_dir = os.path.join(inspection_dir, 'results')
        os.makedirs(results_dir, exist_ok=True)

        original_img_path = image.image_absolute_path
        result_img_path = os.path.join(results_dir, f"result_{image_name}")

        img = cv2.imread(original_img_path)
        if img is not None:
            for label_info in result['labels']:
                chinese_label = label_mapping.get(label_info['label'], label_info['label'])
                x1, y1, x2, y2 = map(int, [label_info['xmin'], label_info['ymin'], label_info['xmax'], label_info['ymax']])
                color = label_colors.get(chinese_label, default_color)
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                cv2.putText(img, label_info['label'], (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.imwrite(result_img_path, img)
        else:
            print(f"警告: 无法读取图片 {original_img_path}")
            shutil.copy2(original_img_path, result_img_path)

        relative_path = os.path.join(
            'inspection', inspection.inspection_name, 'results', f"result_{image_name}"
        )

        detect_result = DetectResult(
            detect_result=json.dumps(result['labels'], ensure_ascii=False),
            detect_result_image_name=relative_path,
            detect_time=datetime.now(),
            inspection_id=inspection_id
        )
        db.session.add(detect_result)

        ImageLabelInfo.query.filter_by(image_id=image.id).delete()
        for label_info in result['labels']:
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

def read_gps_from_image(image_path):
    try:
        exif_dict = piexif.load(image_path)
        if "GPS" in exif_dict:
            gps_data = exif_dict["GPS"]
            lat = gps_data.get(piexif.GPSIFD.GPSLatitude, [0, 0, 0])
            lon = gps_data.get(piexif.GPSIFD.GPSLongitude, [0, 0, 0])

            def to_decimal(coord):
                return coord[0][0]/coord[0][1] + coord[1][0]/coord[1][1] / 60 + coord[2][0]/coord[2][1] / 3600

            return {'latitude': to_decimal(lat), 'longitude': to_decimal(lon)}
        return None
    except:
        return None
