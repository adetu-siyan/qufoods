-- =====================================================
-- QUFOODS DATABASE SCHEMA
-- Updated based on Exploration Team Handoff
-- =====================================================


-- ==========================================
-- BRANCHES
-- ==========================================


CREATE TABLE branches (
    branch_id VARCHAR(10) PRIMARY KEY,
    branch_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    branch_manager VARCHAR(100) NOT NULL
);
ALTER TABLE branches
ADD COLUMN region VARCHAR(20);



-- ==========================================
-- MENU ITEMS
-- ==========================================

CREATE TABLE menu_items (

    menu_item_id SERIAL PRIMARY KEY,

    item_name VARCHAR(100) UNIQUE NOT NULL

);

-- ==========================================
-- SALES
-- ==========================================

CREATE TABLE sales (

    record_id UUID PRIMARY KEY,

    transaction_id VARCHAR(20) UNIQUE NOT NULL,

    batch_id VARCHAR(60) NOT NULL,

    branch_id VARCHAR(10) NOT NULL,

    membership_id VARCHAR(20),

    order_channel VARCHAR(20) NOT NULL
        CHECK (order_channel IN ('ONLINE','PHONE','IN_STORE')),

    order_subtotal NUMERIC(10,2) NOT NULL
        CHECK (order_subtotal >= 0),

    discount_applied NUMERIC(5,2) DEFAULT 0
        CHECK (discount_applied BETWEEN 0 AND 1),

    total_amount NUMERIC(10,2) NOT NULL
        CHECK (total_amount >= 0),

    payment_method VARCHAR(20) NOT NULL
        CHECK (payment_method IN ('CASH','POS','TRANSFER')),

    transaction_status VARCHAR(20) NOT NULL
    
    order_source VARCHAR(20) NOT NULL
        CHECK (order_source IN ('ONLINE','PHYSICAL')),

    customer_arrival_time TIMESTAMP NOT NULL,

    customer_departure_time TIMESTAMP NOT NULL,

    ingested_at TIMESTAMP NOT NULL,

    -- Added based on exploration handoff
    order_items_typo_fixed BOOLEAN NOT NULL DEFAULT FALSE,

    total_amount_imputed BOOLEAN NOT NULL DEFAULT FALSE,

    imputation_method VARCHAR(30)
        CHECK (
            imputation_method IS NULL OR
            imputation_method IN (
                'algebraic',
                'regression',
                'branch_median_fallback'
            )
        ),

    CONSTRAINT fk_sales_branch
        FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id)

);

-- ==========================================
-- SALES ITEMS
-- ==========================================

CREATE TABLE sales_items (

    sales_item_id SERIAL PRIMARY KEY,

    record_id UUID NOT NULL,

    menu_item_id INTEGER NOT NULL,

    quantity INTEGER NOT NULL
        CHECK (quantity > 0),

    CONSTRAINT fk_sales
        FOREIGN KEY (record_id)
        REFERENCES sales(record_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_menu
        FOREIGN KEY (menu_item_id)
        REFERENCES menu_items(menu_item_id),

    CONSTRAINT unique_sale_item
        UNIQUE(record_id, menu_item_id)

);

-- ==========================================
-- EXPENSES
-- ==========================================

CREATE TABLE expenses (

    record_id UUID PRIMARY KEY,

    batch_id VARCHAR(60) NOT NULL,

    branch_id VARCHAR(10) NOT NULL,

    expense_category VARCHAR(50) NOT NULL,

    amount NUMERIC(10,2) NOT NULL
        CHECK (amount >= 0),

    currency CHAR(3) NOT NULL DEFAULT 'NGN',

    raised_by VARCHAR(100) NOT NULL,

    approved_by VARCHAR(100) NOT NULL,

    paid_by VARCHAR(100) NOT NULL,

    approval_status VARCHAR(20) NOT NULL
        CHECK (approval_status IN ('APPROVED','PENDING','REJECTED')),

    expense_date DATE NOT NULL,

    ingested_at TIMESTAMP NOT NULL,

    CONSTRAINT fk_expense_branch
        FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id)

);

-- ==========================================
-- INDEXES
-- ==========================================

CREATE INDEX idx_sales_branch
ON sales(branch_id);

CREATE INDEX idx_sales_transaction
ON sales(transaction_id);

CREATE INDEX idx_sales_arrival
ON sales(customer_arrival_time);

CREATE INDEX idx_expense_branch
ON expenses(branch_id);

CREATE INDEX idx_expense_date
ON expenses(expense_date);

CREATE INDEX idx_menu_name
ON menu_items(item_name);

ALTER TABLE branches
ADD CONSTRAINT uq_branch_name UNIQUE (branch_name);

ALTER TABLE menu_items
ADD CONSTRAINT uq_menu_item UNIQUE (item_name);