import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.db import SessionLocal
from app.models import Product
import json

if __name__ == '__main__':
    s = SessionLocal()
    try:
        count = s.query(Product).count()
        rows = s.query(Product).limit(5).all()
        print('COUNT:', count)
        for p in rows:
            print(json.dumps({
                'sku': p.sku,
                'design_no': p.design_no,
                'category': p.category,
                'size': p.size,
                'color': p.color,
                'stock_quantity': p.stock_quantity,
            }, ensure_ascii=False))
    finally:
        s.close()
