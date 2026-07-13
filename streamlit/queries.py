import pandas as pd
from db import get_data

def get_sales():
    df = get_data()
    sales = df[df["record_type"] == "SALE"].reset_index(drop=True)
    return sales

def get_expenses():
    df = get_data()
    expenses = df[df["record_type"] == "EXPENSE"].reset_index(drop=True)
    return expenses

def revenue_by_branch(sales):
    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    return completed.groupby("branch_name")["total_amount"].sum().sort_values(ascending=False)

def total_revenue(sales):
    # Only count transactions that COMPLETED and have a real amount
    # Incomplete or missing amounts would give a false revenue figure
    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    return completed["total_amount"].sum()


def average_order_value(sales):
    # Same logic — only completed transactions with known amounts
    # Average = total revenue divided by number of those transactions
    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    if len(completed) == 0:
        return 0
    return completed["total_amount"].mean()


def failed_transaction_count(sales):
    # Count how many transactions have a FAILED status
    # This is a data quality and operations signal for the branch manager
    return len(sales[sales["transaction_status"] == "FAILED"])

def payment_method_split(sales):
    # Count how many transactions used each payment method
    # value_counts() goes through the column and tallies each unique value
    return sales["payment_method"].value_counts()




    # TEMPORARY — parses order_items string directly from S3 data
    # Replace with get_top_items() version on Day 7 DB swap
    # See db.py get_top_items() for the live database version
def top_ordered_items(sales, top_n=8):
    # Step 1: Use the typo-corrected column if it exists, otherwise use the original
    # This means the chart works whether or not the cleaning step has run
    items_col = "order_items_clean" if "order_items_clean" in sales.columns else "order_items"

    # Step 2: Split each order string by comma to get individual item entries
    # .explode() turns ["burger, coke", "zobo"] into three separate rows
    items = (
        sales[items_col]
        .dropna()                          # ignore any rows where order_items is empty
        .str.split(", ")                   # split "burger, coke" into ["burger", "coke"]
        .explode()                         # one item per row
        .str.replace(r"\(x\d+\)$", "", regex=True)  # strip "(x2)" from "burger(x2)"
        .str.strip()                       # remove any leftover spaces
    )

    # Step 3: Count and return the top N items
    return items.value_counts().head(top_n)



def regional_revenue(sales):
    # Total revenue across all completed transactions
    # This is the network-wide number for the regional view
    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    return completed["total_amount"].sum()


def revenue_vs_expenses(sales, expenses):
    # Build a combined view showing revenue AND expenses per branch
    # so the manager can see both numbers side by side

    # Revenue side — sum completed sales per branch
    rev = (
        sales[
            (sales["transaction_status"] == "COMPLETED") &
            (sales["total_amount"].notna())
        ]
        .groupby("branch_name")["total_amount"]
        .sum()
        .rename("Revenue")
    )

    # Expenses side — sum all expenses per branch
    exp = (
        expenses
        .groupby("branch_name")["amount"]
        .sum()
        .rename("Expenses")
    )

    # Combine both into one dataframe — branches with no expenses get 0
    combined = pd.concat([rev, exp], axis=1).fillna(0).reset_index()
    combined.columns = ["Branch", "Revenue", "Expenses"]
    return combined


def membership_penetration(sales):
    # For each branch, what percentage of transactions came from loyalty members
    # membership_id is not null = member, null = walk-in
    sales = sales.copy()
    sales["is_member"] = sales["membership_id"].notna()
    penetration = (
        sales.groupby("branch_name")["is_member"]
        .mean()
        .mul(100)          # convert 0.25 to 25%
        .round(1)
        .sort_values(ascending=False)
        .reset_index()
    )
    penetration.columns = ["Branch", "Membership %"]
    return penetration


def top_and_bottom_branch(sales):
    # Returns the name of the highest and lowest revenue branch
    # Used for the metric cards at the top of the regional report
    rev = revenue_by_branch(sales)
    if len(rev) == 0:
        return "N/A", "N/A"
    top = rev.index[0].replace("QuFoods ", "")
    bottom = rev.index[-1].replace("QuFoods ", "")
    return top, bottom

def top_5_branches(sales):
    # Rank all branches by revenue and return the top 5
    # The head of operations wants to know who is carrying the network
    rev = revenue_by_branch(sales).head(5).reset_index()
    rev.columns = ["Branch", "Revenue"]
    rev["Branch"] = rev["Branch"].str.replace("QuFoods ", "")
    return rev


def bottom_5_branches(sales):
    # Rank all branches by revenue and return the bottom 5
    # These are the underperformers the HOO needs to investigate
    rev = revenue_by_branch(sales).tail(5).reset_index()
    rev.columns = ["Branch", "Revenue"]
    rev["Branch"] = rev["Branch"].str.replace("QuFoods ", "")
    return rev


def network_transaction_status(sales):
    # Count completed, failed, and any other statuses across the whole network
    # Gives the HOO a picture of overall pipeline health
    return sales["transaction_status"].value_counts().reset_index()


def total_expenses_network(expenses):
    # Sum all expenses across every branch
    return expenses["amount"].sum()




#Dwell Time for the app
def avg_dwell_time(sales):
    # Calculate dwell time in minutes for each transaction
    # Departure minus arrival gives us the time spent in the branch
    sales = sales.copy()
    sales["arrival"] = pd.to_datetime(sales["customer_arrival_time"])
    sales["departure"] = pd.to_datetime(sales["customer_departure_time"])
    sales["dwell_minutes"] = (
        sales["departure"] - sales["arrival"]
    ).dt.total_seconds() / 60

    # Filter out negative dwell times — these are data entry errors
    # where departure was recorded before arrival. Including them
    # would pull the average down artificially.
    valid = sales[sales["dwell_minutes"] > 0]

    if len(valid) == 0:
        return 0

    return round(valid["dwell_minutes"].mean(), 1)


# After Bukolami normalizes — uses region column from branches table
def revenue_by_region(sales):
    # Uses the region column Bukolami populates during ETL
    # No need to derive Lagos/West/Other manually
    completed = sales[
        (sales["transaction_status"] == "COMPLETED") &
        (sales["total_amount"].notna())
    ]
    return (
        completed.groupby("region")["total_amount"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )


def imputation_summary(sales):
    total = len(sales)
    if total == 0:
        return {"imputed_count": 0, "imputed_pct": 0, "methods": {}}

    # Column only exists in live DB — not in S3 stub data
    # Returns zeros safely until DB swap is done
    if "total_amount_imputed" not in sales.columns:
        return {"imputed_count": 0, "imputed_pct": 0, "methods": {}}

    imputed = sales[sales["total_amount_imputed"] == True]
    imputed_count = len(imputed)
    imputed_pct = round(imputed_count / total * 100, 1)

    methods = {}
    if imputed_count > 0:
        methods = imputed["imputation_method"].value_counts().to_dict()

    return {
        "imputed_count": imputed_count,
        "imputed_pct": imputed_pct,
        "methods": methods
    }
    # Shows what percentage of revenue figures were imputed
    # rather than directly recorded — a reporting confidence signal
    # Fields preserved by Bukolami's ETL from the exploration pipeline
    