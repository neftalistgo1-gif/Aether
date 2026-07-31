from pydantic import BaseModel, Field


class PostalCodeRead(BaseModel):
    postal_code: str = Field(min_length=5, max_length=5)
    state: str = Field(min_length=2, max_length=120)
    municipality: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    settlement_type: str = Field(min_length=2, max_length=120)
    settlement_name: str = Field(min_length=2, max_length=160)