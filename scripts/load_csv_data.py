import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import pandas as pd
from sqlalchemy import text
import re
import json
from datetime import datetime
from pathlib import Path

def _normalize_price(value):
    if pd.isna(value):
        return None
    s = str(value).strip()
    # remove currency symbols and letters
    s = re.sub(r"[^0-9,\.\-]", '', s)
    # if value contains both commas and dots, assume commas are thousand separators
    if s.count(',') > 0 and s.count('.') > 0:
        s = s.replace(',', '')
    else:
        # remove thousand separators
        s = s.replace(',', '')
    try:
        return float(s)
    except Exception:
        return None


def _detect_currency(value: str):
    if value is None:
        return None
    s = str(value)
    # common symbols
    if '₹' in s or 'rs' in s.lower() or 'inr' in s.lower():
        return 'INR'
    if '$' in s or 'usd' in s.lower():
        return 'USD'
    if '€' in s or 'eur' in s.lower():
        return 'EUR'
    # fallback: digits only -> unknown
    return None


def _is_price_outlier(price: float):
    if price is None:
        return False
    if price < 0:
        return True
    if price > 1_000_000:  # arbitrary very large threshold
        return True
    return False


def _log_issue(kind: str, row: dict):
    try:
        log_dir = Path(ROOT_DIR) / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        fpath = log_dir / 'etl_issues.jsonl'
        entry = {'timestamp': datetime.utcnow().isoformat() + 'Z', 'kind': kind, 'row': row}
        with open(fpath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass

from app.db import engine
from app.models import Product

CSV_MAPPING = {
    "Amazon Sale Report.csv": "sales_transactions",
    "International sale Report.csv": "sales_transactions",
    "Sale Report.csv": "products",
    "P  L March 2021.csv": "platform_pricing",
    "May-2022.csv": "platform_pricing",
    "Expense IIGF.csv": "expenses",
    "Cloud Warehouse Compersion Chart.csv": "warehouse_operations",
}

DATE_COLUMNS = {
    "Amazon Sale Report.csv": ["Date"],
    "International sale Report.csv": ["Date"],
    "Sale Report.csv": [],
    "P  L March 2021.csv": ["Date"],
    "May-2022.csv": ["Date"],
    "Expense IIGF.csv": ["Date"],
    "Cloud Warehouse Compersion Chart.csv": ["Date"],
}

DATE_FORMATS = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d %b %Y",
    "%b %d, %Y",
]


def parse_date(value: str):
    if pd.isna(value) or value == "":
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue

    try:
        return pd.to_datetime(value, errors="coerce").date()
    except Exception:
        return None


def normalize_products(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "SKU Code": "sku",
        "Design No.": "design_no",
        "Category": "category",
        "Size": "size",
        "Color": "color",
        "Stock": "stock_quantity",
    })
    df = df[["sku", "design_no", "category", "size", "color", "stock_quantity"]]
    df["stock_quantity"] = pd.to_numeric(df["stock_quantity"], errors="coerce").fillna(0).astype(int)
    return df.dropna(subset=["sku"])


def load_products(csv_path: str) -> None:
    df = pd.read_csv(csv_path)
    df = normalize_products(df)
    records = df.to_dict(orient="records")

    if not records:
        return

    insert_sql = text(
        """
        INSERT INTO products (sku, design_no, category, size, color, stock_quantity)
        VALUES (:sku, :design_no, :category, :size, :color, :stock_quantity)
        ON CONFLICT (sku) DO UPDATE SET
            design_no = EXCLUDED.design_no,
            category = EXCLUDED.category,
            size = EXCLUDED.size,
            color = EXCLUDED.color,
            stock_quantity = EXCLUDED.stock_quantity
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)


def _safe_get(col_map, *keys):
    for k in keys:
        if k in col_map:
            return col_map[k]
    return None


def load_amazon_sales(csv_path: str) -> None:
    # Amazon has date format like 05-01-22 -> use %m-%d-%y
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # normalize column names
    col_map = {c.strip(): c for c in df.columns}

    # parse dates with the requested Amazon-specific format first
    if 'Date' in df.columns:
        df['order_date'] = pd.to_datetime(df['Date'], errors='coerce', format='%m-%d-%y')
    else:
        df['order_date'] = pd.to_datetime(df.iloc[:, 0], errors='coerce')

    # mapping/renaming common columns
    df['sku'] = df.get('SKU') if 'SKU' in df.columns else df.get('Product SKU') if 'Product SKU' in df.columns else df.get('Item SKU') if 'Item SKU' in df.columns else None
    df['quantity'] = pd.to_numeric(df.get('Qty') if 'Qty' in df.columns else df.get('Quantity') if 'Quantity' in df.columns else 0, errors='coerce').fillna(0).astype(int)
    df['order_id'] = df.get('Order ID') if 'Order ID' in df.columns else df.get('ORDER ID') if 'ORDER ID' in df.columns else None
    df['platform'] = 'Amazon'
    # normalize prices and detect currency
    raw_unit = df.get('Unit Price') if 'Unit Price' in df.columns else df.get('Price') if 'Price' in df.columns else None
    raw_total = df.get('Total') if 'Total' in df.columns else df.get('Amount') if 'Amount' in df.columns else None
    df['unit_price'] = df[raw_unit.name].apply(_normalize_price) if raw_unit is not None else None
    df['total_amount'] = df[raw_total.name].apply(_normalize_price) if raw_total is not None else None
    # attempt to detect currency from a Currency column or from price strings
    df['currency'] = df.get('Currency') if 'Currency' in df.columns else None
    if df['currency'] is None and raw_total is not None:
        df['currency'] = df[raw_total.name].apply(_detect_currency)
    df['asin'] = df.get('ASIN') if 'ASIN' in df.columns else None

    # drop rows missing essential data
    df = df.dropna(subset=['order_date', 'sku'])

    # ensure referenced SKUs exist in products table to satisfy FK
    skus = {str(s).strip() for s in df['sku'].dropna().unique()}
    if skus:
        _ensure_products_exist(skus)

    records = []
    for _, row in df.iterrows():
        # validate prices
        if row.get('unit_price') is not None and _is_price_outlier(row.get('unit_price')):
            _log_issue('unit_price_outlier', {'order_id': row.get('order_id'), 'sku': row.get('sku'), 'unit_price': row.get('unit_price')})
            # skip negative or extreme prices
            continue
        if row.get('total_amount') is not None and _is_price_outlier(row.get('total_amount')):
            _log_issue('total_amount_outlier', {'order_id': row.get('order_id'), 'sku': row.get('sku'), 'total_amount': row.get('total_amount')})
            continue
        records.append({
            'order_id': row.get('order_id'),
            'order_date': row.get('order_date').date() if pd.notna(row.get('order_date')) else None,
            'sku': str(row.get('sku')).strip(),
            'platform': 'Amazon',
            'customer_type': None,
            'quantity': int(row.get('quantity') or 0),
            'unit_price': float(row.get('unit_price')) if pd.notna(row.get('unit_price')) else None,
            'total_amount': float(row.get('total_amount')) if pd.notna(row.get('total_amount')) else None,
            'currency': row.get('currency') if row.get('currency') is not None else _detect_currency(row.get('Total') if 'Total' in df.columns else None),
            'region': None,
            'status': None,
            'fulfilment': None,
            'sales_channel': None,
            'ship_service_level': None,
            'style': None,
            'asin': row.get('asin'),
            'courier_status': None,
            'promotion_ids': None,
            'b2b': None,
            'fulfilled_by': None,
            'ship_city': None,
            'ship_state': None,
            'ship_postal_code': None,
            'ship_country': None,
        })

    if not records:
        return

    insert_sql = text(
        """
        INSERT INTO sales_transactions (
            order_id, order_date, sku, platform, customer_type, quantity,
            unit_price, total_amount, currency, region, status, fulfilment,
            sales_channel, ship_service_level, style, asin, courier_status,
            promotion_ids, b2b, fulfilled_by, ship_city, ship_state,
            ship_postal_code, ship_country
        ) VALUES (
            :order_id, :order_date, :sku, :platform, :customer_type, :quantity,
            :unit_price, :total_amount, :currency, :region, :status, :fulfilment,
            :sales_channel, :ship_service_level, :style, :asin, :courier_status,
            :promotion_ids, :b2b, :fulfilled_by, :ship_city, :ship_state,
            :ship_postal_code, :ship_country
        )
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)


def _ensure_products_exist(skus: set[str]) -> None:
    if not skus:
        return
    # fetch existing skus
    with engine.begin() as conn:
        res = conn.execute(text("SELECT sku FROM products WHERE sku = ANY(:skus)"), {"skus": list(skus)})
        existing = {row[0] for row in res.fetchall()}
        missing = [s for s in skus if s not in existing]
        if not missing:
            return
        insert_sql = text("INSERT INTO products (sku) VALUES (:sku) ON CONFLICT (sku) DO NOTHING")
        conn.execute(insert_sql, [{"sku": m} for m in missing])


def load_international_sales(csv_path: str) -> None:
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # Try to parse Date using the generic parser
    if 'Date' in df.columns:
        df['order_date'] = pd.to_datetime(df['Date'], errors='coerce')
    else:
        df['order_date'] = pd.to_datetime(df.iloc[:, 0], errors='coerce')

    df['sku'] = df.get('SKU') if 'SKU' in df.columns else df.get('Product SKU') if 'Product SKU' in df.columns else None
    df['quantity'] = pd.to_numeric(df.get('PCS') if 'PCS' in df.columns else df.get('Qty') if 'Qty' in df.columns else 0, errors='coerce').fillna(0).astype(int)
    raw_rate = df.get('RATE') if 'RATE' in df.columns else df.get('Unit Price') if 'Unit Price' in df.columns else None
    raw_total = df.get('GROSS AMT') if 'GROSS AMT' in df.columns else df.get('Amount') if 'Amount' in df.columns else None
    df['unit_price'] = df[raw_rate.name].apply(_normalize_price) if raw_rate is not None else None
    df['total_amount'] = df[raw_total.name].apply(_normalize_price) if raw_total is not None else None
    df['currency'] = df.get('Currency') if 'Currency' in df.columns else None
    if df['currency'] is None and raw_total is not None:
        df['currency'] = df[raw_total.name].apply(_detect_currency)

    df = df.dropna(subset=['order_date', 'sku'])

    skus = {str(s).strip() for s in df['sku'].dropna().unique()}
    if skus:
        _ensure_products_exist(skus)

    records = []
    for _, row in df.iterrows():
        if row.get('unit_price') is not None and _is_price_outlier(row.get('unit_price')):
            _log_issue('unit_price_outlier', {'sku': row.get('sku'), 'unit_price': row.get('unit_price')})
            continue
        if row.get('total_amount') is not None and _is_price_outlier(row.get('total_amount')):
            _log_issue('total_amount_outlier', {'sku': row.get('sku'), 'total_amount': row.get('total_amount')})
            continue
        records.append({
            'order_id': None,
            'order_date': row.get('order_date').date() if pd.notna(row.get('order_date')) else None,
            'sku': str(row.get('sku')).strip(),
            'platform': 'International',
            'customer_type': None,
            'quantity': int(row.get('quantity') or 0),
            'unit_price': float(row.get('unit_price')) if pd.notna(row.get('unit_price')) else None,
            'total_amount': float(row.get('total_amount')) if pd.notna(row.get('total_amount')) else None,
            'currency': row.get('currency') if row.get('currency') is not None else _detect_currency(row.get('GROSS AMT') if 'GROSS AMT' in df.columns else None),
            'region': None,
            'status': None,
            'fulfilment': None,
            'sales_channel': None,
            'ship_service_level': None,
            'style': None,
            'asin': None,
            'courier_status': None,
            'promotion_ids': None,
            'b2b': None,
            'fulfilled_by': None,
            'ship_city': None,
            'ship_state': None,
            'ship_postal_code': None,
            'ship_country': None,
        })

    if not records:
        return

    insert_sql = text(
        """
        INSERT INTO sales_transactions (
            order_id, order_date, sku, platform, customer_type, quantity,
            unit_price, total_amount, currency, region, status, fulfilment,
            sales_channel, ship_service_level, style, asin, courier_status,
            promotion_ids, b2b, fulfilled_by, ship_city, ship_state,
            ship_postal_code, ship_country
        ) VALUES (
            :order_id, :order_date, :sku, :platform, :customer_type, :quantity,
            :unit_price, :total_amount, :currency, :region, :status, :fulfilment,
            :sales_channel, :ship_service_level, :style, :asin, :courier_status,
            :promotion_ids, :b2b, :fulfilled_by, :ship_city, :ship_state,
            :ship_postal_code, :ship_country
        )
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)


def load_platform_pricing(csv_path: str) -> None:
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # normalize column names lower-case for robust matching
    orig_cols = list(df.columns)
    lc_map = {c.lower(): c for c in orig_cols}

    # find sku column (case-insensitive)
    sku_col = None
    for candidate in ('sku', 'sku code', 'sku_code', 'code', 'style id'):
        if candidate in lc_map:
            sku_col = lc_map[candidate]
            break
    if not sku_col:
        # try first column as sku
        sku_col = orig_cols[0]

    # detect platform price columns (contain 'mrp' or 'price')
    price_cols = []
    for c in orig_cols:
        cl = c.lower()
        if 'mrp' in cl or 'price' in cl:
            price_cols.append(c)

    if not price_cols:
        return

    df = df.dropna(subset=[sku_col])

    skus = {str(s).strip() for s in df[sku_col].dropna().unique()}
    if skus:
        _ensure_products_exist(skus)

    # ensure unique index exists so ON CONFLICT can use it
    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_pricing ON platform_pricing (sku, platform, effective_date)"))

    seen = set()
    records = []
    for _, row in df.iterrows():
        sku = str(row.get(sku_col)).strip()
        for pc in price_cols:
            raw = row.get(pc)
            price = _normalize_price(raw)
            if price is None:
                continue
            # derive platform name from column header, e.g. 'Amazon MRP' -> 'Amazon'
            platform_name = pc
            # remove words like 'mrp', 'price', 'old', 'final', 'fba'
            platform_name = re.sub(r'(?i)\b(mrp|price|old|final|fba)\b', '', platform_name).strip()
            platform_name = platform_name.replace('_', ' ').strip()
            if not platform_name:
                platform_name = 'Unknown'

            # dedupe by (sku, platform, price)
            key = (sku, platform_name, float(price))
            if key in seen:
                continue
            seen.add(key)

            records.append({
                'sku': sku,
                'platform': platform_name,
                'mrp': price,
                'selling_price': price,
                'effective_date': None,
                'additional_info': None,
            })

    if not records:
        return

    insert_sql = text(
        """
        INSERT INTO platform_pricing (sku, platform, mrp, selling_price, effective_date, additional_info)
        VALUES (:sku, :platform, :mrp, :selling_price, :effective_date, :additional_info)
        ON CONFLICT (sku, platform, effective_date) DO UPDATE SET
            mrp = EXCLUDED.mrp,
            selling_price = EXCLUDED.selling_price,
            additional_info = EXCLUDED.additional_info
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)


def load_expenses(csv_path: str) -> None:
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # normalize date and amount
    date_col = 'Date' if 'Date' in df.columns else 'Expense Date' if 'Expense Date' in df.columns else df.columns[0]
    df['expense_date'] = pd.to_datetime(df[date_col], errors='coerce')
    amount_col = 'Amount' if 'Amount' in df.columns else 'Total' if 'Total' in df.columns else None
    df['amount'] = pd.to_numeric(df.get(amount_col), errors='coerce') if amount_col else None
    desc_col = 'Description' if 'Description' in df.columns else df.columns[1] if len(df.columns) > 1 else None
    df['description'] = df.get(desc_col)

    df = df.dropna(subset=['expense_date'])

    records = []
    for _, row in df.iterrows():
        records.append({
            'expense_type': None,
            'expense_category': None,
            'amount': float(row.get('amount')) if pd.notna(row.get('amount')) else None,
            'expense_date': row.get('expense_date').date() if pd.notna(row.get('expense_date')) else None,
            'description': row.get('description'),
        })

    if not records:
        return

    insert_sql = text(
        """
        INSERT INTO expenses (expense_type, expense_category, amount, expense_date, description)
        VALUES (:expense_type, :expense_category, :amount, :expense_date, :description)
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)


def load_warehouse_operations(csv_path: str) -> None:
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # Attempt to parse common columns
    df['provider'] = df.get('Provider') if 'Provider' in df.columns else df.get('Warehouse') if 'Warehouse' in df.columns else None
    df['cost_per_unit'] = pd.to_numeric(df.get('Cost per Unit') if 'Cost per Unit' in df.columns else df.get('Cost') if 'Cost' in df.columns else None, errors='coerce')
    df['efficiency_rating'] = pd.to_numeric(df.get('Efficiency') if 'Efficiency' in df.columns else df.get('Efficiency Rating') if 'Efficiency Rating' in df.columns else None, errors='coerce')
    if 'Date' in df.columns:
        df['operation_date'] = pd.to_datetime(df['Date'], errors='coerce')
    else:
        df['operation_date'] = pd.NaT

    records = []
    for _, row in df.iterrows():
        records.append({
            'warehouse_type': None,
            'provider': row.get('provider'),
            'cost_per_unit': float(row.get('cost_per_unit')) if pd.notna(row.get('cost_per_unit')) else None,
            'efficiency_rating': float(row.get('efficiency_rating')) if pd.notna(row.get('efficiency_rating')) else None,
            'operation_date': row.get('operation_date').date() if pd.notna(row.get('operation_date')) else None,
            'description': None,
        })

    if not records:
        return

    insert_sql = text(
        """
        INSERT INTO warehouse_operations (warehouse_type, provider, cost_per_unit, efficiency_rating, operation_date, description)
        VALUES (:warehouse_type, :provider, :cost_per_unit, :efficiency_rating, :operation_date, :description)
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)


def main():
    parser = argparse.ArgumentParser(description="Load CSV data into OmniRetail PostgreSQL database.")
    parser.add_argument("--dataset-dir", default="dataset/unlock-profits-with-e-commerce-sales-data/versions/2", help="Path to dataset directory")
    args = parser.parse_args()

    if not os.path.isdir(args.dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {args.dataset_dir}")

    product_file = os.path.join(args.dataset_dir, "Sale Report.csv")
    if os.path.exists(product_file):
        load_products(product_file)
        print("Loaded products from Sale Report.csv")
    else:
        raise FileNotFoundError(product_file)

    amazon_file = os.path.join(args.dataset_dir, "Amazon Sale Report.csv")
    if os.path.exists(amazon_file):
        load_amazon_sales(amazon_file)
        print("Loaded Amazon Sale Report.csv into sales_transactions")
    else:
        print("Amazon Sale Report.csv not found; skipping")

    intl_file = os.path.join(args.dataset_dir, "International sale Report.csv")
    if os.path.exists(intl_file):
        load_international_sales(intl_file)
        print("Loaded International sale Report.csv into sales_transactions")
    else:
        print("International sale Report.csv not found; skipping")

    # Platform pricing
    pl1 = os.path.join(args.dataset_dir, "P  L March 2021.csv")
    if os.path.exists(pl1):
        load_platform_pricing(pl1)
        print("Loaded P  L March 2021.csv into platform_pricing")
    else:
        print("P  L March 2021.csv not found; skipping")

    pl2 = os.path.join(args.dataset_dir, "May-2022.csv")
    if os.path.exists(pl2):
        load_platform_pricing(pl2)
        print("Loaded May-2022.csv into platform_pricing")
    else:
        print("May-2022.csv not found; skipping")

    # Expenses
    exp = os.path.join(args.dataset_dir, "Expense IIGF.csv")
    if os.path.exists(exp):
        load_expenses(exp)
        print("Loaded Expense IIGF.csv into expenses")
    else:
        print("Expense IIGF.csv not found; skipping")

    # Warehouse operations
    wh = os.path.join(args.dataset_dir, "Cloud Warehouse Compersion Chart.csv")
    if os.path.exists(wh):
        load_warehouse_operations(wh)
        print("Loaded Cloud Warehouse Compersion Chart.csv into warehouse_operations")
    else:
        print("Cloud Warehouse Compersion Chart.csv not found; skipping")


if __name__ == "__main__":
    main()
