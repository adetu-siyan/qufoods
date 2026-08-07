# Database → Reporting Handoff

**From:** Bukolami (Database & ETL)  
**To:** Daniel (Reporting / Streamlit)

---

# Overview

The ETL pipeline receives cleaned sales and expense CSVs produced by the Exploration pipeline and loads them into a normalized PostgreSQL database hosted on Neon.

The reporting layer should query **only the normalized database tables**, not the raw CSV files.

The ETL pipeline performs the following:

- Loads branch reference data
- Loads menu item reference data
- Loads sales transactions
- Normalizes `order_items` into the `sales_items` table
- Loads expense transactions
- Performs UPSERT operations using PostgreSQL `ON CONFLICT`
- Maps branches to regions
- Preserves data-quality indicators produced during exploration

---

# Database Schema

The reporting layer should use the following tables.

---

# 1. branches

Stores one record for every QuFoods branch.

| Column | Type | Description |
|---------|------|-------------|
| branch_id | VARCHAR | Primary Key |
| branch_name | VARCHAR | Branch name |
| city | VARCHAR | Branch city |
| state | VARCHAR | Nigerian state |
| address | TEXT | Branch address |
| region | VARCHAR | Region derived during ETL |
| branch_manager | VARCHAR | Branch manager |

Primary Key

```sql
branch_id
```

---

## Region Mapping

The ETL already populates the `region` column.

| State | Region |
|---------|---------|
| Lagos | Lagos |
| Oyo | West |
| Ogun | West |
| Ondo | West |
| Osun | West |
| All remaining states | Other |

The reporting layer should use this column directly.

---

# 2. menu_items

Reference table containing every valid menu item.

| Column | Type |
|---------|------|
| menu_item_id | SERIAL PRIMARY KEY |
| item_name | VARCHAR |

---

# 3. sales

Stores one record for every customer transaction.

| Column | Description |
|----------|------------|
| record_id | Primary Key |
| transaction_id | Business unique identifier |
| batch_id | Batch identifier |
| branch_id | Foreign key → branches |
| membership_id | Membership number (nullable) |
| order_channel | ONLINE / PHONE / IN_STORE |
| order_subtotal | Amount before discount |
| discount_applied | Discount percentage (0–1) |
| total_amount | Final amount paid |
| payment_method | CASH / POS / TRANSFER |
| transaction_status | COMPLETED / FAILED |
| order_source | ONLINE / PHYSICAL |
| customer_arrival_time | Arrival timestamp |
| customer_departure_time | Departure timestamp |
| ingested_at | ETL timestamp |
| order_items_typo_fixed | Boolean |
| total_amount_imputed | Boolean |
| imputation_method | algebraic / regression / branch_median_fallback / NULL |

---

# 4. sales_items

Contains one record for every menu item sold.

One transaction can have multiple rows.

| Column | Description |
|----------|------------|
| sales_item_id | Primary Key |
| record_id | Foreign key → sales |
| menu_item_id | Foreign key → menu_items |
| quantity | Quantity purchased |

Use this table for:

- Best-selling items
- Menu popularity
- Quantity sold
- Item-level analysis

Do **not** parse the original `order_items` field. It has already been normalized by the ETL.

---

# 5. expenses

Stores expense records.

| Column | Description |
|----------|------------|
| record_id | Primary Key |
| batch_id | Batch identifier |
| branch_id | Foreign key → branches |
| expense_category | Expense type |
| amount | Expense amount |
| currency | Currency (NGN) |
| raised_by | Employee |
| approved_by | Approver |
| paid_by | Finance officer |
| approval_status | APPROVED / PENDING / REJECTED |
| expense_date | Expense date |
| ingested_at | ETL timestamp |

---

# Table Relationships

```
branches
    │
    │ branch_id
    │
    ├────────────── sales
    │                  │
    │                  │ record_id
    │                  │
    │             sales_items
    │                  │
    │                  │ menu_item_id
    │                  │
    │             menu_items
    │
    └────────────── expenses
```

---

# Data Quality Fields

The following fields originate from the Exploration pipeline and are preserved by the ETL.

## order_items_typo_fixed

Indicates whether any menu item names were automatically corrected.

Useful for data-quality reporting.

---

## total_amount_imputed

Indicates whether the transaction total was imputed during data cleaning.

---

## imputation_method

Possible values:

- NULL
- algebraic
- regression
- branch_median_fallback

These fields can be used to display reporting confidence indicators.

Example:

> 7% of this month's revenue was imputed.

---

# Business Rules

## Revenue

Always calculate revenue using:

```sql
total_amount
```

Only include:

```sql
WHERE transaction_status = 'COMPLETED'
```

Some failed transactions still contain monetary values and should **not** contribute to revenue.

---

## Discount Formula

The Exploration team confirmed:

```
total_amount = order_subtotal × (1 - discount_applied)
```

`discount_applied` is a fraction between 0 and 1.

---

## Membership Penetration

Definition:

```
Members
÷
Total Transactions
```

Equivalent SQL:

```sql
COUNT(membership_id)::decimal
/
NULLIF(COUNT(record_id),0)
```

---

## Discount Usage Rate

Definition:

```
Transactions with discounts
÷
Total transactions
```

A transaction is considered discounted when:

```sql
discount_applied > 0
```

---

## Average Customer Dwell Time

Calculate using:

```
customer_departure_time
-
customer_arrival_time
```

Negative durations should be excluded.

---

# Suggested Dashboards

## Branch Manager Dashboard

Recommended metrics:

- Revenue
- Total transactions
- Failed transaction rate
- Membership penetration
- Average transaction value
- Discount usage rate
- Average customer dwell time
- Revenue by payment method
- Revenue by order channel
- Top-selling menu items
- Daily revenue trend

---

## Regional Manager Dashboard

Recommended metrics:

- Revenue by branch
- Expenses by branch
- Profit by branch
- Membership penetration
- Discount usage rate
- Branch comparisons
- Revenue distribution by region
- Data-quality indicators
    - Typo corrections
    - Imputed revenue

---

## Operations Dashboard

Recommended metrics:

- Total network revenue
- Total network expenses
- Network profit
- Weekly revenue trend
- Transaction status counts
- Top 5 branches by revenue
- Bottom 5 branches by revenue
- Expense breakdown
- Revenue by region
- Overall membership penetration

---

# Helpful PostgreSQL Functions

Frequently useful functions include:

- `DATE_TRUNC()`
- `COALESCE()`
- `NULLIF()`
- `CASE`
- `COUNT()`
- `SUM()`
- `AVG()`

---

# Existing Indexes

The following indexes already exist:

- `sales(branch_id)`
- `sales(transaction_id)`
- `sales(customer_arrival_time)`
- `expenses(branch_id)`
- `expenses(expense_date)`
- `menu_items(item_name)`

---

# ETL Guarantees

The reporting layer can assume the following:

- Branches are loaded before sales and expenses.
- Menu items are loaded before sales items.
- Foreign key relationships are valid.
- Duplicate sales are prevented using `transaction_id`.
- Duplicate expenses are prevented using `record_id`.
- Region values have already been populated.
- `sales_items` contains normalized menu-item data.
- Menu item names have already been cleaned.
- Data-quality flags are preserved from the Exploration pipeline.

---

# Important Notes

- Always filter revenue using `transaction_status = 'COMPLETED'`.
- Use `sales_items` for all item-level reporting.
- Use the `region` column directly instead of deriving it.
- Use `COALESCE()` when aggregating to avoid `NULL` values.
- Use `NULLIF()` when calculating ratios to avoid division-by-zero errors.