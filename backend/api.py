"""API route definitions."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import User
from .oauth import encrypt_password
from .schemas import (
    CategoriesResponse,
    CategoryItem,
    CredentialsRequest,
    CredentialsStatus,
    ImportResult,
    ImportUrlRequest,
    RecipeResponse,
    SyncRequest,
    SyncResult,
)
from .services import get_categories, import_from_images, import_from_url, sync_recipe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/import/url", response_model=ImportResult)
async def import_url(
    req: ImportUrlRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await import_from_url(req.url)
    except Exception:
        logger.exception("URL import failed")
        raise HTTPException(status_code=500, detail="Import failed")

    recipe = RecipeResponse(**result)

    if req.quick:
        try:
            final_name = await sync_recipe(
                name=recipe.name,
                source=recipe.source,
                source_url=recipe.source_url,
                categories=[],
                ingredients=recipe.ingredients,
                directions=recipe.directions,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                notes=recipe.notes,
                photo_data=recipe.photo_data,
                image_url=recipe.image_url,
                paprika_email=current_user.paprika_email,
                paprika_password_enc=current_user.paprika_password_enc,
            )
            recipe.name = final_name
            return ImportResult(recipe=recipe, synced=True)
        except Exception:
            logger.exception("Quick sync failed")
            return ImportResult(recipe=recipe, synced=False)

    return ImportResult(recipe=recipe)


@router.post("/import/images", response_model=ImportResult)
async def import_images(
    images: list[UploadFile] = File(...),
    quick: bool = Form(False),
    current_user: User = Depends(get_current_user),
):
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    image_files = []
    for img in images:
        data = await img.read()
        image_files.append((img.filename or "image.jpg", data))

    try:
        result = await import_from_images(image_files)
    except Exception:
        logger.exception("Image import failed")
        raise HTTPException(status_code=500, detail="Import failed")

    recipe = RecipeResponse(**result)

    if quick:
        try:
            final_name = await sync_recipe(
                name=recipe.name,
                source=recipe.source,
                source_url=recipe.source_url,
                categories=[],
                ingredients=recipe.ingredients,
                directions=recipe.directions,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                notes=recipe.notes,
                photo_data=recipe.photo_data,
                image_url=recipe.image_url,
                paprika_email=current_user.paprika_email,
                paprika_password_enc=current_user.paprika_password_enc,
            )
            recipe.name = final_name
            return ImportResult(recipe=recipe, synced=True)
        except Exception:
            logger.exception("Quick sync failed")
            return ImportResult(recipe=recipe, synced=False)

    return ImportResult(recipe=recipe)


@router.get("/categories", response_model=CategoriesResponse)
async def list_categories(current_user: User = Depends(get_current_user)):
    try:
        cats = await get_categories(
            paprika_email=current_user.paprika_email,
            paprika_password_enc=current_user.paprika_password_enc,
        )
    except Exception:
        logger.exception("Failed to fetch categories")
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

    return CategoriesResponse(
        categories=[CategoryItem(**c) for c in cats]
    )


@router.post("/sync", response_model=SyncResult)
async def sync(
    req: SyncRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        final_name = await sync_recipe(
            name=req.name,
            source=req.source,
            source_url=req.source_url,
            categories=req.categories,
            ingredients=req.ingredients,
            directions=req.directions,
            prep_time=req.prep_time,
            cook_time=req.cook_time,
            servings=req.servings,
            notes=req.notes,
            photo_data=req.photo_data,
            image_url=req.image_url,
            paprika_email=current_user.paprika_email,
            paprika_password_enc=current_user.paprika_password_enc,
        )
    except Exception:
        logger.exception("Sync failed")
        raise HTTPException(status_code=500, detail="Sync failed")

    return SyncResult(success=True, name=final_name)


@router.get("/me/credentials", response_model=CredentialsStatus)
def get_credentials(current_user: User = Depends(get_current_user)):
    """Return whether the current user has Paprika credentials saved."""
    return CredentialsStatus(
        has_credentials=bool(current_user.paprika_email and current_user.paprika_password_enc),
        paprika_email=current_user.paprika_email or "",
    )


@router.post("/me/credentials", response_model=CredentialsStatus)
def save_credentials(
    req: CredentialsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Encrypt and save Paprika credentials for the current user."""
    current_user.paprika_email = req.paprika_email
    current_user.paprika_password_enc = encrypt_password(req.paprika_password)
    db.commit()
    db.refresh(current_user)
    return CredentialsStatus(
        has_credentials=True,
        paprika_email=current_user.paprika_email or "",
    )
