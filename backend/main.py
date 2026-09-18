import sys
from pathlib import Path

# Ensure backend root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.documents import router as documents_router
from api.extraction import router as extraction_router
from api.graph import router as graph_router


app = FastAPI(
    title="CrimeGraph API",
    description="Investigation Knowledge Graph Backend for FIR Analysis",
    version="0.1.0",
)

# Configure CORS for local frontend development
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount endpoints
app.include_router(documents_router)
app.include_router(extraction_router)
app.include_router(graph_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "crimegraph-backend"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
