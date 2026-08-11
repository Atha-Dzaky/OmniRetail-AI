from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db_session
from app.models import Product

router = APIRouter()

@router.get("/", response_model=list[dict])
async def list_products(db: Session = Depends(get_db_session)):
    products = db.query(Product).limit(20).all()
    return [
        {
            "sku": p.sku,
            "design_no": p.design_no,
            "category": p.category,
            "size": p.size,
            "color": p.color,
            "stock_quantity": p.stock_quantity,
        }
        for p in products
    ]
