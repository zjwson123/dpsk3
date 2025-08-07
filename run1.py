import os
from flask import Flask
from config import Config
from models import db
from routes import main_bp
from services import process_projects_folder

def create_app():
    print("create_app: START")
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(main_bp)

    @app.cli.command("process-projects")
    def process_projects_command():
        with app.app_context():
            try:
                process_projects_folder()
                print("项目数据导入成功！")
            except Exception as e:
                print(f"数据导入失败: {e}")

    with app.app_context():
        db.create_all()

    print("create_app: END")
    return app

if __name__ == '__main__':
    print("main: START")
    app = create_app()
    print("main: App created. About to run.")
    # Disabling debug mode as the Werkzeug reloader seems to cause a hang in this environment.
    app.run(host='0.0.0.0', port=8080, debug=False)
    print("main: App run finished.") # Should not be reached
