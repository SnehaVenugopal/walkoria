from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from io import BytesIO
from decimal import Decimal
from django.utils import timezone
import barcode
from barcode.writer import ImageWriter


def generate_barcode(invoice_number):
    """Generate a Code128 barcode for the invoice number or fallback"""
    if not invoice_number:
        return None
    try:
        code128 = barcode.get_barcode_class('code128')
        rv = BytesIO()
        code128(str(invoice_number), writer=ImageWriter()).write(rv)
        rv.seek(0)
        return rv
    except Exception:
        return None


def generate_invoice_pdf(order_item, address):
    buffer = BytesIO()

    order = order_item.order
    inv_num = order_item.invoice_number if order_item.invoice_number else f"ORD-{order.order_number}-{order_item.id}"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Invoice {inv_num} – Walkoria",
        author="Walkoria",
    )

    elements = []
    styles = getSampleStyleSheet()

    style_normal  = styles['Normal']
    style_heading = styles['Heading1']
    style_right   = ParagraphStyle('Right',  parent=styles['Normal'], alignment=TA_RIGHT)
    style_center  = ParagraphStyle('Center', parent=styles['Normal'], alignment=TA_CENTER)
    style_bold    = ParagraphStyle('Bold',   parent=styles['Normal'], fontName='Helvetica-Bold')
    style_small   = ParagraphStyle('Small',  parent=styles['Normal'], fontSize=8)
    style_small_orange = ParagraphStyle('SmallOrange', parent=styles['Normal'],
                                        fontSize=8, textColor=colors.Color(0.8, 0.4, 0))

    # ── Header ──────────────────────────────────────────────────────────────
    company_info = [
        Paragraph("<b>Walkoria</b>", style_heading),
        Paragraph("Premium Footwear Store", style_normal),
        Paragraph("123 Fashion Street, Style District", style_normal),
        Paragraph("Mumbai, Maharashtra - 400001", style_normal),
        Paragraph("Email: support@walkoria.com", style_normal),
    ]

    invoice_info = [
        Paragraph("<b>INVOICE</b>", style_right),
        Paragraph(f"<b>Invoice No:</b> {inv_num}", style_right),
        Paragraph(f"<b>Order ID:</b> {order.order_number}", style_right),
        Paragraph(f"<b>Order Date:</b> {order.created_at.strftime('%d-%m-%Y')}", style_right),
        Paragraph(f"<b>Invoice Date:</b> {timezone.now().strftime('%d-%m-%Y')}", style_right),
    ]

    header_table = Table([[company_info, invoice_info]], colWidths=[100 * mm, 80 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 5 * mm))

    # Barcode
    bc_io = generate_barcode(inv_num)
    if bc_io:
        img = Image(bc_io, width=50 * mm, height=12 * mm)
        img.hAlign = 'RIGHT'
        elements.append(img)

    elements.append(Spacer(1, 10 * mm))

    # ── Ship To / Payment Info ───────────────────────────────────────────────
    user = order.user
    customer_name = user.name if user.name else (user.username if user.username else "Customer")

    ship_to = [
        Paragraph("<b>Ship To:</b>", style_bold),
        Paragraph(f"{address.full_name}", style_normal),
        Paragraph(f"{address.address}", style_normal),
        Paragraph(f"{address.city}, {address.state} - {address.pin_code}", style_normal),
        Paragraph(f"Phone: {address.mobile_no}", style_normal),
    ]

    pay_status_display = "Pending"
    if order_item.item_payment_status:
        pay_status_display = order_item.get_item_payment_status_display().title()
    elif order.payment_status:
        pay_status_display = "Paid"

    payment_info = [
        Paragraph("<b>Payment Details:</b>", style_bold),
        Paragraph(f"Customer: {customer_name}", style_normal),
        Paragraph(f"Method: {order.get_payment_method_display()}", style_normal),
        Paragraph(f"Status: {pay_status_display}", style_normal),
    ]

    info_table = Table([[ship_to, payment_info]], colWidths=[100 * mm, 80 * mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10 * mm))

    # ── Line Items Table ─────────────────────────────────────────────────────
    # Use get_effective_price() — same as the order detail page shows
    unit_price        = order_item.get_effective_price()
    qty               = order_item.quantity
    item_subtotal_val = unit_price * qty

    # Variant details
    variant = order_item.product_variant
    color = variant.color if variant.color and variant.color != 'N/A' else '-'
    size  = variant.size  if variant.size  and variant.size  != 'N/A' else '-'
    sku   = variant.product.id

    prod_cell = [
        Paragraph(f"<b>{variant.product.name}</b>", style_normal),
        Paragraph(f"SKU: {sku}", style_small),
    ]

    # Columns: Product | Qty | Color | Size | Unit Price | Subtotal
    headers = ["Product", "Qty", "Color", "Size", "Unit Price", "Subtotal"]
    row = [
        prod_cell,
        str(qty),
        color,
        size,
        f"₹{unit_price:,.2f}",
        f"₹{item_subtotal_val:,.2f}",
    ]

    table_data = [headers, row]

    # 180 mm total width
    col_widths = [62 * mm, 12 * mm, 22 * mm, 16 * mm, 28 * mm, 28 * mm - 0.5]

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), colors.Color(0.93, 0.93, 0.93)),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.black),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN',         (1, 0), (1, -1), 'CENTER'),   # Qty – center
        ('ALIGN',         (4, 0), (5, -1), 'RIGHT'),    # Prices – right
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 4 * mm))

    # ── Totals Section ───────────────────────────────────────────────────────
    totals_data = [
        ["Grand Total:", f"₹{item_subtotal_val:,.2f}"],
    ]

    totals_table = Table(totals_data, colWidths=[38 * mm, 32 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN',      (0, 0), (0, -1), 'LEFT'),
        ('ALIGN',      (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE',  (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, -1), (-1, -1), 6),
    ]))

    layout_t = Table([["", totals_table]], colWidths=[110 * mm, 70 * mm])
    layout_t.setStyle(TableStyle([
        ('ALIGN',        (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements.append(layout_t)
    elements.append(Spacer(1, 20 * mm))

    # ── Footer ───────────────────────────────────────────────────────────────
    elements.append(Paragraph("Thank you for shopping with Walkoria!", style_center))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(
        "This is a computer generated invoice and requires no signature.",
        style_small
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
