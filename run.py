import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

config_name = os.environ.get("FLASK_ENV", "production")
app = create_app(config_name)

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = config_name == "development"
    print("="*40)
    print("  Boost Central demarre !")
    print(f"  http://{host}:{port}")
    print("="*40)
    app.run(host=host, port=port, debug=debug)
