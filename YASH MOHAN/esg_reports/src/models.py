from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TableRow(BaseModel):
    data: Dict[str, Any]

class CleanedTable(BaseModel):
    rows: List[Dict[str, Any]]
    summary: Optional[str] = None

class ParsedReport(BaseModel):
    filename: str
    text: str
    tables: List[CleanedTable]
    metadata: Dict[str, Any] = Field(default_factory=dict)
