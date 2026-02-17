"""API route definitions."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .auth import verify_token
from .schemas import (
    CategoriesResponse,
    CategoryItem,
    ImportResult,
    ImportUrlRequest,
    RecipeResponse,
    SyncRequest,
    SyncResult,
)
from .services import get_categories, import_from_images, import_from_url, sync_recipe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", dependencies=[Depends(verify_token)])


@router.post("/import/url", response_model=ImportResult)
async def import_url(req: ImportUrlRequest):
    try:
        result = await import_from_url(req.url)
    except Exception as e:
        logger.exception("URL import failed")
        raise HTTPException(status_code=500, detail=str(e))

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
            )
            recipe.name = final_name
            return ImportResult(recipe=recipe, synced=True)
        except Exception as e:
            logger.exception("Quick sync failed")
            # Return the recipe anyway, just not synced
            return ImportResult(recipe=recipe, synced=False)

    return ImportResult(recipe=recipe)


@router.post("/import/images", response_model=ImportResult)
async def import_images(
    images: list[UploadFile] = File(...),
    quick: bool = Form(False),
):
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    image_files = []
    for img in images:
        data = await img.read()
        image_files.append((img.filename or "image.jpg", data))

    try:
        result = await import_from_images(image_files)
    except Exception as e:
        logger.exception("Image import failed")
        raise HTTPException(status_code=500, detail=str(e))

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
            )
            recipe.name = final_name
            return ImportResult(recipe=recipe, synced=True)
        except Exception as e:
            logger.exception("Quick sync failed")
            return ImportResult(recipe=recipe, synced=False)

    return ImportResult(recipe=recipe)


@router.get("/categories", response_model=CategoriesResponse)
async def list_categories():
    try:
        cats = await get_categories()
    except Exception as e:
        logger.exception("Failed to fetch categories")
        raise HTTPException(status_code=500, detail=str(e))

    return CategoriesResponse(
        categories=[CategoryItem(**c) for c in cats]
    )


@router.post("/sync", response_model=SyncResult)
async def sync(req: SyncRequest):
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
        )
    except Exception as e:
        logger.exception("Sync failed")
        raise HTTPException(status_code=500, detail=str(e))

    return SyncResult(success=True, name=final_name)
