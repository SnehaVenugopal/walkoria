from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
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

def calculate_tax_details(amount):
    """Calculate IGST and taxable value from inclusive amount"""
    total = Decimal(str(amount))
    igst_rate = Decimal('0.18') 
    igst_amount = (total * igst_rate) / (1 + igst_rate)
    taxable_value = total - igst_amount
    return {
        'total': total,
        'igst_amount': round(igst_amount, 2),
        'taxable_value': round(taxable_value, 2),
        'igst_rate': 18
    }

def generate_invoice_pdf(order_item, address):
    buffer = BytesIO()
    # A4 width is 210mm. Margins 15mm left/right -> 180mm usable width.
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    style_normal = styles['Normal']
    style_heading = styles['Heading1']
    style_right = ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT)
    style_center = ParagraphStyle('Center', parent=styles['Normal'], alignment=TA_CENTER)
    style_bold = ParagraphStyle('Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
    style_small = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)

    # --- Data Preparation ---
    order = order_item.order
    # Fallback for invoice number if None
    inv_num = order_item.invoice_number if order_item.invoice_number else f"ORD-{order.order_number}-{order_item.id}"
    
    # --- Header Section ---
    # Left: Company Info
    company_info = [
        Paragraph("<b>Walkoria</b>", style_heading),
        Paragraph("Premium Footwear Store", style_normal),
        Paragraph("123 Fashion Street, Style District", style_normal),
        Paragraph("Mumbai, Maharashtra - 400001", style_normal),
        Paragraph("GSTIN: 27AAGCK4304E3ZP", style_normal),
        Paragraph(f"Email: support@walkoria.com", style_normal),
    ]
    
    # Right: Invoice Details
    invoice_info = [
        Paragraph("<b>TAX INVOICE</b>", style_right),
        Paragraph(f"<b>Invoice No:</b> {inv_num}", style_right),
        Paragraph(f"<b>Order ID:</b> {order.order_number}", style_right),
        Paragraph(f"<b>Order Date:</b> {order.created_at.strftime('%d-%m-%Y')}", style_right),
        Paragraph(f"<b>Invoice Date:</b> {timezone.now().strftime('%d-%m-%Y')}", style_right),
    ]
    
    # Header Table
    header_data = [[company_info, invoice_info]]
    header_table = Table(header_data, colWidths=[100*mm, 80*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 5*mm))
    
    # Barcode (Right aligned)
    bc_io = generate_barcode(inv_num)
    if bc_io:
        img = Image(bc_io, width=50*mm, height=12*mm)
        img.hAlign = 'RIGHT'
        elements.append(img)
    
    elements.append(Spacer(1, 10*mm))
    
    # --- Addresses and Payment Info ---
    
    # Ship To Address
    ship_to = [
        Paragraph("<b>Ship To:</b>", style_bold),
        Paragraph(f"{address.full_name}", style_normal),
        Paragraph(f"{address.address}", style_normal),
        Paragraph(f"{address.city}, {address.state} - {address.pin_code}", style_normal),
        Paragraph(f"Phone: {address.mobile_no}", style_normal),
    ]
    
    # Payment Info
    pay_status_display = "Pending"
    if order_item.item_payment_status:
        pay_status_display = order_item.get_item_payment_status_display().title()
    elif order.payment_status:
        pay_status_display = "Paid"
        
    payment_info = [
        Paragraph("<b>Payment Details:</b>", style_bold),
        Paragraph(f"Method: {order.get_payment_method_display()}", style_normal),
        Paragraph(f"Status: {pay_status_display}", style_normal),
    ]
    
    info_data = [[ship_to, payment_info]]
    info_table = Table(info_data, colWidths=[100*mm, 80*mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))
    
    # --- Line Items Table ---
    
    # Calculations
    unit_price = order_item.price # Original Price/Unit
    qty = order_item.quantity
    item_subtotal_val = unit_price * qty
    
    # Discount
    total_order_discount = order.subtotal - order.total_amount
    if order.subtotal > 0 and total_order_discount > 0:
        discount_share = (item_subtotal_val / order.subtotal) * total_order_discount
    else:
        discount_share = Decimal('0')
    
    net_total = item_subtotal_val - discount_share
    
    # Product Meta
    sku = order_item.product_variant.product.id # Using ID as SKU if SKU doesn't exist
    variant_text = f"Color: {order_item.product_variant.color} | Size: {order_item.product_variant.size}"
    
    # Table Header
    headers = ["Product", "Qty", "Price", "Discount", "Total"]
    
    # Table Row Content
    prod_cell = [
        Paragraph(f"<b>{order_item.product_variant.product.name}</b>", style_normal),
        Paragraph(variant_text, style_small),
        Paragraph(f"SKU: {sku}", style_small),
    ]
    
    row = [
        prod_cell,
        str(qty),
        f"₹{unit_price:,.2f}",
        f"₹{discount_share:,.2f}",
        f"₹{net_total:,.2f}"
    ]
    
    table_data = [headers, row]
    
    # Column Widths (Total 180mm)
    col_widths = [80*mm, 15*mm, 28*mm, 28*mm, 29*mm]
    
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.Color(0.95, 0.95, 0.95)), # Header BG
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'), # Default Left
        ('ALIGN', (1,0), (-1,-1), 'CENTER'), # Qty Center
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'), # Numbers Right
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 4*mm))
    
    # --- Totals Section ---
    tax_info = calculate_tax_details(net_total)
    
    # Totals Table (aligned right)
    totals_data = [
        ["Subtotal:", f"₹{item_subtotal_val:,.2f}"],
        ["Discount:", f"- ₹{discount_share:,.2f}"],
        ["Taxable Value:", f"₹{tax_info['taxable_value']:,.2f}"],
        ["IGST (18%):", f"₹{tax_info['igst_amount']:,.2f}"],
        ["Grand Total:", f"₹{net_total:,.2f}"],
    ]
    
    totals_table = Table(totals_data, colWidths=[35*mm, 30*mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'LEFT'), # Labels Left
        ('ALIGN', (1,0), (1,-1), 'RIGHT'), # Values Right
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), # Bold Grand Total
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black), # Line above total
        ('TOPPADDING', (0,-1), (-1,-1), 6),
    ]))
    
    # Layout Table to push totals to right
    # Col 1: Empty, Col 2: Totals
    layout_data = [["", totals_table]]
    layout_t = Table(layout_data, colWidths=[115*mm, 65*mm])
    layout_t.setStyle(TableStyle([
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    elements.append(layout_t)
    elements.append(Spacer(1, 20*mm))
    
    # --- Footer ---
    elements.append(Paragraph("Thank you for shopping with Walkoria!", style_center))
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("This is a computer generated invoice and requires no signature.", style_small))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
