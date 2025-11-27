from pydantic import BaseModel
from typing import List

class SalesNoteItem(BaseModel):
    productoId: str
    cantidad: int
    precioUnitario: float
    importe: float

class SalesNote(BaseModel):
    folio: str
    clienteId: str
    direccionFacturacionId: str
    direccionEnvioId: str
    total: float
    items: List[SalesNoteItem]