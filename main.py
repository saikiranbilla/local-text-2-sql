from dotenv import load_dotenv
load_dotenv()  # loads .env before any module reads os.getenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router
import uvicorn

app = FastAPI(title="Quill - Natural Language BI")
app.include_router(router, prefix="/api")

# Serve the frontend
app.mount("/static", StaticFiles(directory="ui"), name="static")

@app.get("/tables")
async def get_tables_root():
    from api.routes import orchestrator
    sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main';"
    df = orchestrator.engine.execute(sql)
    tables = df["table_name"].tolist() if "table_name" in df.columns else []
    return tables


@app.get("/")
async def serve_frontend():
    return FileResponse("ui/index.html")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
