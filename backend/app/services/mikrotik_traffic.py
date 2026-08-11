import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.mikrotik import RouterOSRestClient
from app.models.mikrotik import MikrotikRouter
from app.models.traffic_sample import MikrotikTrafficSample


def traffic_interface_name(router: MikrotikRouter) -> str | None:
    return os.getenv(
        f"MIKROTIK_{router.credential_key.upper()}_TRAFFIC_INTERFACE",
        "LAN",
    )


def counter_value(source: dict, field_name: str) -> int:
    try:
        return int(source.get(field_name, 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"MikroTik interface counter is invalid: {field_name}") from exc


def collect_mikrotik_traffic(db: Session) -> dict[str, int]:
    collected = skipped = 0
    captured_at = datetime.now(UTC)
    for router in db.scalars(select(MikrotikRouter).order_by(MikrotikRouter.name)):
        interface_name = traffic_interface_name(router)
        if not interface_name:
            skipped += 1
            continue
        source = RouterOSRestClient(router, monitor=True).get_interface_stats(interface_name)
        rx_bytes = counter_value(source, "rx-byte")
        tx_bytes = counter_value(source, "tx-byte")
        previous = db.scalar(
            select(MikrotikTrafficSample)
            .where(
                MikrotikTrafficSample.router_id == router.id,
                MikrotikTrafficSample.interface_name == interface_name,
            )
            .order_by(MikrotikTrafficSample.captured_at.desc())
        )
        rx_bps = tx_bps = 0.0
        if previous is not None:
            elapsed = (captured_at - previous.captured_at).total_seconds()
            if elapsed > 0 and rx_bytes >= previous.rx_bytes and tx_bytes >= previous.tx_bytes:
                rx_bps = (rx_bytes - previous.rx_bytes) * 8 / elapsed
                tx_bps = (tx_bytes - previous.tx_bytes) * 8 / elapsed
        db.add(MikrotikTrafficSample(
            router_id=router.id,
            interface_name=interface_name,
            captured_at=captured_at,
            rx_bytes=rx_bytes,
            tx_bytes=tx_bytes,
            rx_bps=rx_bps,
            tx_bps=tx_bps,
        ))
        collected += 1
    db.commit()
    return {"collected": collected, "skipped": skipped}
