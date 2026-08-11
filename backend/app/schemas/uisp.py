from pydantic import BaseModel


class UISPConnectionRead(BaseModel):
    connected: bool
    device_count: int
