from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io

# Light theme colors — PDF lives on white paper, not a dark screen
WHITE = colors.white
DARK_TEXT = colors.HexColor("#1a1a2e")
MUTED_TEXT = colors.HexColor("#555555")
LIGHT_ROW = colors.HexColor("#f8f9fa")
ALT_ROW = colors.HexColor("#ffffff")
BORDER = colors.HexColor("#dee2e6")

# Accent colors per report — used only for headers and dividers
GREEN = colors.HexColor("#1a7a1a")
RED = colors.HexColor("#c0392b")
BLUE = colors.HexColor("#0077b6")


def _base_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontSize=24,
        textColor=DARK_TEXT,
        spaceAfter=14,
        fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        fontSize=10,
        textColor=MUTED_TEXT,
        spaceAfter=16,
        fontName="Helvetica"
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontSize=13,
        textColor=DARK_TEXT,
        spaceBefore=14,
        spaceAfter=6,
        fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        name="BodyText2",
        fontSize=10,
        textColor=DARK_TEXT,
        spaceAfter=14,
        fontName="Helvetica"
    ))
    return styles


def _metric_table(metrics, accent_color):
    # Four metric cards across the top
    # Label in muted grey, value in accent color, white background
    col_width = (A4[0] - 4 * cm) / len(metrics)

    label_style = ParagraphStyle(
        "ml", fontName="Helvetica", fontSize=9,
        textColor=MUTED_TEXT
    )
    value_style = ParagraphStyle(
        "mv", fontName="Helvetica-Bold", fontSize=13,
        textColor=accent_color
    )

    header_row = [Paragraph(label, label_style) for label, _ in metrics]
    value_row = [Paragraph(value, value_style) for _, value in metrics]

    t = Table(
    [header_row, value_row],
    colWidths=[col_width] * len(metrics),
    rowHeights=[20, 30]
     )

    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return t


def _data_table(headers, rows, accent_color):
    # Clean table — colored header, alternating white/light grey rows
    # Dark text throughout so everything is readable on white paper
    header_style = ParagraphStyle(
        "th", fontName="Helvetica-Bold", fontSize=9,
        textColor=WHITE
    )
    cell_style = ParagraphStyle(
        "td", fontName="Helvetica", fontSize=9,
        textColor=DARK_TEXT
    )

    header_row = [Paragraph(h, header_style) for h in headers]
    data_rows = [
        [Paragraph(str(cell), cell_style) for cell in row]
        for row in rows
    ]

    col_width = (A4[0] - 4 * cm) / len(headers)
    t = Table(
        [header_row] + data_rows,
        colWidths=[col_width] * len(headers),
        repeatRows=1
    )

    # Build alternating row colors
    row_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), accent_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]
    for i, _ in enumerate(data_rows):
        bg = LIGHT_ROW if i % 2 == 0 else ALT_ROW
        row_styles.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))

    t.setStyle(TableStyle(row_styles))
    return t


def _build_doc(buffer, title_text, subtitle_text, metrics, accent_color, sections):
    # sections is a list of (heading, headers, rows) tuples
    # This shared builder means all three reports have identical structure
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=title_text
    )
    styles = _base_styles()
    story = []

    # Header
    story.append(Paragraph(title_text, styles["ReportTitle"]))
    story.append(Paragraph(subtitle_text, styles["ReportSubtitle"]))
    story.append(HRFlowable(
        width="100%", thickness=2,
        color=accent_color, spaceAfter=10
    ))

    # Metric cards
    story.append(_metric_table(metrics, accent_color))
    story.append(Spacer(1, 0.6*cm))

    # Data sections
    for heading, headers, rows in sections:
        story.append(Paragraph(heading, styles["SectionHeader"]))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=BORDER, spaceAfter=6
        ))
        story.append(_data_table(headers, rows, accent_color))
        story.append(Spacer(1, 0.5*cm))

    doc.build(story)


def generate_branch_pdf(sales, expenses):
    buffer = io.BytesIO()

    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    rev_total = completed["total_amount"].sum()
    aov = completed["total_amount"].mean() if len(completed) else 0
    failed = len(sales[sales["transaction_status"] == "FAILED"])

    metrics = [
        ("Total Revenue", f"N{rev_total:,.0f}"),
        ("Transactions", str(len(sales))),
        ("Avg Order Value", f"N{aov:,.0f}"),
        ("Failed", str(failed)),
    ]

    rev_by_branch = (
        completed.groupby("branch_name")["total_amount"]
        .sum().sort_values(ascending=False).reset_index()
    )
    branch_rows = [
        [r["branch_name"], f"N{r['total_amount']:,.0f}"]
        for _, r in rev_by_branch.iterrows()
    ]

    pay = sales["payment_method"].value_counts().reset_index()
    pay.columns = ["Method", "Count"]
    pay_rows = [[r["Method"], str(r["Count"])] for _, r in pay.iterrows()]

    sections = [
        ("Revenue by Branch", ["Branch", "Revenue (NGN)"], branch_rows),
        ("Payment Method Breakdown", ["Payment Method", "Transactions"], pay_rows),
    ]

    _build_doc(
        buffer,
        "Branch Performance Report",
        "Daily snapshot — 17 Jun 2026",
        metrics, GREEN, sections
    )
    buffer.seek(0)
    return buffer.read()


def generate_regional_pdf(sales, expenses):
    import pandas as pd
    buffer = io.BytesIO()

    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    rev_total = completed["total_amount"].sum()
    rev_by_branch = completed.groupby("branch_name")["total_amount"].sum().sort_values(ascending=False)
    top = rev_by_branch.index[0].replace("QuFoods ", "") if len(rev_by_branch) else "N/A"
    bottom = rev_by_branch.index[-1].replace("QuFoods ", "") if len(rev_by_branch) else "N/A"

    metrics = [
        ("Total Revenue", f"N{rev_total:,.0f}"),
        ("Branches Active", str(sales["branch_name"].nunique())),
        ("Top Performer", top),
        ("Lowest Performer", bottom),
    ]

    rev = completed.groupby("branch_name")["total_amount"].sum().rename("Revenue")
    exp = expenses.groupby("branch_name")["amount"].sum().rename("Expenses")
    combined = pd.concat([rev, exp], axis=1).fillna(0).reset_index()
    rev_exp_rows = [
        [r["branch_name"], f"N{r['Revenue']:,.0f}", f"N{r['Expenses']:,.0f}"]
        for _, r in combined.iterrows()
    ]

    sales2 = sales.copy()
    sales2["is_member"] = sales2["membership_id"].notna()
    mem = (
        sales2.groupby("branch_name")["is_member"]
        .mean().mul(100).round(1)
        .sort_values(ascending=False).reset_index()
    )
    mem_rows = [
        [r["branch_name"], f"{r['is_member']}%"]
        for _, r in mem.iterrows()
    ]

    sections = [
        ("Revenue vs Expenses by Branch", ["Branch", "Revenue", "Expenses"], rev_exp_rows),
        ("Membership Penetration by Branch", ["Branch", "Membership %"], mem_rows),
    ]

    _build_doc(
        buffer,
        "Regional Comparison Report",
        "Weekly snapshot — 17 Jun 2026",
        metrics, RED, sections
    )
    buffer.seek(0)
    return buffer.read()


def generate_operations_pdf(sales, expenses):
    buffer = io.BytesIO()

    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    net_rev = completed["total_amount"].sum()
    net_exp = expenses["amount"].sum()

    metrics = [
        ("Network Revenue", f"N{net_rev:,.0f}"),
        ("Total Transactions", str(len(sales))),
        ("Branches Active", str(sales["branch_name"].nunique())),
        ("Total Expenses", f"N{net_exp:,.0f}"),
    ]

    top5 = (
        completed.groupby("branch_name")["total_amount"]
        .sum().sort_values(ascending=False).head(5).reset_index()
    )
    top5_rows = [
        [r["branch_name"].replace("QuFoods ", ""), f"N{r['total_amount']:,.0f}"]
        for _, r in top5.iterrows()
    ]

    bottom5 = (
        completed.groupby("branch_name")["total_amount"]
        .sum().sort_values(ascending=True).head(5).reset_index()
    )
    bottom5_rows = [
        [r["branch_name"].replace("QuFoods ", ""), f"N{r['total_amount']:,.0f}"]
        for _, r in bottom5.iterrows()
    ]

    status = sales["transaction_status"].value_counts().reset_index()
    status.columns = ["Status", "Count"]
    status_rows = [[r["Status"], str(r["Count"])] for _, r in status.iterrows()]

    sections = [
        ("Top 5 Branches by Revenue", ["Branch", "Revenue"], top5_rows),
        ("Bottom 5 Branches by Revenue", ["Branch", "Revenue"], bottom5_rows),
        ("Network Transaction Status", ["Status", "Count"], status_rows),
    ]

    _build_doc(
        buffer,
        "Operations Report",
        "Network-wide snapshot — 17 Jun 2026",
        metrics, BLUE, sections
    )
    buffer.seek(0)
    return buffer.read()