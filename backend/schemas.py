"""Pydantic request/response models for the web API."""

from pydantic import BaseModel


class ImportUrlRequest(BaseModel):
    url: str
    quick: bool = False


class RecipeResponse(BaseModel):
    name: str
    ingredients: str
    directions: str
    prep_time: str = ""
    cook_time: str = ""
    servings: str = ""
    notes: str = ""
    source_url: str = ""
    source: str = ""


class ImportResult(BaseModel):
    recipe: RecipeResponse
    synced: bool = False


class SyncRequest(BaseModel):
    name: str
    source: str = ""
    source_url: str = ""
    categories: list[str] = []
    ingredients: str = ""
    directions: str = ""
    prep_time: str = ""
    cook_time: str = ""
    servings: str = ""
    notes: str = ""


class SyncResult(BaseModel):
    success: bool
    name: str


class CategoryChild(BaseModel):
    name: str
    uid: str


class CategoryItem(BaseModel):
    name: str
    uid: str
    children: list[CategoryChild] = []


class CategoriesResponse(BaseModel):
    categories: list[CategoryItem]


class CredentialsRequest(BaseModel):
    paprika_email: str
    paprika_password: str  # plaintext in transit (HTTPS), Fernet-encrypted at rest


class CredentialsStatus(BaseModel):
    has_credentials: bool
    paprika_email: str = ""
