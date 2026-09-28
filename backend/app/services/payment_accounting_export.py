from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO

import xlsxwriter

from app.models.payment import Payment, PaymentMethod, PaymentStatus


@dataclass(frozen=True)
class PaymentAccountingRow:
    """Context needed to turn a payment into a useful accounting row."""

    payment: Payment
    customer_name: str
    amr_code: str | None


METHOD_LABELS = {
    PaymentMethod.cash: "Efectivo",
    PaymentMethod.bank_transfer: "Transferencia bancaria",
    PaymentMethod.bank_deposit: "Depósito bancario",
    PaymentMethod.card: "Tarjeta",
    PaymentMethod.other: "Otro",
}

STATUS_LABELS = {
    PaymentStatus.pending: "Pendiente",
    PaymentStatus.verified: "Verificado",
    PaymentStatus.rejected: "Rechazado",
    PaymentStatus.cancelled: "Cancelado",
}


def _local_excel_datetime(value: datetime | None, timezone) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone)
    return value.astimezone(timezone).replace(tzinfo=None)


def _accounting_status(payment: Payment) -> str:
    if payment.applied_at is not None:
        return "Aplicado"
    if payment.status == PaymentStatus.verified:
        return "Por aplicar"
    if payment.status == PaymentStatus.pending:
        return "Por revisar"
    return "No procesado"


def _amount(payment: Payment) -> Decimal:
    return payment.confirmed_amount or payment.declared_amount


def build_payment_accounting_workbook(
    rows: list[PaymentAccountingRow],
    *,
    period_label: str,
    period_start: datetime,
    period_end: datetime,
    generated_at: datetime,
    timezone,
) -> bytes:
    """Create an Excel report without changing any payment records."""

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties(
        {
            "title": f"Archivo contable de pagos - {period_label}",
            "subject": "Resumen y movimientos del módulo de Pagos de Aether",
            "author": "Aether",
            "company": "Servicios AMR",
        }
    )

    navy = "#0B1D36"
    navy_soft = "#102A4C"
    cyan = "#49B9FF"
    white = "#FFFFFF"
    text = "#17324F"
    muted = "#60738D"
    green = "#DCFCE7"
    amber = "#FEF3C7"
    blue = "#DBEAFE"
    red = "#FEE2E2"

    title_format = workbook.add_format(
        {
            "bold": True,
            "font_size": 20,
            "font_color": white,
            "bg_color": navy,
            "align": "left",
            "valign": "vcenter",
        }
    )
    subtitle_format = workbook.add_format(
        {
            "font_color": muted,
            "font_size": 10,
            "text_wrap": True,
            "valign": "vcenter",
        }
    )
    section_format = workbook.add_format(
        {
            "bold": True,
            "font_color": white,
            "bg_color": navy_soft,
            "border": 0,
        }
    )
    label_format = workbook.add_format(
        {"bold": True, "font_color": text, "bg_color": "#EAF2FB"}
    )
    integer_format = workbook.add_format({"num_format": "0"})
    currency_format = workbook.add_format(
        {"num_format": '$#,##0.00;[Red]-$#,##0.00', "font_color": text}
    )
    date_format = workbook.add_format(
        {"num_format": "dd/mm/yyyy hh:mm", "font_color": text}
    )
    header_format = workbook.add_format(
        {
            "bold": True,
            "font_color": white,
            "bg_color": navy_soft,
            "border": 0,
            "text_wrap": True,
            "valign": "vcenter",
        }
    )
    status_formats = {
        "Aplicado": workbook.add_format({"bg_color": green, "font_color": "#166534"}),
        "Por revisar": workbook.add_format({"bg_color": amber, "font_color": "#92400E"}),
        "Por aplicar": workbook.add_format({"bg_color": blue, "font_color": "#1E40AF"}),
        "No procesado": workbook.add_format({"bg_color": red, "font_color": "#991B1B"}),
    }

    movement_rows = []
    totals = {
        "Total registrado": Decimal("0"),
        "Aplicado": Decimal("0"),
        "Por revisar": Decimal("0"),
        "Por aplicar": Decimal("0"),
        "No procesado": Decimal("0"),
    }
    counts = {key: 0 for key in totals}

    for item in rows:
        payment = item.payment
        accounting_status = _accounting_status(payment)
        amount = _amount(payment)
        totals["Total registrado"] += amount
        totals[accounting_status] += amount
        counts["Total registrado"] += 1
        counts[accounting_status] += 1
        movement_rows.append(
            [
                str(payment.id),
                _local_excel_datetime(payment.declared_at, timezone),
                _local_excel_datetime(payment.received_at, timezone),
                item.customer_name,
                item.amr_code or "",
                METHOD_LABELS.get(payment.method, payment.method.value),
                payment.reference or "",
                payment.origin_account_holder or "",
                float(payment.declared_amount),
                float(payment.confirmed_amount) if payment.confirmed_amount is not None else None,
                float(amount),
                accounting_status,
                STATUS_LABELS.get(payment.status, payment.status.value),
                _local_excel_datetime(payment.verified_at, timezone),
                _local_excel_datetime(payment.applied_at, timezone),
                payment.received_by,
                payment.verified_by or "",
                payment.applied_by or "",
                payment.notes or "",
                payment.verification_notes or "",
                payment.application_notes or "",
            ]
        )

    summary = workbook.add_worksheet("Resumen")
    summary.hide_gridlines(2)
    summary.set_tab_color(cyan)
    summary.set_column("A:A", 24)
    summary.set_column("B:B", 19)
    summary.set_column("C:C", 15)
    summary.set_column("D:F", 14)
    summary.set_row(0, 34)
    summary.set_row(3, 22)
    summary.set_row(4, 22)
    summary.merge_range("A1:F1", "Aether · Archivo contable de pagos", title_format)
    summary.write("A3", "Periodo", label_format)
    summary.write("B3", period_label.title())
    summary.write("A4", "Desde", label_format)
    summary.write_datetime("B4", _local_excel_datetime(period_start, timezone), date_format)
    summary.write("A5", "Hasta", label_format)
    summary.write_datetime(
        "B5",
        _local_excel_datetime(period_end - timedelta(seconds=1), timezone),
        date_format,
    )
    summary.write("D3", "Generado", label_format)
    summary.write_datetime("E3", _local_excel_datetime(generated_at, timezone), date_format)
    summary.merge_range(
        "C4:F5",
        "Los importes del resumen se calculan automáticamente a partir de la hoja Movimientos.",
        subtitle_format,
    )
    summary.write_row("A7", ["Concepto", "Importe", "Movimientos"], section_format)

    metrics = [
        ("Total registrado", None),
        ("Aplicado", "Aplicado"),
        ("Por revisar", "Por revisar"),
        ("Por aplicar", "Por aplicar"),
        ("No procesado", "No procesado"),
    ]
    first_data_excel_row = 3
    last_data_excel_row = len(movement_rows) + 2
    amount_range = f"Movimientos!$K${first_data_excel_row}:$K${last_data_excel_row}"
    status_range = f"Movimientos!$L${first_data_excel_row}:$L${last_data_excel_row}"

    for index, (label, status_label) in enumerate(metrics, start=7):
        summary.write(index, 0, label)
        if not movement_rows:
            amount_formula = "=0"
            count_formula = "=0"
        elif status_label is None:
            amount_formula = f"=SUM({amount_range})"
            count_formula = f"=COUNTA(Movimientos!$A${first_data_excel_row}:$A${last_data_excel_row})"
        else:
            amount_formula = f'=SUMIF({status_range},"{status_label}",{amount_range})'
            count_formula = f'=COUNTIF({status_range},"{status_label}")'
        summary.write_formula(index, 1, amount_formula, currency_format, float(totals[label]))
        summary.write_formula(index, 2, count_formula, integer_format, counts[label])

    summary.conditional_format("A9:C9", {"type": "no_blanks", "format": status_formats["Aplicado"]})
    summary.conditional_format("A10:C10", {"type": "no_blanks", "format": status_formats["Por revisar"]})
    summary.conditional_format("A11:C11", {"type": "no_blanks", "format": status_formats["Por aplicar"]})
    summary.conditional_format("A12:C12", {"type": "no_blanks", "format": status_formats["No procesado"]})
    summary.write("A14", "Criterio del periodo", label_format)
    summary.merge_range(
        "B14:F14",
        "Incluye pagos registrados en Aether dentro del mes seleccionado, según la hora de Reynosa.",
        subtitle_format,
    )
    summary.freeze_panes(7, 0)
    summary.set_landscape()
    summary.fit_to_pages(1, 1)
    summary.set_footer("&LAether · Servicios AMR&C&P de &N&RArchivo contable")

    movements = workbook.add_worksheet("Movimientos")
    movements.hide_gridlines(2)
    movements.set_tab_color(navy_soft)
    movements.freeze_panes(2, 5)
    movements.set_row(0, 30)
    movements.merge_range("A1:U1", f"Movimientos de pagos · {period_label.title()}", title_format)
    columns = [
        "ID de pago",
        "Fecha de pago",
        "Fecha de registro",
        "Cliente",
        "AMR",
        "Método",
        "Cuenta o referencia",
        "Titular de origen",
        "Importe declarado",
        "Importe confirmado",
        "Importe considerado",
        "Estado contable",
        "Estado del pago",
        "Fecha de verificación",
        "Fecha de aplicación",
        "Recibido por",
        "Verificado por",
        "Aplicado por",
        "Notas de recepción",
        "Notas de verificación",
        "Notas de aplicación",
    ]
    movements.write_row(1, 0, columns, header_format)
    for row_index, values in enumerate(movement_rows, start=2):
        movements.write_row(row_index, 0, values)
        for column_index in (1, 2, 13, 14):
            if values[column_index] is not None:
                movements.write_datetime(row_index, column_index, values[column_index], date_format)
        for column_index in (8, 9, 10):
            if values[column_index] is not None:
                movements.write_number(row_index, column_index, values[column_index], currency_format)

    if movement_rows:
        movements.add_table(
            1,
            0,
            len(movement_rows) + 1,
            len(columns) - 1,
            {
                "name": "MovimientosContables",
                "style": "Table Style Medium 2",
                "columns": [{"header": column} for column in columns],
            },
        )
        movements.conditional_format(
            2,
            11,
            len(movement_rows) + 1,
            11,
            {"type": "text", "criteria": "containing", "value": "Aplicado", "format": status_formats["Aplicado"]},
        )
        movements.conditional_format(
            2,
            11,
            len(movement_rows) + 1,
            11,
            {"type": "text", "criteria": "containing", "value": "Por revisar", "format": status_formats["Por revisar"]},
        )
        movements.conditional_format(
            2,
            11,
            len(movement_rows) + 1,
            11,
            {"type": "text", "criteria": "containing", "value": "Por aplicar", "format": status_formats["Por aplicar"]},
        )
        movements.conditional_format(
            2,
            11,
            len(movement_rows) + 1,
            11,
            {"type": "text", "criteria": "containing", "value": "No procesado", "format": status_formats["No procesado"]},
        )
    else:
        movements.autofilter(1, 0, 1, len(columns) - 1)

    movements.set_column("A:A", 38)
    movements.set_column("B:C", 19)
    movements.set_column("D:D", 28)
    movements.set_column("E:E", 12)
    movements.set_column("F:H", 22)
    movements.set_column("I:K", 18)
    movements.set_column("L:M", 18)
    movements.set_column("N:O", 19)
    movements.set_column("P:R", 20)
    movements.set_column("S:U", 30)
    movements.set_landscape()
    movements.fit_to_pages(1, 0)
    movements.repeat_rows(1)
    movements.set_footer("&LAether · Servicios AMR&C&P de &N&RMovimientos")

    workbook.close()
    return output.getvalue()
