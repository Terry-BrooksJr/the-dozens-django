from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from API.models import Insult


@dataclass
class InsultDataType:
    content: str
    category: Insult.CATEGORY
    nsfw: bool
    added_on: date
    added_by: int
    last_modified: datetime
    status: Insult.STATUS