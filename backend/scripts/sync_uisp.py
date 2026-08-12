# Importing the application registers every model used by the shared metadata
# before the standalone scheduler opens a database session.
import app.main  # noqa: F401

from app.db.session import SessionLocal
from app.integrations.uisp import UISPReadClient, sync_devices


def main() -> None:
    with SessionLocal() as db:
        result = sync_devices(db, UISPReadClient().list_devices())
    print(result)


if __name__ == "__main__":
    main()
