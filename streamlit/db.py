# import psycopg2
# import pandas as pd

# # Neon PostgreSQL connection string — get this from Bukolami
# # Format: postgresql://user:password@host/dbname?sslmode=require
# CONNECTION_STRING = "YOUR_NEON_CONNECTION_STRING_HERE"

# def get_sales():
#     conn = psycopg2.connect(CONNECTION_STRING)
#     query = """
#         SELECT 
#             s.record_id, s.transaction_id, s.batch_id,
#             s.branch_id, b.branch_name, b.branch_manager, b.region,
#             s.membership_id, s.order_channel, s.order_source,
#             s.order_subtotal, s.discount_applied, s.total_amount,
#             s.payment_method, s.transaction_status,
#             s.customer_arrival_time, s.customer_departure_time,
#             s.ingested_at, s.order_items_typo_fixed,
#             s.total_amount_imputed, s.imputation_method
#         FROM sales s
#         JOIN branches b ON s.branch_id = b.branch_id
#     """
#     df = pd.read_sql(query, conn)
#     conn.close()
#     return df

# def get_expenses():
#     conn = psycopg2.connect(CONNECTION_STRING)
#     query = """
#         SELECT 
#             e.record_id, e.batch_id, e.branch_id,
#             b.branch_name, b.region,
#             e.expense_category, e.amount, e.currency,
#             e.raised_by, e.approved_by, e.paid_by,
#             e.approval_status, e.expense_date, e.ingested_at
#         FROM expenses e
#         JOIN branches b ON e.branch_id = b.branch_id
#     """
#     df = pd.read_sql(query, conn)
#     conn.close()
#     return df

# def get_top_items(branch_id=None, limit=8):
#     # Uses sales_items table — do NOT parse order_items string
#     # Bukolami has already normalized this into the sales_items table
#     conn = psycopg2.connect(CONNECTION_STRING)
#     query = """
#         SELECT 
#             m.item_name,
#             SUM(si.quantity) as total_quantity
#         FROM sales_items si
#         JOIN menu_items m ON si.menu_item_id = m.menu_item_id
#         JOIN sales s ON si.record_id = s.record_id
#         WHERE s.transaction_status = 'COMPLETED'
#         {branch_filter}
#         GROUP BY m.item_name
#         ORDER BY total_quantity DESC
#         LIMIT %(limit)s
#     """.format(
#         branch_filter="AND s.branch_id = %(branch_id)s" if branch_id else ""
#     )
#     params = {"limit": limit}
#     if branch_id:
#         params["branch_id"] = branch_id
#     df = pd.read_sql(query, conn, params=params)
#     conn.close()
#     return df



import requests
import pandas as pd

# This is temporary — points at the raw S3 batch directly
# On Day 7 this gets replaced with a real Neon PostgreSQL connection

BATCH_URL = "https://qufoods-raw.s3.amazonaws.com/year=2026/month=06/day=17/batch_BATCH-96bd24c2-7124-4fb5-93e8-f016bd600d67_20260617T154538Z.json"

def get_data():
    response = requests.get(BATCH_URL)
    batch = response.json()
    records = batch["records"]
    df = pd.DataFrame(records)
    return df