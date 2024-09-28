import typing
from dataclasses import dataclass
from enum import Enum
from datetime import date, datetime

@dataclass
class InsultDataType:
    content: str
    category: Enum
    explicit: bool
    added_on: date
    added_by: int
    last_modified: datetime
    status: Enum