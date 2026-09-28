"""Importador del catálogo de Correos de México en formato .xls basado en HTML.

El archivo descargado por Correos de México usa extensión .xls pero contiene una
tabla HTML. Mantener esta lógica aquí hace explícito dónde ampliar Aether cuando
se agreguen otras ciudades: se sube el mismo formato desde Usuarios/administración
y se mezcla con el catálogo persistente, sin borrar las ciudades existentes.
"""
import csv
import io
import json
from html.parser import HTMLParser
from pathlib import Path

REQUIRED_COLUMNS = (
    "codigo postal", "estado", "municipio", "ciudad",
    "tipo de asentamiento", "asentamiento",
)


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.row=[]
        elif tag == "td" and self.row is not None: self.cell=[]
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append("".join(self.cell).strip()); self.cell=None
        elif tag == "tr" and self.row:
            self.rows.append(self.row); self.row=None


def _norm(value: str) -> str:
    return " ".join(value.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").lower().split())


def parse_catalog(content: bytes) -> list[dict[str, str]]:
    text = content.decode("cp1252", errors="replace")
    parser = _TableParser(); parser.feed(text)
    header_index = next((i for i, row in enumerate(parser.rows) if len(row) >= 6 and _norm(row[0]) == "codigo postal"), None)
    if header_index is None:
        raise ValueError("El archivo debe incluir las columnas Código Postal, Estado, Municipio, Ciudad, Tipo de Asentamiento y Asentamiento.")
    rows = parser.rows[header_index + 1:]
    catalog=[]
    for row in rows:
        if len(row) < 6 or not row[0].strip().isdigit() or not all(cell.strip() for cell in row[:6]): continue
        catalog.append({"postal_code": row[0].strip().zfill(5), "state": row[1].strip(), "municipality": row[2].strip(), "city": row[3].strip(), "settlement_type": row[4].strip(), "settlement_name": row[5].strip()})
    if not catalog: raise ValueError("No se encontraron códigos postales válidos en el archivo.")
    return catalog


def merge_catalog(path: Path, imported: list[dict[str, str]]) -> list[dict[str, str]]:
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    keyed = {(item["postal_code"], _norm(item["settlement_name"])): item for item in existing}
    for item in imported: keyed[(item["postal_code"], _norm(item["settlement_name"]))] = item
    result = sorted(keyed.values(), key=lambda item: (item["postal_code"], item["settlement_name"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
