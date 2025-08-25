import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from decimal import Decimal
from reportlab.lib.utils import ImageReader
from django.utils import timezone
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph


def generate_barcode(invoice_number):
    """Generate a Code128 barcode for the invoice number"""
    code128 = barcode.get_barcode_class('code128')
    
    rv = BytesIO()
    code128(str(invoice_number), writer=ImageWriter()).write(rv)
    
    rv.seek(0)
    return ImageReader(rv)


def calculate_tax_details(price):
    """Calculate IGST and taxable value"""
    total = Decimal(str(price))
    igst_rate = Decimal('0.18')  # 18% IGST
    
    # Calculate backwards from total
    igst_amount = (total * igst_rate) / (1 + igst_rate)
    taxable_value = total - igst_amount
    
    return {
        'total': total,
        'igst_amount': round(igst_amount, 2),
        'taxable_value': round(taxable_value, 2),
        'igst_rate': 18  # Percentage
    }


def generate_invoice_pdf(order_item, address):
    """Generate PDF invoice for an order item"""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    # Company details (left side)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, height - 1*inch, "Walkoria")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, height - 1.2*inch, "Premium Footwear Store")
    p.drawString(1*inch, height - 1.4*inch, "123 Fashion Street, Style District")
    p.drawString(1*inch, height - 1.6*inch, "Mumbai, Maharashtra, India - 400001")
    p.drawString(1*inch, height - 1.8*inch, "GSTIN: 27AAGCK4304E3ZP")

    # Invoice details (right side)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(5*inch, height - 1*inch, "Tax Invoice")
    p.setFont("Helvetica", 10)
    p.drawString(5*inch, height - 1.2*inch, f"Invoice Number: {order_item.invoice_number}")
    p.drawString(5*inch, height - 1.4*inch, f"Order Date: {order_item.order.created_at.strftime('%d-%m-%Y')}")
    p.drawString(5*inch, height - 1.6*inch, f"Invoice Date: {timezone.now().strftime('%d-%m-%Y')}")

    # Add barcode (right side)
    barcode_image = generate_barcode(order_item.invoice_number)
    p.drawImage(barcode_image, 5*inch, height - 2.4*inch, width=2*inch, height=0.5*inch)

    # Shipping Address
    y = height - 3*inch
    address = address
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1*inch, y, "Ship To:")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, y - 0.2*inch, address.full_name)
    p.drawString(1*inch, y - 0.4*inch, address.address)
    p.drawString(1*inch, y - 0.6*inch, f"{address.city}, {address.state}")
    p.drawString(1*inch, y - 0.8*inch, f"PIN: {address.pin_code}")
    p.drawString(1*inch, y - 1*inch, f"Phone: {address.mobile_no}")

    # Table Header
    y = height - 4.5*inch
    p.setFont("Helvetica-Bold", 10)
    col1_x = 1*inch      # Title
    col2_x = 4.5*inch    # Qty
    col3_x = 5*inch      # Price
    col4_x = 5.8*inch    # Discount
    col5_x = 6.5*inch    # Total

    # Draw column headers
    p.drawString(col1_x, y, "Product")
    p.drawString(col2_x, y, "Qty")
    p.drawString(col3_x, y, "Price")
    p.drawString(col4_x, y, "Discount")
    p.drawString(col5_x, y, "Total")

    # Line under header
    y -= 0.2*inch
    p.line(1*inch, y, 7.5*inch, y)

    # Function to format currency with proper alignment
    def draw_amount(x, y, amount, right_align=True):
        amount_str = f"₹{amount:,.2f}"
        if right_align:
            string_width = p.stringWidth(amount_str, "Helvetica", 10)
            x = x - string_width
        p.drawString(x, y, amount_str)

    # Item details
    y -= 0.3*inch
    p.setFont("Helvetica", 10)
    tax_details = calculate_tax_details(order_item.price * order_item.quantity)
    
    # Product title with wrapping
    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        'Normal',
        fontName='Helvetica',
        fontSize=10,
        leading=12,
    )
    product_name = Paragraph(order_item.product_variant.product.name, style)
    w, h = product_name.wrap(3*inch, 10*inch)
    product_name.drawOn(p, col1_x, y - h)
    
    # Draw tax details under the product name
    p.setFont("Helvetica", 9)
    p.drawString(col1_x, y - h - 0.2*inch, f"Taxable Value: ₹{tax_details['taxable_value']:,.2f}")
    p.drawString(col1_x, y - h - 0.4*inch, f"IGST ({tax_details['igst_rate']}%): ₹{tax_details['igst_amount']:,.2f}")
    
    # Draw other columns
    p.setFont("Helvetica", 10)
    p.drawString(col2_x, y, str(order_item.quantity))
    draw_amount(col3_x + 0.7*inch, y, int(order_item.price) * order_item.quantity)
    p.drawString(col4_x, y, "0.00")
    draw_amount(col5_x + 0.7*inch, y, tax_details['total'])

    # Total section
    y = y - h - 0.8*inch
    p.line(1*inch, y, 7.5*inch, y)
    y -= 0.3*inch
    p.setFont("Helvetica-Bold", 10)
    p.drawString(5.5*inch, y, "Grand Total:")
    draw_amount(7.2*inch, y, tax_details['total'])

    # Footer
    p.setFont("Helvetica", 8)
    p.drawString(1*inch, 1*inch, "This is a computer generated invoice")
    p.drawString(6*inch, 1*inch, "Authorized Signatory")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer.getvalue()
