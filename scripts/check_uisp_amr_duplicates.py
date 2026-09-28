from collections import defaultdict

from app.integrations.uisp import UISPReadClient, device_amr_code


duplicates: dict[str, list[tuple[str, str]]] = defaultdict(list)
for device in UISPReadClient().list_devices():
    identity = device.get("identification") or {}
    if identity.get("role") != "station":
        continue
    name = str(identity.get("displayName") or identity.get("name") or "")
    code = device_amr_code(name)
    if code:
        duplicates[code].append((name, str(identity.get("mac") or "")))

repeated = {code: items for code, items in duplicates.items() if len(items) > 1}
print(f"CPE con código AMR: {len(duplicates)}")
print(f"Códigos repetidos: {len(repeated)}")
for code, items in sorted(repeated.items(), key=lambda item: int(item[0][3:])):
    print(code)
    for name, mac in items:
        print(f"  - {name} [{mac}]")
