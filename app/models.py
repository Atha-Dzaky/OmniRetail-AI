from sqlalchemy import Column, Integer, String, Numeric, Date, Text, TIMESTAMP, func, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    design_no = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)
    color = Column(String(50), nullable=True)
    stock_quantity = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    sales_transactions = relationship("SalesTransaction", back_populates="product")
    platform_pricing = relationship("PlatformPricing", back_populates="product")


class SalesTransaction(Base):
    __tablename__ = "sales_transactions"

    transaction_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(100), nullable=True)
    order_date = Column(Date, nullable=False, index=True)
    sku = Column(String(100), ForeignKey("products.sku"), nullable=False, index=True)
    platform = Column(String(50), nullable=True, index=True)
    customer_type = Column(String(20), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=True)
    total_amount = Column(Numeric(14, 2), nullable=True)
    currency = Column(String(3), nullable=True, index=True)
    region = Column(String(100), nullable=True)
    status = Column(String(100), nullable=True)
    fulfilment = Column(String(100), nullable=True)
    sales_channel = Column(String(100), nullable=True)
    ship_service_level = Column(String(100), nullable=True)
    style = Column(String(100), nullable=True)
    asin = Column(String(50), nullable=True)
    courier_status = Column(String(100), nullable=True)
    promotion_ids = Column(Text, nullable=True)
    b2b = Column(String(20), nullable=True)
    fulfilled_by = Column(String(100), nullable=True)
    ship_city = Column(String(100), nullable=True)
    ship_state = Column(String(100), nullable=True)
    ship_postal_code = Column(String(50), nullable=True)
    ship_country = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="sales_transactions")


class PlatformPricing(Base):
    __tablename__ = "platform_pricing"
    __table_args__ = (
        UniqueConstraint('sku', 'platform', 'effective_date', name='uq_platform_pricing'),
    )

    pricing_id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), ForeignKey("products.sku"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)
    mrp = Column(Numeric(12, 2), nullable=True)
    selling_price = Column(Numeric(12, 2), nullable=True)
    effective_date = Column(Date, nullable=True, index=True)
    additional_info = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="platform_pricing")


class Expense(Base):
    __tablename__ = "expenses"

    expense_id = Column(Integer, primary_key=True, index=True)
    expense_type = Column(String(100), nullable=True)
    expense_category = Column(String(50), nullable=True, index=True)
    amount = Column(Numeric(14, 2), nullable=True)
    expense_date = Column(Date, nullable=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class WarehouseOperation(Base):
    __tablename__ = "warehouse_operations"

    operation_id = Column(Integer, primary_key=True, index=True)
    warehouse_type = Column(String(50), nullable=True, index=True)
    provider = Column(String(50), nullable=True, index=True)
    cost_per_unit = Column(Numeric(12, 2), nullable=True)
    efficiency_rating = Column(Numeric(5, 2), nullable=True)
    operation_date = Column(Date, nullable=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
