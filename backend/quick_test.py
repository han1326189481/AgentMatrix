import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
print('Testing...')
try:
    from app.main import app
    print('✅ Import successful!')
    import uvicorn
    print('🚀 Starting server on http://localhost:8000')
    uvicorn.run(app, host='0.0.0.0', port=8000)
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
