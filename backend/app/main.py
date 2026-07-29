
from fastapi import FastAPI

from app.api.v1.endpoints.assets import router as assets_router
from app.api.v1.endpoints.charges import router as charges_router
from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.equipment_recovery import (
    router as equipment_recovery_router,
)
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.maintenance_inspections import (
    router as maintenance_inspections_router,
)
from app.api.v1.endpoints.network_assignments import (
    router as network_assignments_router,
)
from app.api.v1.endpoints.payments import router as payments_router
from app.api.v1.endpoints.service_operations import (
    router as service_operations_router,
)
from app.api.v1.endpoints.services import router as services_router

app = FastAPI(
    title="Aether API",
    description="Backend principal de Aether para Servicios AMR.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(customers_router)
app.include_router(services_router)
app.include_router(assets_router)
app.include_router(charges_router)
app.include_router(payments_router)
app.include_router(network_assignments_router)
app.include_router(service_operations_router)
app.include_router(equipment_recovery_router)
app.include_router(maintenance_inspections_router)


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
