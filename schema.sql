-- schema.sql

-- 1. Master Data
CREATE TABLE menu_items (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10,2)
);

CREATE TABLE ingredients (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    cost_per_unit DECIMAL(10,2),
    unit VARCHAR(20),
    par_level DECIMAL(10,2),
    reorder_threshold DECIMAL(10,2),
    lead_time_days INT,
    shelf_life_days INT
);

CREATE TABLE recipes (
    menu_item_id INT REFERENCES menu_items(id),
    ingredient_id INT REFERENCES ingredients(id),
    quantity DECIMAL(10,4), -- Precision for small quantities like saffron
    PRIMARY KEY (menu_item_id, ingredient_id)
);

-- 2. Transactional Data
CREATE TABLE sales_orders (
    id VARCHAR(50) PRIMARY KEY,
    timestamp TIMESTAMP,
    party_size INT,
    total_amount DECIMAL(10,2)
);

CREATE TABLE order_line_items (
    order_id VARCHAR(50) REFERENCES sales_orders(id),
    menu_item_id INT REFERENCES menu_items(id),
    quantity INT,
    price_at_order DECIMAL(10,2)
);

-- 3. Operational Data (The "Flux" Value Add)
CREATE TABLE inventory_log (
    date DATE,
    ingredient_id INT REFERENCES ingredients(id),
    opening_stock DECIMAL(10,2),
    used_qty DECIMAL(10,2),
    waste_qty DECIMAL(10,2),
    closing_stock DECIMAL(10,2)
);

CREATE TABLE staff_schedule (
    date DATE,
    role VARCHAR(50),
    count INT,
    cost DECIMAL(10,2)
);

CREATE TABLE lost_sales (
    timestamp TIMESTAMP,
    party_size INT,
    reason VARCHAR(50),
    potential_revenue DECIMAL(10,2)
);
