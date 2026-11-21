import io

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Invoice


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """
    Generates an official Spanish invoice PDF (Factura Ordinaria) in compliance
    with Real Decreto 1619/2012, de 30 de noviembre.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # Palette
    color_ink = colors.HexColor("#0D0F14")
    color_vermilion = colors.HexColor("#E8392B")
    colors.HexColor("#F4EFE6")
    color_muted = colors.HexColor("#64748B")

    # Typography styles
    style_logo = ParagraphStyle(
        "InvoiceLogo",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=color_ink,
    )
    ParagraphStyle(
        "InvoiceH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=color_ink,
    )
    style_meta = ParagraphStyle(
        "InvoiceMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=color_muted,
    )
    style_bold_meta = ParagraphStyle(
        "InvoiceBoldMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=color_ink,
    )
    style_table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=color_ink,
    )
    style_table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=color_ink,
    )

    company = settings.TINTORA_COMPANY

    # 1. Header: Brand & Invoice Meta
    header_data = [
        [
            Paragraph('<b>Tintora<font color="#E8392B">.</font></b><br/><font size="8" color="#64748B">Tinta que deja huella &middot; Taller de Getafe</font>', style_logo),
            Paragraph(
                f'<font color="#E8392B"><b>FACTURA ORDINARIA</b></font><br/>'
                f'<b>Nº Factura:</b> {invoice.invoice_number}<br/>'
                f'<b>Fecha Emisión:</b> {invoice.issue_date.strftime("%d/%m/%Y")}<br/>'
                f'<b>Ref. Pedido:</b> {invoice.order.order_number}',
                ParagraphStyle("InvoiceNum", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, alignment=2),
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[10 * cm, 8 * cm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=color_ink, spaceAfter=12))

    # 2. Fiscal Parties (Emisor & Receptor)
    order = invoice.order
    customer_name = order.company_name if order.company_name else f"{order.first_name} {order.last_name}"
    customer_nif = order.nif_cif
    customer_addr = f"{order.shipping_address_line1}, {order.shipping_postal_code} {order.shipping_city} ({order.shipping_province})"

    fiscal_data = [
        [
            Paragraph("<b>DATOS DEL EMISOR</b>", style_bold_meta),
            Paragraph("<b>DATOS DEL CLIENTE / RECEPTOR</b>", style_bold_meta),
        ],
        [
            Paragraph(
                f"<b>Razón Social:</b> {company['NAME']}<br/>"
                f"<b>NIF/CIF:</b> {company['NIF_CIF']}<br/>"
                f"<b>Domicilio:</b> {company['ADDRESS']}<br/>"
                f"<b>Email:</b> {company['EMAIL']}<br/>"
                f"<b>Registro Mercantil de Madrid</b>",
                style_meta,
            ),
            Paragraph(
                f"<b>Nombre / Razón:</b> {customer_name}<br/>"
                f"<b>NIF / CIF:</b> {customer_nif}<br/>"
                f"<b>Dirección:</b> {customer_addr}<br/>"
                f"<b>Email:</b> {order.email}<br/>"
                f"<b>Teléfono:</b> {order.phone}",
                style_meta,
            ),
        ],
    ]
    fiscal_table = Table(fiscal_data, colWidths=[9 * cm, 9 * cm])
    fiscal_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("PADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    story.append(fiscal_table)
    story.append(Spacer(1, 6 * mm))

    # 3. Itemized Products Table
    items_data = [
        [
            Paragraph("Concepto / Especificación", style_table_header),
            Paragraph("Tirada / Cant.", style_table_header),
            Paragraph("Precio Ud.", style_table_header),
            Paragraph("Total Línea (IVA incl.)", style_table_header),
        ]
    ]

    for item in order.items.all():
        opts_summary = ", ".join([f"{key}: {value}" for key, value in item.configuration.items()]) if item.configuration else ""
        proof_note = " &middot; <i>+Prueba física</i>" if item.request_proof else ""
        variant_note = f" · {item.variant_label}" if item.variant_label else ""
        desc = f"<b>{item.product_name}{variant_note}</b><br/><font color='#64748B'>{opts_summary}{proof_note}</font>"
        items_data.append(
            [
                Paragraph(desc, style_table_cell),
                Paragraph(str(item.quantity), style_table_cell),
                Paragraph(f"{item.unit_price:.4f}€", style_table_cell),
                Paragraph(f"{item.line_total:.2f}€", style_table_cell),
            ]
        )

    # Shipping Line if applicable
    if order.shipping_cost > 0:
        items_data.append(
            [
                Paragraph(f"<b>Gastos de Envío:</b> {order.shipping_method_name} ({order.courier})", style_table_cell),
                Paragraph("1", style_table_cell),
                Paragraph(f"{order.shipping_cost:.2f}€", style_table_cell),
                Paragraph(f"{order.shipping_cost:.2f}€", style_table_cell),
            ]
        )

    # Discount Line if coupon applied
    if order.discount_amount > 0:
        items_data.append(
            [
                Paragraph(f"<b>Descuento promocional:</b> Cupón {order.coupon_code}", style_table_cell),
                Paragraph("1", style_table_cell),
                Paragraph(f"-{order.discount_amount:.2f}€", style_table_cell),
                Paragraph(f"-{order.discount_amount:.2f}€", style_table_cell),
            ]
        )

    items_table = Table(items_data, colWidths=[9.5 * cm, 2.5 * cm, 3 * cm, 3 * cm])
    items_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, color_ink),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    # 4. Tax & Totals Breakdown (Base, IVA 21%, Total)
    totals_data = [
        [Paragraph("Base Imponible:", style_bold_meta), Paragraph(f"{invoice.taxable_base:.2f} €", style_bold_meta)],
        [Paragraph(f"Cuota IVA ({invoice.iva_percentage:.0f}%):", style_bold_meta), Paragraph(f"{invoice.iva_amount:.2f} €", style_bold_meta)],
        [
            Paragraph("<b>TOTAL FACTURA:</b>", ParagraphStyle("TotLbl", parent=style_bold_meta, fontSize=11, textColor=color_vermilion)),
            Paragraph(f"<b>{invoice.total:.2f} €</b>", ParagraphStyle("TotVal", parent=style_bold_meta, fontSize=11, textColor=color_vermilion)),
        ],
    ]
    totals_table = Table(totals_data, colWidths=[5 * cm, 3.5 * cm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 1, color_vermilion),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 8 * mm))

    # 5. Payment details & Legal Notice (Spanish RD 1619/2012)
    pay_status = "PAGADA" if invoice.is_paid or order.is_paid else "PENDIENTE DE PAGO"
    legal_text = (
        f"<b>Forma de Pago:</b> {order.get_payment_method_display()} &middot; Estado: <b>{pay_status}</b><br/>"
        f"<b>Datos bancarios:</b> Banco Santander &middot; IBAN: ES76 0049 1500 0512 3456 7890 &middot; SWIFT/BIC: BSCHESMMXXX<br/>"
        f"<font size='7' color='#94A3B8'>Factura emitida conforme al Real Decreto 1619/2012, de 30 de noviembre, por el que se aprueba el Reglamento "
        f"por el que se regulan las obligaciones de facturación en España. {company['NAME']} &middot; {company['ADDRESS']}.</font>"
    )
    story.append(Paragraph(legal_text, style_meta))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
