from app.db.session import SessionLocal
from app.services.mikrotik_traffic import collect_mikrotik_traffic


def main() -> None:
    db = SessionLocal()
    try:
        print(collect_mikrotik_traffic(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
