import streamlit as st
import plotly.express as px
from pdf import generate_branch_pdf, generate_regional_pdf, generate_operations_pdf
from queries import (
    get_sales, get_expenses, imputation_summary, revenue_by_branch,
    total_revenue, average_order_value, failed_transaction_count,
    payment_method_split, top_ordered_items,
    regional_revenue, revenue_vs_expenses, membership_penetration, top_and_bottom_branch,
    top_5_branches, bottom_5_branches, network_transaction_status, total_expenses_network
)
# Page config — sets the browser tab title and layout
st.set_page_config(page_title="QuFoods Dashboard", layout="wide")

# Sidebar
st.sidebar.image("https://via.placeholder.com/150x50?text=QuFoods", width=150)
st.sidebar.title("QuFoods Reports")
st.sidebar.markdown("---")

report_type = st.sidebar.selectbox(
    "Select report type",
    ["Branch Report", "Regional Report", "Operations Report"]
)

st.sidebar.markdown("---")
st.sidebar.caption("Batch: 2026-06-17 | Pipeline: Live")

# Load data once
sales = get_sales()
expenses = get_expenses()

# Pages
if report_type == "Branch Report":
    st.title("Branch Performance Report")
    st.caption("Daily snapshot — 17 Jun 2026")

    rev_total = total_revenue(sales)
    txn_count = len(sales)
    aov = average_order_value(sales)
    failed = failed_transaction_count(sales)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"₦{rev_total:,.0f}")
    col2.metric("Transactions", txn_count)
    col3.metric("Avg Order Value", f"₦{aov:,.0f}")
    col4.metric("Failed Transactions", failed)

    st.markdown("---")

    # Revenue by branch — green palette
    rev = revenue_by_branch(sales).reset_index()
    rev.columns = ["Branch", "Revenue"]
    fig1 = px.bar(
        rev,
        x="Branch",
        y="Revenue",
        title="Revenue by Branch",
        color="Revenue",
        color_continuous_scale=["#1abc9c", "#2ecc71", "#39FF14"],
        template="plotly_dark"
    )
    fig1.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#161b22",
        coloraxis_showscale=False
    )
    st.plotly_chart(fig1, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        # Payment methods — green shades
        pay = payment_method_split(sales).reset_index()
        pay.columns = ["Method", "Count"]
        fig2 = px.bar(
            pay,
            x="Method",
            y="Count",
            title="Payment Methods",
            color="Method",
            color_discrete_sequence=["#39FF14", "#2ecc71", "#1abc9c"],
            template="plotly_dark"
        )
        fig2.update_layout(
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            showlegend=False
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_right:
        # Top ordered items — green shades
        items = top_ordered_items(sales).reset_index()
        items.columns = ["Item", "Count"]
        fig3 = px.bar(
            items,
            x="Item",
            y="Count",
            title="Top Ordered Items",
            color="Item",
            color_discrete_sequence=["#39FF14", "#2ecc71", "#1abc9c", "#16a085", "#148f77"],
            template="plotly_dark"
        )
        fig3.update_layout(
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            showlegend=False
        )
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")

    imp = imputation_summary(sales)
    if imp["imputed_count"] > 0:
        st.warning(
            f"{imp['imputed_pct']}% of revenue figures in this batch "
            f"({imp['imputed_count']} records) were estimated rather than "
            f"directly recorded. Breakdown by method: "
            f"{imp['methods']}"
        )

    st.markdown("---")
    pdf_bytes = generate_branch_pdf(sales, expenses)
    st.download_button(
        label="Download Branch Report PDF",
        data=pdf_bytes,
        file_name="qufoods_branch_report.pdf",
        mime="application/pdf"
    )


   #REGIONAL REPORT 

elif report_type == "Regional Report":
    st.title("Regional Comparison Report")
    st.caption("Weekly snapshot — 17 Jun 2026")

    # Metric cards
    reg_rev = regional_revenue(sales)
    top_branch, bottom_branch = top_and_bottom_branch(sales)
    total_branches = sales["branch_name"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"₦{reg_rev:,.0f}")
    col2.metric("Branches Active", total_branches)
    col3.metric("Top Performer", top_branch)
    col4.metric("Lowest Performer", bottom_branch)
    

    st.markdown("---")

    # Revenue vs Expenses chart — grouped bars, red palette
    rev_exp = revenue_vs_expenses(sales, expenses)
    fig4 = px.bar(
        rev_exp,
        x="Branch",
        y=["Revenue", "Expenses"],
        title="Revenue vs Expenses by Branch",
        barmode="group",
        color_discrete_sequence=["#FF3131", "#6b0000"],
        template="plotly_dark"
    )
    fig4.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#161b22"
    )
    st.plotly_chart(fig4, use_container_width=True)

    # Membership penetration — red shades
    mem = membership_penetration(sales)
    fig5 = px.bar(
        mem,
        x="Branch",
        y="Membership %",
        title="Loyalty Membership Penetration by Branch (%)",
        color="Membership %",
        color_continuous_scale=["#c0392b", "#e74c3c", "#FF3131"],
        template="plotly_dark"
    )
    fig5.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#161b22",
        coloraxis_showscale=False
    )
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown("---")
    pdf_bytes = generate_regional_pdf(sales, expenses)
    st.download_button(
        label="Download Regional Report PDF",
        data=pdf_bytes,
        file_name="qufoods_regional_report.pdf",
        mime="application/pdf"
    )

elif report_type == "Operations Report":
    st.title("Operations Report")
    st.caption("Network-wide snapshot — 17 Jun 2026")

    # Metric cards
    net_rev = total_revenue(sales)
    net_txn = len(sales)
    net_branches = sales["branch_name"].nunique()
    net_exp = total_expenses_network(expenses)

    col1, col2, col3, col4 = st.columns(4)

# Network Revenue — neon green
    col1.markdown(f"""
    <div style="font-size:14px; color:#aaa;">Network Revenue</div>
    <div style="font-size:30px; font-weight:600; color:#39FF14;">₦{net_rev:,.0f}</div>
""", unsafe_allow_html=True)

# These two stay as normal metrics
    col2.metric("Total Transactions", net_txn)
    col3.metric("Branches Active", net_branches)

# Total Expenses — red
    col4.markdown(f"""
    <div style="font-size:14px; color:#aaa;">Total Expenses</div>
    <div style="font-size:30px; font-weight:600; color:#FF3131;">₦{net_exp:,.0f}</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # Top 5 vs Bottom 5 side by side
    col_left, col_right = st.columns(2)

    with col_left:
        top5 = top_5_branches(sales)
        fig6 = px.bar(
            top5,
            x="Branch",
            y="Revenue",
            title="Top 5 Branches by Revenue",
            color="Revenue",
            color_continuous_scale=["#0077b6", "#00b4d8", "#90e0ef"],
            template="plotly_dark"
        )
        fig6.update_layout(
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig6, use_container_width=True)

    with col_right:
        bottom5 = bottom_5_branches(sales)
        fig7 = px.bar(
            bottom5,
            x="Branch",
            y="Revenue",
            title="Bottom 5 Branches by Revenue",
            color="Revenue",
            color_continuous_scale=["#90e0ef", "#00b4d8", "#0077b6"],
            template="plotly_dark"
        )
        fig7.update_layout(
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig7, use_container_width=True)

    # Network transaction status breakdown
    status = network_transaction_status(sales)
    status.columns = ["Status", "Count"]
    fig8 = px.bar(
        status,
        x="Status",
        y="Count",
        title="Network-wide Transaction Status",
        color="Status",
        color_discrete_sequence=["#00b4d8", "#0077b6", "#023e8a"],
        template="plotly_dark"
    )
    fig8.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#161b22",
        showlegend=False
    )
    st.plotly_chart(fig8, use_container_width=True)

    st.markdown("---")
    pdf_bytes = generate_operations_pdf(sales, expenses)
    st.download_button(
        label="Download Operations Report PDF",
        data=pdf_bytes,
        file_name="qufoods_operations_report.pdf",
        mime="application/pdf"
    )