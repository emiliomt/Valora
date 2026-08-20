from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import assumptions, auth, deals, documents, exports, financials, model_versions, workspaces

app = FastAPI(
    title="Valora — Investment Research & Valuation Platform API",
    version="0.1.0",
    description=(
        "Deterministic, source-traceable underwriting API. Outputs are analytical model results, "
        "not investment, legal, tax, or accounting advice."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(deals.router)
app.include_router(documents.router)
app.include_router(financials.router)
app.include_router(assumptions.router)
app.include_router(model_versions.router)
app.include_router(exports.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
