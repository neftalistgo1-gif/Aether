"""Carga todos los modelos para que las pruebas SQLite tengan el esquema completo."""

# SQLAlchemy sólo registra una tabla después de importar su modelo. Las pruebas
# usan `Base.metadata.create_all()` con SQLite temporal, por eso deben cargar
# el conjunto completo antes de crear el esquema.
import app.models.access_point
import app.models.asset
import app.models.audit
import app.models.auth
import app.models.charge
import app.models.contract
import app.models.customer
import app.models.daily_operation
import app.models.equipment_recovery
import app.models.extension
import app.models.holder_transfer
import app.models.incident
import app.models.installation
import app.models.maintenance_inspection
import app.models.mikrotik
import app.models.network_assignment
import app.models.network_device
import app.models.notification
import app.models.payment
import app.models.payment_agreement
import app.models.payment_allocation
import app.models.plan
import app.models.service
import app.models.service_operations
import app.models.service_plan_change
import app.models.traffic_sample
