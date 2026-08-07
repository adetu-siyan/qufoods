from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as colors_module
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io
import io as _io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Light theme colors
WHITE = colors_module.white
DARK_TEXT = colors_module.HexColor("#1a1a2e")
MUTED_TEXT = colors_module.HexColor("#555555")
LIGHT_ROW = colors_module.HexColor("#f8f9fa")
ALT_ROW = colors_module.HexColor("#ffffff")
BORDER = colors_module.HexColor("#dee2e6")
GREEN = colors_module.HexColor("#1a7a1a")
RED = colors_module.HexColor("#c0392b")
BLUE = colors_module.HexColor("#0077b6")


def _base_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontSize=24,
        textColor=DARK_TEXT,
        spaceAfter=20,
        fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        fontSize=10,
        textColor=MUTED_TEXT,
        spaceBefore=8,
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
        spaceBefore=8,
        spaceAfter=14,
        fontName="Helvetica"
    ))
    return styles


def _metric_table(metrics, accent_color):
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


def _pie_chart_image(labels, values, colors, title):
    fig, ax = plt.subplots(figsize=(5, 3.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90,
        pctdistance=0.75,
        wedgeprops=dict(edgecolor='white', linewidth=1.5)
    )
    for text in texts:
        text.set_fontsize(8)
        text.set_color('#1a1a2e')
    for autotext in autotexts:
        autotext.set_fontsize(7)
        autotext.set_color('white')
        autotext.set_fontweight('bold')
    ax.set_title(title, fontsize=10, fontweight='bold', color='#1a1a2e', pad=10)
    plt.tight_layout()
    img_buffer = _io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150,
                bbox_inches='tight', facecolor='white')
    plt.close()
    img_buffer.seek(0)
    return Image(img_buffer, width=14*cm, height=9*cm)


def _pie_with_explanation(labels, values, colors, title, styles):
    elements = []
    img = _pie_chart_image(labels, values, colors, title)
    elements.append(img)
    elements.append(Spacer(1, 0.2*cm))

    max_idx = values.index(max(values))
    min_idx = values.index(min(values))
    total = sum(values)
    dominant_pct = round(values[max_idx] / total * 100, 1)
    smallest_pct = round(values[min_idx] / total * 100, 1)

    explanation_text = (
        f"<b>{labels[max_idx]}</b> accounts for the largest share at "
        f"<b>{dominant_pct}%</b> of the total. "
        f"<b>{labels[min_idx]}</b> represents the smallest share at "
        f"<b>{smallest_pct}%</b>. "
        f"The chart shows the breakdown across all {len(labels)} categories."
    )
    explanation_style = ParagraphStyle(
        "explanation",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors_module.HexColor("#444444"),
        spaceAfter=12,
        leading=14
    )
    elements.append(Paragraph(explanation_text, explanation_style))
    return elements


def generate_branch_pdf(sales, expenses):
    import pandas as pd
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
    pay_labels = pay["Method"].tolist()
    pay_values = pay["Count"].tolist()
    pay_colors = ["#1a7a1a", "#2ecc71", "#27ae60"][:len(pay_labels)]

    channel = sales["order_channel"].value_counts().reset_index()
    channel.columns = ["Channel", "Count"]
    chan_labels = channel["Channel"].tolist()
    chan_values = channel["Count"].tolist()
    chan_colors = ["#1abc9c", "#16a085", "#0e6655"][:len(chan_labels)]

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="QuFoods Branch Report"
    )
    styles = _base_styles()
    story = []

    story.append(Paragraph("Branch Performance Report", styles["ReportTitle"]))
    story.append(Paragraph("Daily snapshot — 17 Jun 2026", styles["ReportSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=10))
    story.append(_metric_table(metrics, GREEN))
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph("Revenue by Branch", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(_data_table(["Branch", "Revenue (NGN)"], branch_rows, GREEN))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Payment Method Breakdown", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(_data_table(["Payment Method", "Transactions"], pay_rows, GREEN))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Payment Method Split", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    for el in _pie_with_explanation(pay_labels, pay_values, pay_colors,
                                     "How customers are paying", styles):
        story.append(el)

    story.append(Paragraph("Order Channel Split", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    for el in _pie_with_explanation(chan_labels, chan_values, chan_colors,
                                     "Where orders are coming from", styles):
        story.append(el)

    doc.build(story)
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
    rev_by_branch = (
        completed.groupby("branch_name")["total_amount"]
        .sum().sort_values(ascending=False)
    )
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

    pay = sales["payment_method"].value_counts().reset_index()
    pay.columns = ["Method", "Count"]
    pay_labels = pay["Method"].tolist()
    pay_values = pay["Count"].tolist()
    pay_colors = ["#c0392b", "#e74c3c", "#922b21"][:len(pay_labels)]

    mem_count = int(sales["membership_id"].notna().sum())
    walk_count = int(sales["membership_id"].isna().sum())
    mem_labels = ["Members", "Walk-ins"]
    mem_values = [mem_count, walk_count]
    mem_colors = ["#c0392b", "#f5b7b1"]

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="QuFoods Regional Report"
    )
    styles = _base_styles()
    story = []

    story.append(Paragraph("Regional Comparison Report", styles["ReportTitle"]))
    story.append(Paragraph("Weekly snapshot — 17 Jun 2026", styles["ReportSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=RED, spaceAfter=10))
    story.append(_metric_table(metrics, RED))
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph("Revenue vs Expenses by Branch", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(_data_table(["Branch", "Revenue", "Expenses"], rev_exp_rows, RED))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Membership Penetration by Branch", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(_data_table(["Branch", "Membership %"], mem_rows, RED))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Payment Method Split", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    for el in _pie_with_explanation(pay_labels, pay_values, pay_colors,
                                     "How customers are paying", styles):
        story.append(el)

    story.append(Paragraph("Membership vs Walk-in Split", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    for el in _pie_with_explanation(mem_labels, mem_values, mem_colors,
                                     "Loyalty membership penetration", styles):
        story.append(el)

    doc.build(story)
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
    stat_labels = status["Status"].tolist()
    stat_values = status["Count"].tolist()
    stat_colors = ["#0077b6", "#023e8a"][:len(stat_labels)]

    exp_cat = expenses["expense_category"].value_counts().reset_index()
    exp_cat.columns = ["Category", "Count"]
    exp_labels = exp_cat["Category"].tolist()
    exp_values = exp_cat["Count"].tolist()
    exp_colors = ["#00b4d8", "#0077b6", "#023e8a", "#03045e"][:len(exp_labels)]

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="QuFoods Operations Report"
    )
    styles = _base_styles()
    story = []

    story.append(Paragraph("Operations Report", styles["ReportTitle"]))
    story.append(Paragraph("Network-wide snapshot — 17 Jun 2026", styles["ReportSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=10))
    story.append(_metric_table(metrics, BLUE))
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph("Top 5 Branches by Revenue", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(_data_table(["Branch", "Revenue"], top5_rows, BLUE))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Bottom 5 Branches by Revenue", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(_data_table(["Branch", "Revenue"], bottom5_rows, BLUE))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Network Transaction Status", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(_data_table(["Status", "Count"], status_rows, BLUE))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Transaction Status Breakdown", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    for el in _pie_with_explanation(stat_labels, stat_values, stat_colors,
                                     "Completed vs failed transactions network-wide", styles):
        story.append(el)

    story.append(Paragraph("Expense Category Breakdown", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    for el in _pie_with_explanation(exp_labels, exp_values, exp_colors,
                                     "Where network expenses are being spent", styles):
        story.append(el)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()