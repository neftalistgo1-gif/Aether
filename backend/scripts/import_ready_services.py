"""Import reviewed migration services without creating customer accounts.

This is intentionally a one-time, explicit command. It only accepts the
prepared JSON file and creates pending services so no network action is
triggered by the import.
"""

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.plan import Plan, PlanPrice, PlanStatus
from app.models.service import Service, ServiceEvent, ServiceEventType, ServiceStatus
from app.services.audit import record_audit_event

PLANS = {
    "15 Mbps": {"speed": "15 Mbps", "price": Decimal("350.00")},
    "25 Mbps": {"speed": "25 Mbps", "price": Decimal("550.00")},
    "35 Mbps": {"speed": "35 Mbps", "price": Decimal("650.00")},
}


def load_candidates(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("The import file must contain a list of services")
    return data


def ensure_plans(db) -> dict[str, Plan]:
    result: dict[str, Plan] = {}
    for name, config in PLANS.items():
        plan = db.scalar(select(Plan).where(Plan.name == name))
        if plan is None:
            plan = Plan(
                name=name,
                speed=config["speed"],
                description="Plan oficial importado de la operacion AMR.",
                status=PlanStatus.active,
            )
            plan.prices.append(
                PlanPrice(
                    monthly_price=config["price"],
                    valid_from=date.today(),
                    changed_by="Migracion Aether",
                    reason="Catalogo inicial de planes oficiales",
                )
            )
            db.add(plan)
            db.flush()
        elif plan.status != PlanStatus.active or plan.current_price != config["price"]:
            raise ValueError(
                f"Existing plan {name!r} does not match the approved catalog"
            )
        result[name] = plan
    return result


def import_services(candidates: list[dict[str, object]]) -> dict[str, int]:
    with SessionLocal() as db:
        plans = ensure_plans(db)
        existing_codes = set(db.scalars(select(Service.amr_code)).all())
        created = 0
        skipped = 0
        for candidate in candidates:
            amr_code = str(candidate["amr_code"])
            if amr_code in existing_codes:
                skipped += 1
                continue
            plan_name = str(candidate["plan_name"])
            plan = plans[plan_name]
            service = Service(
                amr_code=amr_code,
                plan_id=plan.id,
                address=str(candidate["address"]),
                plan_name=plan.name,
                monthly_price=plan.current_price,
                payment_day=int(candidate["payment_day"]),
                grace_days=5,
                status=ServiceStatus.pending,
            )
            service.events.append(
                ServiceEvent(
                    event_type=ServiceEventType.registered,
                    from_status=None,
                    to_status=ServiceStatus.pending,
                    reason="Migracion inicial: servicio sin cliente asignado",
                )
            )
            db.add(service)
            existing_codes.add(amr_code)
            created += 1
        db.flush()
        record_audit_event(
            db,
            actor="Migracion Aether",
            action="migration.reviewed_services_imported",
            entity_type="Service",
            entity_id="reviewed-services",
            reason="Importacion de registros marcados como Listo",
            after_data={
                "created_services": created,
                "skipped_existing_services": skipped,
                "plans": {name: str(plan.current_price) for name, plan in plans.items()},
                "customer_accounts_created": 0,
                "service_status": ServiceStatus.pending.value,
            },
        )
        db.commit()
    return {"created": created, "skipped": skipped, "plans": len(PLANS)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    print(json.dumps(import_services(load_candidates(args.input))))


if __name__ == "__main__":
    main()
