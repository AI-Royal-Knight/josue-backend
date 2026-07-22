"""
PDF utilities for Purchase Orders.
- parse_po_pdf: extracts structured data from a supplier quotation PDF
- generate_branded_po_pdf: creates a clean branded PDF with company logo
"""

import re
import io
import os
from datetime import date


# ──────────────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_po_pdf(file_obj) -> dict:
    """
    Accepts a file-like object (Django InMemoryUploadedFile or bytes-IO).
    Returns a dict with:
      supplier_name, supplier_address, fao, quotation_number, your_ref,
      job_site_ref, quotation_date, line_items (list of dicts), grand_total,
      raw_text
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber is not installed. Run: pip install pdfplumber")

    file_obj.seek(0)
    result = {
        "supplier_name": "",
        "supplier_address": "",
        "fao": "",
        "quotation_number": "",
        "your_ref": "",
        "job_site_ref": "",
        "quotation_date": "",
        "line_items": [],
        "grand_total": "",
        "raw_text": "",
    }

    all_text_lines = []
    all_tables = []

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text_lines.extend(text.splitlines())
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)

    full_text = "\n".join(all_text_lines)
    result["raw_text"] = full_text

    # ── Prioritize table-based header extraction ─────────────────────────────
    # The header table has rows like ["Label:", None, "Value", None, "Address"]
    if all_tables:
        header_table = all_tables[0]
        for row in header_table:
            # Normalise the row: get col0 (label) and col2 (value)
            cells = [str(c or "").strip() for c in row]
            label = cells[0].lower().rstrip(":")
            value = cells[2] if len(cells) > 2 else ""

            if "to" == label and not result["supplier_name"]:
                # strip leading account/ref number like "7707Y07 - "
                cleaned = re.sub(r"^[A-Z0-9]{4,}\s*[-–]\s*", "", value).strip()
                result["supplier_name"] = cleaned
            elif "fao" == label:
                # value might be "JOHN 203 VALE ROAD" due to table column layout
                # take only the first token(s) that look like a name (no digits)
                name_part = re.match(r"^([A-Za-z]+(?:\s+[A-Za-z]+)?)", value)
                result["fao"] = name_part.group(1) if name_part else value
            elif "quotation number" == label:
                result["quotation_number"] = value
            elif "your ref" == label:
                result["your_ref"] = value
            elif "job/site ref" == label:
                # strip trailing phone numbers (e.g. " 01732 350022")
                job_clean = re.split(r"\s+0\d{4,}", value)[0].strip()
                result["job_site_ref"] = job_clean
            elif "quotation date" == label:
                date_match = re.search(r"\d{2}[/\-]\d{2}[/\-]\d{4}|\d{4}[/\-]\d{2}[/\-]\d{2}", value)
                result["quotation_date"] = date_match.group(0) if date_match else value

    # ── Fall back to text-line scanning if table didn't capture everything ───
    for line in all_text_lines:
        line = line.strip()

        # "To: 7707Y07 - MALCOLM BUILDING SERVICES LTD  WOLSELEY TONBRIDGE"
        m = re.match(r"^To:\s*(.+)", line, re.IGNORECASE)
        if m and not result["supplier_name"]:
            raw = m.group(1).strip()
            # strip address portion (after 2+ spaces or a tabular gap)
            part = re.split(r"\s{2,}", raw)[0].strip()
            # strip leading account/reference numbers like "7707Y07 - " or "12345 - "
            part = re.sub(r"^[A-Z0-9]{4,}\s*[-–]\s*", "", part).strip()
            result["supplier_name"] = part

        m = re.match(r"^FAO:\s*(.+)", line, re.IGNORECASE)
        if m and not result["fao"]:
            fao_raw = m.group(1).strip()
            result["fao"] = fao_raw.split("  ")[0].strip()

        m = re.match(r"^Quotation\s+(?:Number|No\.?):\s*(.+)", line, re.IGNORECASE)
        if m and not result["quotation_number"]:
            ref_match = re.search(r"[A-Z0-9|\-]+", m.group(1))
            result["quotation_number"] = ref_match.group(0) if ref_match else m.group(1).strip()

        m = re.match(r"^Your\s+Ref:\s*(.+)", line, re.IGNORECASE)
        if m and not result["your_ref"]:
            result["your_ref"] = m.group(1).strip()

        m = re.match(r"^Job/Site\s+Ref:\s*(.+)", line, re.IGNORECASE)
        if m and not result["job_site_ref"]:
            job_raw = m.group(1).strip()
            job_clean = re.split(r"\s{2,}", job_raw)[0].strip()
            result["job_site_ref"] = job_clean

        m = re.match(r"^Quotation\s+Date:\s*(.+)", line, re.IGNORECASE)
        if m:
            # grab only the date part (DD/MM/YYYY or YYYY-MM-DD), strip phone numbers etc.
            date_match = re.search(r"\d{2}[/\-]\d{2}[/\-]\d{4}|\d{4}[/\-]\d{2}[/\-]\d{2}", m.group(1))
            result["quotation_date"] = date_match.group(0) if date_match else m.group(1).strip()

    # ── Grand total ──────────────────────────────────────────────────────────
    m = re.search(r"Quotation\s+Total\s+[£$]?([\d,]+\.?\d*)", full_text, re.IGNORECASE)
    if m:
        result["grand_total"] = f"£{m.group(1)}"

    # ── Line items from table ─────────────────────────────────────────────────
    line_items = []
    for table in all_tables:
        # find header row
        header_idx = None
        for i, row in enumerate(table):
            cells = [str(c or "").strip() for c in row]
            if any("Cat No" in c or "Cat" in c for c in cells):
                header_idx = i
                break

        if header_idx is None:
            continue

        for row in table[header_idx + 1:]:
            if not row or not row[0]:
                continue
            cells = [str(c or "").strip() for c in row]
            cat_no = cells[0]
            # Skip section headers like "1 BEDROOM", totals etc.
            if not re.match(r"^[A-Z]\d+", cat_no):
                continue

            description = cells[1] if len(cells) > 1 else ""
            discount    = cells[3] if len(cells) > 3 else ""
            quantity    = cells[5] if len(cells) > 5 else ""
            unit_price  = cells[7] if len(cells) > 7 else ""
            total_value = cells[8] if len(cells) > 8 else ""

            line_items.append({
                "cat_no": cat_no,
                "description": description,
                "discount": discount,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_value": total_value,
            })

    result["line_items"] = line_items
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Branded PDF generation
# ──────────────────────────────────────────────────────────────────────────────

def generate_branded_po_pdf(parsed: dict, logo_path: str | None = None) -> bytes:
    """
    Generates a clean, compact branded Purchase Order PDF.
    Returns bytes of the PDF.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, HRFlowable, Image
        )
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    except ImportError:
        raise RuntimeError("reportlab is not installed. Run: pip install reportlab")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm,
    )

    W = A4[0] - 30*mm  # usable width

    styles = getSampleStyleSheet()

    # ── Custom styles ─────────────────────────────────────────────────────────
    h1 = ParagraphStyle("h1", fontSize=16, fontName="Helvetica-Bold",
                         textColor=colors.HexColor("#1e293b"), spaceAfter=2)
    sub = ParagraphStyle("sub", fontSize=8, fontName="Helvetica",
                          textColor=colors.HexColor("#64748b"), spaceAfter=0)
    label_style = ParagraphStyle("lbl", fontSize=7.5, fontName="Helvetica",
                                  textColor=colors.HexColor("#94a3b8"))
    value_style = ParagraphStyle("val", fontSize=8.5, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1e293b"))
    tbl_hdr = ParagraphStyle("th", fontSize=7.5, fontName="Helvetica-Bold",
                               textColor=colors.white, alignment=TA_CENTER)
    tbl_cell = ParagraphStyle("tc", fontSize=7.5, fontName="Helvetica",
                               textColor=colors.HexColor("#1e293b"))
    tbl_cell_r = ParagraphStyle("tcr", fontSize=7.5, fontName="Helvetica",
                                 textColor=colors.HexColor("#1e293b"), alignment=TA_RIGHT)
    total_style = ParagraphStyle("tot", fontSize=11, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#16a34a"), alignment=TA_RIGHT)
    footer_style = ParagraphStyle("ft", fontSize=6.5, fontName="Helvetica",
                                   textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)

    story = []

    # ── Header: logo + title ──────────────────────────────────────────────────
    brand_color = colors.HexColor("#1e3a5f")

    logo_cell = ""
    if logo_path and os.path.exists(logo_path):
        logo_img = Image(logo_path, width=50*mm, height=20*mm, kind="proportional")
        logo_img.hAlign = 'LEFT'
        logo_cell = logo_img
    else:
        logo_cell = Paragraph(
            "<font color='#1e3a5f'><b>PAYPARO</b></font>",
            ParagraphStyle("logo", fontSize=18, fontName="Helvetica-Bold",
                            textColor=brand_color)
        )

    title_block = [
        Paragraph("PURCHASE ORDER", h1),
        Spacer(1, 3*mm),
        Paragraph(f"Ref: {parsed.get('quotation_number', 'N/A')}", sub),
        Paragraph(f"Date: {parsed.get('quotation_date', date.today().strftime('%d/%m/%Y'))}", sub),
    ]

    header_tbl = Table(
        [[logo_cell, title_block]],
        colWidths=[W * 0.35, W * 0.65],
    )
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),  # Logo vertically centered
        ("VALIGN", (1, 0), (1, 0), "TOP"),     # Title block at the top
        ("ALIGN",  (1, 0), (1, 0),  "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width="100%", thickness=1.5, color=brand_color, spaceAfter=5))

    # ── Supplier + order info block ───────────────────────────────────────────
    def kv(label, value, style=None):
        return [
            Paragraph(label, label_style),
            Paragraph(str(value or "—"), style or value_style),
        ]

    info_data = [
        kv("SUPPLIER", parsed.get("supplier_name", "")),
        kv("FAO", parsed.get("fao", "")),
        kv("JOB / SITE REF", parsed.get("job_site_ref", "")),
        kv("YOUR REF", parsed.get("your_ref", "")),
    ]

    info_tbl = Table(info_data, colWidths=[W * 0.25, W * 0.75])
    info_tbl.setStyle(TableStyle([
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
        ("TOPPADDING",     (0, 0), (-1, -1), 1),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#e2e8f0"), spaceAfter=5))

    # ── Line items table ──────────────────────────────────────────────────────
    col_widths = [W * 0.10, W * 0.40, W * 0.10, W * 0.10, W * 0.15, W * 0.15]
    headers = ["Cat No", "Description", "Discount", "Qty", "Unit £", "Total £"]

    tbl_data = [[Paragraph(h, tbl_hdr) for h in headers]]

    items = parsed.get("line_items", [])
    for item in items:
        tbl_data.append([
            Paragraph(item.get("cat_no", ""), tbl_cell),
            Paragraph(item.get("description", ""), tbl_cell),
            Paragraph(item.get("discount", ""), tbl_cell_r),
            Paragraph(item.get("quantity", ""), tbl_cell_r),
            Paragraph(item.get("unit_price", ""), tbl_cell_r),
            Paragraph(item.get("total_value", ""), tbl_cell_r),
        ])

    if not items:
        tbl_data.append([Paragraph("No line items extracted", tbl_cell)] + [""] * 5)

    item_tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)
    item_tbl.setStyle(TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), brand_color),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    story.append(item_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Grand total ───────────────────────────────────────────────────────────
    grand_total = parsed.get("grand_total", "")
    if grand_total:
        total_tbl = Table(
            [[Paragraph(f"QUOTATION TOTAL: {grand_total}", total_style)]],
            colWidths=[W],
        )
        total_tbl.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (0, 0), "RIGHT"),
            ("BACKGROUND",    (0, 0), (0, 0), colors.HexColor("#f0fdf4")),
            ("TOPPADDING",    (0, 0), (0, 0), 5),
            ("BOTTOMPADDING", (0, 0), (0, 0), 5),
            ("LEFTPADDING",   (0, 0), (0, 0), 8),
            ("RIGHTPADDING",  (0, 0), (0, 0), 8),
            ("BOX",           (0, 0), (0, 0), 1, colors.HexColor("#16a34a")),
            ("ROUNDEDCORNERS", [2]),
        ]))
        story.append(total_tbl)

    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#e2e8f0"), spaceAfter=4))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "Prices are correct only as at the Quotation Date shown. "
        "This document is generated by Payparo and is subject to standard terms and conditions.",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()

def generate_quotation_pdf(quotation, logo_path=None) -> bytes:
    """
    Generates a PDF for a given Quotation instance and returns it as bytes.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()
    
    normal_style = styles["Normal"]
    normal_style.fontSize = 10
    normal_style.leading = 14

    title_style = ParagraphStyle(
        name="PO_Title",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        spaceAfter=15,
        textColor=colors.HexColor("#2C3E50"),
        alignment=TA_CENTER
    )

    meta_style = ParagraphStyle(
        name="PO_Meta",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#34495E")
    )

    elements = []

    # Logo
    if logo_path and os.path.exists(logo_path):
        try:
            logo = RLImage(logo_path)
            logo.drawWidth = 50*mm
            logo.drawHeight = 20*mm
            logo.hAlign = 'LEFT'
            elements.append(logo)
            elements.append(Spacer(1, 10*mm))
        except Exception:
            pass

    # Title
    elements.append(Paragraph("REQUEST FOR QUOTATION", title_style))
    
    project_name = quotation.project.project_name if quotation.project else "N/A"
    company_name = quotation.supplier.supplier.company_name if quotation.supplier and quotation.supplier.supplier else "N/A"
    
    # Metadata Table
    meta_data = [
        [Paragraph(f"<b>Quotation Ref:</b> {quotation.quote_ref}", meta_style),
         Paragraph(f"<b>Date:</b> {quotation.date_of_quote.strftime('%d/%m/%Y')}", meta_style)],
        [Paragraph(f"<b>Project:</b> {project_name}", meta_style),
         Paragraph(f"<b>Supplier:</b> {company_name}", meta_style)],
    ]
    meta_table = Table(meta_data, colWidths=[90*mm, 90*mm])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10*mm))

    # Line Items Table
    table_data = [["No.", "Description", "Quantity", "Per"]]
    line_items = quotation.line_items.all()
    
    for idx, item in enumerate(line_items, start=1):
        table_data.append([
            str(idx),
            Paragraph(item.description or "", normal_style),
            str(item.qty),
            str(item.per or "Each")
        ])

    items_table = Table(table_data, colWidths=[15*mm, 105*mm, 30*mm, 30*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),

        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (3, -1), 'CENTER'),
        
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 15*mm))
    
    footer_text = "Please submit your pricing via the unique link provided in the email."
    elements.append(Paragraph(footer_text, meta_style))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
