import uvicorn
import os
import sys

# Ensure backend root is on sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    print("Starting MediBud FastAPI Server...")
    print("Patient & Admin UI: http://localhost:8000")
    print("Interactive Swagger API Docs: http://localhost:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
