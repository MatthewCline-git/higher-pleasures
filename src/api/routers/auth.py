from fastapi import APIRouter


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/login")
async def login() -> None:
    """Log in user."""
