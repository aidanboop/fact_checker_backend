# /home/ubuntu/fact_checker_backend/src/main.py
import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
# Remove or comment out unused user model and blueprint if not needed for this app
# from src.models.user import db 
# from src.routes.user import user_bp
from src.routes.verify_api import verify_bp # Import the new blueprint

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT_factchecker'

# Register the new blueprint for the verification API
app.register_blueprint(verify_bp, url_prefix='/api')

# The default user_bp is not used in this project, so it's commented out.
# app.register_blueprint(user_bp, url_prefix='/api')

# Database functionality is not required for this specific app as per current design
# app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USERNAME', 'root')}:{os.getenv('DB_PASSWORD', 'password')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'mydb')}"
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# db.init_app(app)
# with app.app_context():
#     db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            # For a pure API backend, we might not need to serve index.html
            # Or we can return a simple API status message
            return jsonify({"status": "Fact Checker API is running"}), 200

if __name__ == '__main__':
    # Ensure the app runs in an async-friendly way if using asyncio in routes
    # For Flask 2.x and above, it handles async views automatically.
    # For older versions or specific configurations, you might need `nest_asyncio` or similar.
    # The current Flask version in the template (3.1.0) should support async views.
    app.run(host='0.0.0.0', port=5000, debug=True)

