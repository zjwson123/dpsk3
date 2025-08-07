from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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
