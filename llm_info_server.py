from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Health Demo LLM Info Server")

# Allow the demo UI (running on localhost) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo only; tighten in real deployments
    allow_credentials=True,
    allow_methods=["*"]
    ,
    allow_headers=["*"],
)


@app.get("/llm-info")
async def llm_info():
    """Return simple metadata about the backing LLM / orchestration.

    This is a mock endpoint for the demo UI so that calls to /llm-info
    on localhost:8000 succeed even if no real LLM metadata service exists.
    """
    return {
        "model_name": "demo-health-llm",
        "status": "ok",
        "provider": "local-fastapi",
        "notes": "Mock /llm-info endpoint for the Health demo dashboard.",
    }


@app.get("/health")
async def health():
    """Basic healthcheck for the LLM info server."""
    return {"status": "ok"}


if __name__ == "__main__":
    # Helpful for running directly with `python llm_info_server.py`,
    # but in most cases you will run via:
    #   uvicorn llm_info_server:app --host 127.0.0.1 --port 8000 --reload
    import uvicorn

    uvicorn.run(
        "llm_info_server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
