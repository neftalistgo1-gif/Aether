from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import DATABASE_URL
from app.db.base import Base
from app.models.asset import Asset, AssetAssignment
from app.models.auth import AuthSession, OperatorUser, UserPermission
from app.models.audit import AuditEvent
from app.models.charge import Charge
from app.models.contract import Contract, ContractAmendment
from app.models.customer import Customer
from app.models.daily_operation import DailyOperationRun
from app.models.equipment_recovery import EquipmentRecovery
from app.models.extension import Extension
from app.models.holder_transfer import HolderTransfer
from app.models.incident import Incident, IncidentServiceImpact
from app.models.installation import Installation, InstallationScheduleChange
from app.models.maintenance_inspection import MaintenanceInspection
from app.models.mikrotik import MikrotikRouter, NetworkControlCommand
from app.models.network_assignment import NetworkAssignment
from app.models.notification import CustomerNotification
from app.models.payment import Payment, PaymentStatusEvent
from app.models.payment_allocation import CreditMovement, PaymentAllocation
from app.models.plan import Plan, PlanPrice
from app.models.service import Service, ServiceEvent, ServiceHolder
from app.models.service_plan_change import ServicePlanChange
from app.models.service_operations import Cancellation, Reactivation, Suspension

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
