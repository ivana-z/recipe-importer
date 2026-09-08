"""API route definitions."""

import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import User
from .oauth import encrypt_password
from .schemas import (
    AppVersion,
    CategoriesResponse,
    CategoryItem,
    CredentialsRequest,
    CredentialsStatus,
    ImportResult,
    ImportTextRequest,
    ImportUrlRequest,
    RecipeResponse,
    SyncRequest,
    SyncResult,
)
from .services import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_COUNT,
    get_categories,
    import_from_images,
    import_from_text,
    import_from_url,
    sync_recipe,
)
from .source_errors import SourceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/version", response_model=AppVersion)
def get_app_version(_current_user: User = Depends(get_current_user)):
    """Return the Git revision that produced the running deployment."""
    raw_message = os.environ.get("RAILWAY_GIT_COMMIT_MESSAGE", "")
    message = next(
        (line.strip() for line in raw_message.splitlines() if line.strip()),
        "Development build",
    )
    commit_sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "").strip()[:7]
    return AppVersion(message=message, commit_sha=commit_sha)


@router.post("/import/url", response_model=ImportResult)
async def import_url(
    req: ImportUrlRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await import_from_url(req.validated_url())
    except SourceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except Exception:
        logger.exception("URL import failed")
        raise HTTPException(status_code=500, detail="Import failed")

    return _import_result(result)


@router.post("/import/text", response_model=ImportResult)
async def import_text(
    req: ImportTextRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await import_from_text(req.text)
    except SourceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except Exception:
        logger.exception("Text import failed")
        raise HTTPException(status_code=500, detail="Import failed")

    return _import_result(result)


@router.post("/import/images", response_model=ImportResult)
async def import_images(
    images: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")
    if len(images) > MAX_IMAGE_COUNT:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "too_many_images",
                "message": f"Upload no more than {MAX_IMAGE_COUNT} images at a time.",
            },
        )

    image_files = []
    for img in images:
        data = await img.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "image_too_large",
                    "message": (
                        f"Each image must be "
                        f"{MAX_IMAGE_BYTES // (1024 * 1024)} MB or smaller."
                    ),
                },
            )
        image_files.append((img.filename or "image.jpg", data))

    try:
        result = await import_from_images(image_files)
    except SourceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except Exception:
        logger.exception("Image import failed")
        raise HTTPException(status_code=500, detail="Import failed")

    return _import_result(result)


def _import_result(result: dict) -> ImportResult:
    return ImportResult(
        recipes=[RecipeResponse(**recipe) for recipe in result["recipes"]]
    )


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
