import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.db import SessionLocal
from app.models import SalesTransaction
import json

if __name__ == '__main__':
    s = SessionLocal()
    try:
        count = s.query(SalesTransaction).count()
        rows = s.query(SalesTransaction).limit(5).all()
        print('COUNT:', count)
        for r in rows:
            print(json.dumps({
                'transaction_id': r.transaction_id,
                'order_date': r.order_date.isoformat() if r.order_date else None,
                'sku': r.sku,
                'platform': r.platform,
                'quantity': r.quantity,
                'total_amount': float(r.total_amount) if r.total_amount is not None else None,
            }, ensure_ascii=False))
    finally:
        s.close()
