import streamlit as st
import plotly.express as px
from pdf import generate_branch_pdf, generate_regional_pdf, generate_operations_pdf
from bedrock import generate_narrative, build_branch_prompt, build_regional_prompt, build_operations_prompt
from queries import (
    get_sales, get_expenses, revenue_by_branch,
    total_revenue, average_order_value, failed_transaction_count,
    payment_method_split, top_ordered_items,
    regional_revenue, revenue_vs_expenses, membership_penetration, 
    top_and_bottom_branch, top_5_branches, bottom_5_branches, 
    network_transaction_status, total_expenses_network,
    revenue_by_region, imputation_summary, filter_by_period
)

# This codeblock controls the chart rendering and the color scheme of the charts

def render_chart(df, x, y, title, colors, chart_type, key):
    # Draws a bar, line, or pie chart depending on what the manager selected
    # df = dataframe, x = x-axis column, y = y-axis column
    # key = unique identifier so each chart's switcher is independent
    
    # Small radio selector sitting above the chart
    chart_type_selected = st.radio(
        "",
        ["Bar", "Line", "Pie"],
        horizontal=True,
        index=["Bar", "Line", "Pie"].index(chart_type),
        key=key
    )

    if chart_type_selected == "Bar":
        # Check if colors list has enough entries to use discrete coloring
        # Discrete = one color per bar by label
        # Continuous = gradient based on value
        if len(colors) >= len(df):
            fig = px.bar(
                df, x=x, y=y, title=title,
                color=x,
                color_discrete_sequence=colors,
                template="plotly_dark"
            )
        else:
            fig = px.bar(
                df, x=x, y=y, title=title,
                color=y,
                color_continuous_scale=colors,
                template="plotly_dark"
            )
        fig.update_layout(
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            coloraxis_showscale=False,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type_selected == "Line":
        fig = px.line(
            df, x=x, y=y, title=title,
            template="plotly_dark",
            markers=True
        )
        fig.update_layout(
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22"
        )
        fig.update_traces(line_color=colors[0] if isinstance(colors, list) else colors)
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type_selected == "Pie":
        fig = px.pie(
            df, names=x, values=y, title=title,
            color_discrete_sequence=colors,
            template="plotly_dark"
        )
        fig.update_layout(
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22"
        )
        st.plotly_chart(fig, use_container_width=True)



# Page config — sets the browser tab title and layout
st.set_page_config(
    page_title="QuFoods Dashboard",
    page_icon="🍔",
    layout="wide"
)

# Sidebar
st.sidebar.image("Q-removebg-preview (1).png", width=180)
st.sidebar.title(" REPORTS")
st.sidebar.markdown("---")

# Report type selector
report_type = st.sidebar.selectbox(
    "Select report type",
    ["Branch Report", "Regional Report", "Operations Report"]
)

st.sidebar.markdown("---")

# Load data once — must happen before branch filter
# so the dropdown can be built from real branch names
sales = get_sales()
expenses = get_expenses()

# Branch filter — pulls unique branch names from the data
# sorted alphabetically so the list is easy to scan
all_branches = sorted(sales["branch_name"].dropna().unique().tolist())
branch_options = ["All branches"] + all_branches
selected_branch = st.sidebar.selectbox("Filter by branch", branch_options)

st.sidebar.markdown("---")

# Time period selector
st.sidebar.markdown("**Time Period**")
period = st.sidebar.radio(
    "Select period",
    ["All", "Today", "1W", "1M", "3M"],
    horizontal=False
)

st.sidebar.markdown("---")

# Report selector
st.sidebar.caption("Batch: 2026-06-17 | Pipeline: Live")

# Apply branch filter
# If a specific branch is selected, filter both dataframes down to that branch
if selected_branch != "All branches":
    sales = sales[sales["branch_name"] == selected_branch]
    expenses = expenses[expenses["branch_name"] == selected_branch]

# Apply time period filter to sales
# Expenses use expense_date not arrival_time so filtered separately
sales = filter_by_period(sales, period)


# Pages
if report_type == "Branch Report":
    st.title("Branch Performance Report")
    st.caption("Daily snapshot — 17 Jun 2026")

    rev_total = total_revenue(sales)
    txn_count = len(sales)
    aov = average_order_value(sales)
    failed = failed_transaction_count(sales)

# Revenue and Income text and color tone
    col1, col2, col3, col4 = st.columns(4)

    # Total Revenue — neon green
    col1.markdown(f"""
        <div style="font-size:14px; color:#aaa;">Total Revenue</div>
        <div style="font-size:28px; font-weight:600; color:#39FF14;">₦{rev_total:,.0f}</div>
    """, unsafe_allow_html=True)

    # Transactions — plain white
    col2.metric("Transactions", txn_count)

    # Avg Order Value — neon green
    col3.markdown(f"""
        <div style="font-size:14px; color:#aaa;">Avg Order Value</div>
        <div style="font-size:28px; font-weight:600; color:#39FF14;">₦{aov:,.0f}</div>
    """, unsafe_allow_html=True)

    # Failed Transactions — red
    col4.markdown(f"""
        <div style="font-size:14px; color:#aaa;">Failed Transactions</div>
        <div style="font-size:28px; font-weight:600; color:#FF3131;">{failed}</div>
    """, unsafe_allow_html=True)
    


    st.markdown("---")
    # AI Summary button — only calls Bedrock when clicked
    # Cached in session_state so it persists across rerenders
    if "branch_narrative" not in st.session_state:
        st.session_state.branch_narrative = None

    if st.button("✨ Generate AI Summary", key="branch_ai_btn"):
        with st.spinner("Generating summary..."):
            aws_key = st.secrets["aws"]["access_key_id"]
            aws_secret = st.secrets["aws"]["secret_access_key"]

            top_item = top_ordered_items(sales).index[0] if len(top_ordered_items(sales)) > 0 else "N/A"
            top_pay = payment_method_split(sales).index[0] if len(payment_method_split(sales)) > 0 else "N/A"

            metrics = {
                "total_revenue": f"₦{rev_total:,.0f}",
                "transactions": txn_count,
                "avg_order_value": f"₦{aov:,.0f}",
                "failed_transactions": failed,
                "top_item": top_item,
                "top_payment": top_pay
            }
            prompt = build_branch_prompt(metrics)
            st.session_state.branch_narrative = generate_narrative(
                prompt, aws_key, aws_secret
            )

    if st.session_state.branch_narrative:
        st.markdown(f"""
            <div style="
                border: 1px solid #39FF14;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 16px;
                background: #0d1117;
                color: #e6edf3;
                font-size: 14px;
                line-height: 1.6;
            ">
                <span style="color:#39FF14; font-weight:600;">
                    ✨ AI Summary
                </span><br><br>
                {st.session_state.branch_narrative}
            </div>
        """, unsafe_allow_html=True)

    # Revenue by branch — green palette
    rev = revenue_by_branch(sales).reset_index()
    rev.columns = ["Branch", "Revenue"]
    render_chart(
        rev, "Branch", "Revenue",
        "Revenue by Branch",
        ["#1abc9c", "#2ecc71", "#39FF14"],
        "Bar",
        "branch_rev_chart"
    )

    col_left, col_right = st.columns(2)

    # Payment methods — green shades
    with col_left:
        pay = payment_method_split(sales).reset_index()
        pay.columns = ["Method", "Count"]
        render_chart(
            pay, "Method", "Count",
            "Payment Methods",
            ["#39FF14", "#2ecc71", "#1abc9c"],
            "Bar",
            "pay_method_chart"
        )

    with col_right:
        # Top ordered items — green shades
        items = top_ordered_items(sales).reset_index()
        items.columns = ["Item", "Count"]
        render_chart(
            items, "Item", "Count",
            "Top Ordered Items",
            ["#39FF14", "#2ecc71", "#1abc9c", "#16a085", "#148f77"],
            "Bar",
            "top_items_chart"
        )

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

    # The color coding for top income and loss
    col1, col2, col3, col4 = st.columns(4)

    # Total Revenue — green
    col1.markdown(f"""
        <div style="font-size:14px; color:#aaa;">Total Revenue</div>
        <div style="font-size:28px; font-weight:600; color:#39FF14;">₦{reg_rev:,.0f}</div>
    """, unsafe_allow_html=True)

    # Branches Active — plain
    col2.metric("Branches Active", total_branches)

    # Top Performer — green
    col3.markdown(f"""
        <div style="font-size:14px; color:#aaa;">Top Performer</div>
        <div style="font-size:22px; font-weight:600; color:#39FF14;">{top_branch}</div>
    """, unsafe_allow_html=True)

    # Lowest Performer — red
    col4.markdown(f"""
        <div style="font-size:14px; color:#aaa;">Lowest Performer</div>
        <div style="font-size:22px; font-weight:600; color:#FF3131;">{bottom_branch}</div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # AI Summary button — cached so it doesn't re-call Bedrock on every rerender
    if "regional_narrative" not in st.session_state:
        st.session_state.regional_narrative = None

    if st.button("✨ Generate AI Summary", key="regional_ai_btn"):
        with st.spinner("Generating summary..."):
            aws_key = st.secrets["aws"]["access_key_id"]
            aws_secret = st.secrets["aws"]["secret_access_key"]

            total_exp = total_expenses_network(expenses)
            mem_rate = round(sales["membership_id"].notna().sum() / len(sales) * 100, 1) if len(sales) > 0 else 0

            metrics = {
                "total_revenue": f"₦{reg_rev:,.0f}",
                "branches_active": total_branches,
                "top_branch": top_branch,
                "bottom_branch": bottom_branch,
                "total_expenses": f"₦{total_exp:,.0f}",
                "membership_rate": f"{mem_rate}%"
            }
            prompt = build_regional_prompt(metrics)
            st.session_state.regional_narrative = generate_narrative(
                prompt, aws_key, aws_secret
            )

    if st.session_state.regional_narrative:
        st.markdown(f"""
            <div style="
                border: 1px solid #FF3131;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 16px;
                background: #0d1117;
                color: #e6edf3;
                font-size: 14px;
                line-height: 1.6;
            ">
                <span style="color:#FF3131; font-weight:600;">
                    ✨ AI Summary
                </span><br><br>
                {st.session_state.regional_narrative}
            </div>
        """, unsafe_allow_html=True)

    # Revenue vs Expenses chart — grouped bars, red palette
    rev_exp = revenue_vs_expenses(sales, expenses)
    render_chart(
        rev_exp, "Branch", "Revenue",
        "Revenue by Branch",
        ["#FF3131", "#e74c3c", "#c0392b", "#a93226", "#922b21",
         "#7b241c", "#641e16", "#e74c3c", "#FF3131", "#c0392b",
         "#a93226", "#922b21"],
        "Bar",
        "regional_rev_chart"
    )

    # Membership penetration — red shades
    mem = membership_penetration(sales)
    render_chart(
        mem, "Branch", "Membership %",
        "Loyalty Membership Penetration by Branch (%)",
        ["#FF3131", "#e74c3c", "#c0392b", "#a93226", "#922b21",
         "#7b241c", "#641e16", "#e74c3c", "#FF3131", "#c0392b",
         "#a93226", "#922b21"],
        "Bar",
        "mem_chart"
    )

    st.markdown("---")
    pdf_bytes = generate_regional_pdf(sales, expenses)
    st.download_button(
        label="Download Regional Report PDF",
        data=pdf_bytes,
        file_name="qufoods_regional_report.pdf",
        mime="application/pdf"
    )


# OPERATIONS REPORT
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

    # AI Summary — operations report
    if "operations_narrative" not in st.session_state:
        st.session_state.operations_narrative = None

    if st.button("✨ Generate AI Summary", key="operations_ai_btn"):
        with st.spinner("Generating summary..."):
            aws_key = st.secrets["aws"]["access_key_id"]
            aws_secret = st.secrets["aws"]["secret_access_key"]

            # Use operations-specific variables — not branch variables
            top_branch, bottom_branch = top_and_bottom_branch(sales)
            failed_count = failed_transaction_count(sales)
            failed_rate = round(failed_count / len(sales) * 100, 1) if len(sales) > 0 else 0

            metrics = {
                "total_revenue": f"₦{net_rev:,.0f}",
                "total_expenses": f"₦{net_exp:,.0f}",
                "total_transactions": net_txn,
                "branches_active": net_branches,
                "top_branch": top_branch,
                "bottom_branch": bottom_branch,
                "failed_rate": f"{failed_rate}%"
            }
            # Correct function name — build_operations_prompt not build_operational_prompt
            prompt = build_operations_prompt(metrics)
            st.session_state.operations_narrative = generate_narrative(
                prompt, aws_key, aws_secret
            )

    if st.session_state.operations_narrative:
        st.markdown(f"""
            <div style="
                border: 1px solid #00b4d8;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 16px;
                background: #0d1117;
                color: #e6edf3;
                font-size: 14px;
                line-height: 1.6;
            ">
                <span style="color:#00b4d8; font-weight:600;">
                    ✨ AI Summary
                </span><br><br>
                {st.session_state.operations_narrative}
            </div>
        """, unsafe_allow_html=True)




    # Top 5 vs Bottom 5 side by side
    col_left, col_right = st.columns(2)

    with col_left:
        top5 = top_5_branches(sales)
        render_chart(
            top5, "Branch", "Revenue",
            "Top 5 Branches by Revenue",
            ["#0077b6", "#00b4d8", "#90e0ef"],
            "Bar",
            "top5_chart"
        )

    with col_right:
        bottom5 = bottom_5_branches(sales)
        render_chart(
            bottom5, "Branch", "Revenue",
            "Bottom 5 Branches by Revenue",
            ["#90e0ef", "#00b4d8", "#0077b6"],
            "Bar",
            "bottom5_chart"
        )

    status = network_transaction_status(sales)
    status.columns = ["Status", "Count"]
    render_chart(
        status, "Status", "Count",
        "Network-wide Transaction Status",
        ["#00b4d8", "#0077b6", "#023e8a"],
        "Bar",
        "status_chart"
    )



    st.markdown("---")
    pdf_bytes = generate_operations_pdf(sales, expenses)
    st.download_button(
        label="Download Operations Report PDF",
        data=pdf_bytes,
        file_name="qufoods_operations_report.pdf",
        mime="application/pdf"
    )