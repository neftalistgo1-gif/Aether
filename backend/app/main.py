
from fastapi import FastAPI

from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.services import router as services_router

app = FastAPI(
    title="Aether API",
    description="Backend principal de Aether para Servicios AMR.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(customers_router)
app.include_router(services_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Aether",
        "status": "online",
    }


@app.get("/about")
def about():
    return {
        "project": "Aether",
        "company": "servicios AMR",
        "city": "Reynosa, Tamaulipas ",
        "version": "0.1.0",
    }
