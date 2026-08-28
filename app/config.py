import os
from pydantic import BaseModel
from typing import Optional


class Settings(BaseModel):
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
            whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN"),
        )
