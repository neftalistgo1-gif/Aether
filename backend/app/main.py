
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.dependencies.auth import require_authorized_user
from app.api.v1.endpoints.audit import router as audit_router
from app.api.v1.endpoints.assets import router as assets_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.charges import router as charges_router
from app.api.v1.endpoints.contracts import router as contracts_router
from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.daily_operations import (
    router as daily_operations_router,
)
from app.api.v1.endpoints.equipment_recovery import (
    router as equipment_recovery_router,
)
from app.api.v1.endpoints.extensions import router as extensions_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.holder_transfers import (
    router as holder_transfers_router,
)
from app.api.v1.endpoints.incidents import router as incidents_router
from app.api.v1.endpoints.installations import router as installations_router
from app.api.v1.endpoints.maintenance_inspections import (
    router as maintenance_inspections_router,
)
from app.api.v1.endpoints.mikrotik import router as mikrotik_router
from app.api.v1.endpoints.network_assignments import (
    router as network_assignments_router,
)
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.payments import router as payments_router
from app.api.v1.endpoints.plans import router as plans_router
from app.api.v1.endpoints.payment_allocations import (
    router as payment_allocations_router,
)
from app.api.v1.endpoints.payment_agreements import (
    router as payment_agreements_router,
)
from app.api.v1.endpoints.postal_codes import router as postal_codes_router
from app.api.v1.endpoints.service_operations import (
    router as service_operations_router,
)
from app.api.v1.endpoints.service_plan_changes import (
    router as service_plan_changes_router,
)
from app.api.v1.endpoints.services import router as services_router

app = FastAPI(
    title="Aether API",
    description="Backend principal de Aether para Servicios AMR.",
    version="0.1.0",
)

protected = [Depends(require_authorized_user)]

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(daily_operations_router, dependencies=protected)
app.include_router(notifications_router, dependencies=protected)
app.include_router(audit_router, dependencies=protected)
app.include_router(incidents_router, dependencies=protected)
app.include_router(installations_router, dependencies=protected)
app.include_router(holder_transfers_router, dependencies=protected)
app.include_router(customers_router, dependencies=protected)
app.include_router(contracts_router, dependencies=protected)
app.include_router(services_router, dependencies=protected)
app.include_router(assets_router, dependencies=protected)
app.include_router(charges_router, dependencies=protected)
app.include_router(payments_router, dependencies=protected)
app.include_router(plans_router, dependencies=protected)
app.include_router(payment_allocations_router, dependencies=protected)
app.include_router(payment_agreements_router, dependencies=protected)
app.include_router(postal_codes_router, dependencies=protected)
app.include_router(extensions_router, dependencies=protected)
app.include_router(network_assignments_router, dependencies=protected)
app.include_router(service_operations_router, dependencies=protected)
app.include_router(service_plan_changes_router, dependencies=protected)
app.include_router(equipment_recovery_router, dependencies=protected)
app.include_router(maintenance_inspections_router, dependencies=protected)
app.include_router(mikrotik_router, dependencies=protected)


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


frontend_directory = Path(__file__).resolve().parents[2] / "frontend"
if frontend_directory.is_dir():
    app.mount(
        "/app",
        StaticFiles(directory=frontend_directory, html=True),
        name="frontend",
    )
