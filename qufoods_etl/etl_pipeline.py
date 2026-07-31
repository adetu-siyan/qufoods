import logging
import re

import pandas as pd
from sqlalchemy import text

from config import DatabaseManager
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(
    filename="etl.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


STATE_TO_REGION = {
    "Lagos": "Lagos",

    "Oyo": "West",
    "Ogun": "West",
    "Ondo": "West",
    "Osun": "West",

    "FCT": "Other",
    "Rivers": "Other",
    "Delta": "Other",
    "Edo": "Other",
    "Enugu": "Other",
    "Anambra": "Other",
    "Abia": "Other",
    "Kaduna": "Other",
    "Kano": "Other",
    "Plateau": "Other"
}


logger = logging.getLogger(__name__)

def read_csv_files():

    branches_df = pd.read_csv(
        BASE_DIR / "exploration/data/reference/reference_branches.csv"
    )

    menu_df = pd.read_csv(
        BASE_DIR / "exploration/data/reference/reference_menu_items.csv"
    )

    sales_df = pd.read_csv(
        BASE_DIR / "output/sales.csv"
    )

    expenses_df = pd.read_csv(
        BASE_DIR / "output/expenses.csv"
    )

    logger.info("CSV files loaded successfully.")

    return branches_df, menu_df, sales_df, expenses_df

    sales_df = sales_df.where(pd.notnull(sales_df), None)
    expenses_df = expenses_df.where(pd.notnull(expenses_df), None)
    branches_df = branches_df.where(pd.notnull(branches_df), None)
    menu_df = menu_df.where(pd.notnull(menu_df), None)

def load_branches(session, branches_df):

    logger.info("Loading branches...")

    branches_df["region"] = (
        branches_df["state"]
        .map(STATE_TO_REGION)
        .fillna("Other")
    )

    query = text("""
        INSERT INTO branches (
            branch_id,
            branch_name,
            city,
            state,
            address,
            region,
            branch_manager
        )
        VALUES (
            :branch_id,
            :branch_name,
            :city,
            :state,
            :address,
            :region,
            :branch_manager
        )
        ON CONFLICT (branch_id)
        DO UPDATE SET
            branch_name = EXCLUDED.branch_name,
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            address = EXCLUDED.address,
            region = EXCLUDED.region,
            branch_manager = EXCLUDED.branch_manager;
    """)

    for _, row in branches_df.iterrows():

        session.execute(
            query,
            {
                "branch_id": row.branch_id,
                "branch_name": row.branch_name,
                "city": row.city,
                "state": row.state,
                "address": row.address,
                "region": row.region,
                "branch_manager": row.branch_manager,
            }
        )

    logger.info(f"{len(branches_df)} branches loaded.")



def load_menu_items(session, menu_df):

    logger.info("Loading menu items...")

    query = text("""
        INSERT INTO menu_items (
            item_name
        )
        VALUES (
            :item_name
        )
        ON CONFLICT (item_name)
        DO NOTHING;
    """)

    for _, row in menu_df.iterrows():

        session.execute(
            query,
            {
                "item_name": row.item_name
            }
        )

    logger.info(f"{len(menu_df)} menu items loaded.")


def run_pipeline():

    print("Starting ETL Pipeline...")


    logger.info("=" * 60)
    logger.info("Starting ETL Pipeline")
    logger.info("=" * 60)

    db = DatabaseManager()

    session = db.get_session()

    try:

        (
            branches_df,
            menu_df,
            sales_df,
            expenses_df
        ) = read_csv_files()

        # Reference data first
        load_branches(session, branches_df)

        load_menu_items(session, menu_df)

        # Transactions
        load_sales(session, sales_df)

        load_sales_items(session, sales_df)

        load_expenses(session, expenses_df)

        session.commit()

        logger.info("ETL completed successfully.")

        print("ETL Pipeline completed successfully!")

    except Exception as e:

        session.rollback()

        logger.exception("Pipeline failed.")

        print(e)

    finally:

        session.close()

        db.dispose()



def load_sales(session, sales_df):
    logger.info("Loading sales...")

    query = text("""
        INSERT INTO sales (
            record_id,
            transaction_id,
            batch_id,
            branch_id,
            membership_id,
            order_channel,
            order_subtotal,
            discount_applied,
            total_amount,
            payment_method,
            transaction_status,
            order_source,
            customer_arrival_time,
            customer_departure_time,
            ingested_at,
            order_items_typo_fixed,
            total_amount_imputed,
            imputation_method
        )

        VALUES (

            :record_id,
            :transaction_id,
            :batch_id,
            :branch_id,
            :membership_id,
            :order_channel,
            :order_subtotal,
            :discount_applied,
            :total_amount,
            :payment_method,
            :transaction_status,
            :order_source,
            :customer_arrival_time,
            :customer_departure_time,
            :ingested_at,
            :order_items_typo_fixed,
            :total_amount_imputed,
            :imputation_method

        )

        ON CONFLICT (transaction_id)

        DO UPDATE SET

            total_amount = EXCLUDED.total_amount,
            transaction_status = EXCLUDED.transaction_status,
            payment_method = EXCLUDED.payment_method,
            order_subtotal = EXCLUDED.order_subtotal,
            discount_applied = EXCLUDED.discount_applied,
            total_amount_imputed = EXCLUDED.total_amount_imputed,
            imputation_method = EXCLUDED.imputation_method;

    """)

    for _, row in sales_df.iterrows():

        session.execute(
            query,
            {

                "record_id": row.record_id,
                "transaction_id": row.transaction_id,
                "batch_id": row.batch_id,
                "branch_id": row.branch_id,
                "membership_id": None if pd.isna(row.membership_id) else row.membership_id,
                "order_channel": row.order_channel,
                "order_subtotal": row.order_subtotal,
                "discount_applied": row.discount_applied,
                "total_amount": row.total_amount,
                "payment_method": row.payment_method,
                "transaction_status": row.transaction_status,
                "order_source": row.order_source,
                "customer_arrival_time": row.customer_arrival_time,
                "customer_departure_time": row.customer_departure_time,
                "ingested_at": row.ingested_at,

                "order_items_typo_fixed": False if pd.isna(row.order_items_typo_fixed) else bool(row.order_items_typo_fixed),
                "total_amount_imputed": False if pd.isna(row.total_amount_imputed) else bool(row.total_amount_imputed),
                "imputation_method": (
                    None
                    if pd.isna(row.imputation_method)
                    else row.imputation_method
),

            }
        )

    logger.info(f"{len(sales_df)} sales loaded.")


def get_menu_lookup(session):

    result = session.execute(
        text("""
            SELECT menu_item_id, item_name
            FROM menu_items;
        """)
    )

    return {
        row.item_name.lower().strip(): row.menu_item_id
        for row in result
    }


def parse_order_items(order_items):
    """
    Converts:

    burger(x2), coke, fried rice

    into

    [
        ("burger", 2),
        ("coke", 1),
        ("fried rice", 1)
    ]
    """

    items = []

    for item in order_items.split(","):

        item = item.strip()

        match = re.match(r"(.+?)\(x(\d+)\)$", item)

        if match:

            name = match.group(1).strip().lower()
            quantity = int(match.group(2))

        else:

            name = item.lower()
            quantity = 1

        items.append((name, quantity))

    return items


def load_sales_items(session, sales_df):

    logger.info("Loading sales items...")

    menu_lookup = get_menu_lookup(session)

    query = text("""
        INSERT INTO sales_items (
            record_id,
            menu_item_id,
            quantity
        )
        VALUES (
            :record_id,
            :menu_item_id,
            :quantity
        )
        ON CONFLICT (record_id, menu_item_id)
        DO UPDATE
        SET quantity = EXCLUDED.quantity;
    """)

    inserted = 0

    for _, sale in sales_df.iterrows():

        items = parse_order_items(sale.order_items)

        for item_name, quantity in items:

            menu_item_id = menu_lookup.get(item_name)

            if menu_item_id is None:

                logger.warning(
                    f"Menu item not found: {item_name}"
                )

                continue

            session.execute(
                query,
                {
                    "record_id": sale.record_id,
                    "menu_item_id": menu_item_id,
                    "quantity": quantity,
                },
            )

            inserted += 1

    logger.info(f"{inserted} sales items loaded.")



def load_expenses(session, expenses_df):

    logger.info("Loading expenses...")

    query = text("""
        INSERT INTO expenses (
            record_id,
            batch_id,
            branch_id,
            expense_category,
            amount,
            currency,
            raised_by,
            approved_by,
            paid_by,
            approval_status,
            expense_date,
            ingested_at
        )

        VALUES (

            :record_id,
            :batch_id,
            :branch_id,
            :expense_category,
            :amount,
            :currency,
            :raised_by,
            :approved_by,
            :paid_by,
            :approval_status,
            :expense_date,
            :ingested_at

        )

        ON CONFLICT (record_id)

        DO UPDATE SET

            amount = EXCLUDED.amount,
            approval_status = EXCLUDED.approval_status,
            approved_by = EXCLUDED.approved_by,
            paid_by = EXCLUDED.paid_by;

    """)

    for _, row in expenses_df.iterrows():

        session.execute(
            query,
            {

                "record_id": row.record_id,
                "batch_id": row.batch_id,
                "branch_id": row.branch_id,
                "expense_category": row.expense_category,
                "amount": row.amount,
                "currency": row.currency,
                "raised_by": row.raised_by,
                "approved_by": row.approved_by,
                "paid_by": row.paid_by,
                "approval_status": row.approval_status,
                "expense_date": row.expense_date,
                "ingested_at": row.ingested_at

            }
        )

    logger.info(f"{len(expenses_df)} expenses loaded.")


if __name__ == "__main__":
    run_pipeline()