import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const sourcePath = process.argv[2];
const destinationPath = process.argv[3] || "backend/private_storage/uisp_reference/services.json";
if (!sourcePath) throw new Error("Uso: node scripts/import_uisp_service_reference.mjs <archivo.xlsx>");

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));
const values = workbook.worksheets.getItem("Antenas activas").getUsedRange().values;
const headers = values[0];
const references = {};
const excelEpoch = Date.UTC(1899, 11, 30);
for (const row of values.slice(1)) {
  const source = Object.fromEntries(headers.map((header, index) => [header, row[index]]));
  const code = String(source.amr_code || "").trim().toUpperCase();
  if (!/^AMR\d{3,6}$/.test(code)) continue;
  const serial = Number(source.fecha_inicio);
  const startDate = Number.isFinite(serial)
    ? new Date(excelEpoch + Math.floor(serial) * 86400000).toISOString().slice(0, 10)
    : null;
  references[code] = {
    address: String(source.direccion || "").trim() || null,
    speed_mbps: Number.parseInt(String(source.paquete_bajada || source.paquete_subida || ""), 10) || null,
    start_date: startDate,
  };
}
await fs.mkdir(destinationPath.split(/[\\/]/).slice(0, -1).join("/"), { recursive: true });
await fs.writeFile(destinationPath, JSON.stringify(references, null, 2), "utf8");
console.log(`Referencia privada creada: ${Object.keys(references).length} códigos.`);
