-- GraphRec – MySQL Schema
-- Khởi tạo tự động khi container mysql khởi động lần đầu

CREATE DATABASE IF NOT EXISTS graphrec_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE graphrec_db;

-- Bảng sản phẩm
CREATE TABLE IF NOT EXISTS products (
    product_id     VARCHAR(20)    PRIMARY KEY,
    title          TEXT           NOT NULL,
    sub_category   VARCHAR(200),
    main_category  VARCHAR(200),
    brand          VARCHAR(200),
    price          DECIMAL(12,2)  DEFAULT 0,
    original_price DECIMAL(12,2)  DEFAULT 0,
    rating         DECIMAL(3,1)   DEFAULT 0,
    review_count   INT            DEFAULT 0,
    image_url      TEXT,
    link           TEXT,
    -- FULLTEXT index cho phép tìm kiếm văn bản đầy đủ trên cột title
    FULLTEXT KEY ft_title (title)
);

-- Bảng người dùng
CREATE TABLE IF NOT EXISTS users (
    user_id  VARCHAR(20)  PRIMARY KEY,
    name     VARCHAR(200),
    email    VARCHAR(200)
);

-- Bảng hành vi (VIEWED / BOUGHT)
-- Đây là bảng trung tâm cho các truy vấn JOIN nhiều tầng
CREATE TABLE IF NOT EXISTS actions (
    id         BIGINT       AUTO_INCREMENT PRIMARY KEY,
    user_id    VARCHAR(20)  NOT NULL,
    product_id VARCHAR(20)  NOT NULL,
    action     ENUM('VIEWED','BOUGHT') NOT NULL,
    ts         DATETIME     DEFAULT CURRENT_TIMESTAMP,

    -- Index giúp tăng tốc JOIN theo user_id và product_id
    INDEX idx_user    (user_id),
    INDEX idx_product (product_id),
    INDEX idx_action  (action),

    FOREIGN KEY (user_id)    REFERENCES users(user_id)    ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

-- Bảng đánh giá sản phẩm do người dùng gửi trong luồng ecommerce
CREATE TABLE IF NOT EXISTS product_reviews (
    id             BIGINT       AUTO_INCREMENT PRIMARY KEY,
    product_id     VARCHAR(20)  NOT NULL,
    user_id        VARCHAR(20)  NULL,
    user_name      VARCHAR(200) NOT NULL,
    wallet_address VARCHAR(200) NULL,
    rating         TINYINT      NOT NULL,
    comment        TEXT,
    created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_pr_product_created (product_id, created_at),
    INDEX idx_pr_rating (rating),
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);
