from pydantic import BaseModel

class ProductOut(BaseModel):
    sku: str
    design_no: str | None
    category: str | None
    size: str | None
    color: str | None
    stock_quantity: int

    class Config:
        orm_mode = True
