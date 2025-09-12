from pydantic import BaseModel


class LanguageBase(BaseModel):
    name: str


class LanguageCreate(LanguageBase):
    pass


class LanguageRead(LanguageBase):
    name: str

    class Config:
        from_attributes = True


class UserLanguageUpdate(BaseModel):
    language_names: list[str]

    class Config:
        json_schema_extra = {"example": {"language_names": ["English", "Yoruba", "Igbo"]}}
