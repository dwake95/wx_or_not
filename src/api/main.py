"""
Weather Model Selector - Dashboard API

FastAPI application for monitoring system health and verification metrics.
"""
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api import dashboard

# Initialize FastAPI app
app = FastAPI(
    title="Weather Model Selector Dashboard",
    description="Monitoring and visualization for forecast verification system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])

# Mount static files
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Root endpoint serves dashboard HTML
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve main dashboard page."""
    templates_dir = Path(__file__).parent.parent.parent / "templates"
    dashboard_html = templates_dir / "dashboard.html"

    if dashboard_html.exists():
        return dashboard_html.read_text()
    else:
        return """
        <html>
            <head><title>Weather Model Selector</title></head>
            <body>
                <h1>Weather Model Selector Dashboard</h1>
                <p>Dashboard UI is being set up...</p>
                <p><a href="/api/docs">API Documentation</a></p>
            </body>
        </html>
        """

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "service": "weather-model-selector",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
