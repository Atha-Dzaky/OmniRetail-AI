-- DDL migration: add unique constraint/index for platform_pricing
CREATE TABLE IF NOT EXISTS migrations__applied (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Unique index for platform_pricing (sku, platform, effective_date)
CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_pricing ON platform_pricing (sku, platform, effective_date);

-- Ensure products.sku is unique (already unique in model)
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_sku ON products (sku);
