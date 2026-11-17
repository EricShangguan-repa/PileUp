CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(20) NOT NULL,
    source_product_id VARCHAR(64) NOT NULL,
    sku VARCHAR(64),
    description VARCHAR(255),
    UNIQUE KEY uq_products_source_id (source, source_product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(20) NOT NULL,
    source_order_id VARCHAR(64) NOT NULL,
    order_date DATETIME NOT NULL,
    customer_id VARCHAR(64),
    country VARCHAR(64),
    is_cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE KEY uq_orders_source_id (source, source_order_id)
);

CREATE TABLE IF NOT EXISTS order_lines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    source VARCHAR(20) NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    source VARCHAR(20) NOT NULL,
    snapshot_date DATE NOT NULL,
    stock_quantity INT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (product_id) REFERENCES products(id),
    UNIQUE KEY uq_inventory_product_date (product_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS daily_sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    source VARCHAR(20) NOT NULL,
    sale_date DATE NOT NULL,
    quantity_sold INT NOT NULL,
    revenue DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    UNIQUE KEY uq_daily_sales_product_date (product_id, sale_date)
);

CREATE TABLE IF NOT EXISTS forecasts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    source VARCHAR(20) NOT NULL,
    forecast_made_date DATE NOT NULL,
    horizon_date DATE NOT NULL,
    predicted_quantity DECIMAL(10, 2) NOT NULL,
    model_name VARCHAR(64) NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
