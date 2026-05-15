import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
realpath = os.path.realpath(backend_dir)

print(f"backend_dir: {backend_dir}")
print(f"realpath: {realpath}")
print(f"sys.path before: {sys.path[:3]}")

if realpath not in sys.path:
    sys.path.insert(0, realpath)

print(f"sys.path after: {sys.path[:3]}")
print(f"knowledge exists: {os.path.exists(os.path.join(realpath, 'knowledge'))}")

if __name__ == "__main__":
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="0.0.0.0", port=8000)