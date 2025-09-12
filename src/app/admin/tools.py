from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.dependencies import get_current_superuser
from ..core.db.database import async_get_db
from ..core.security import TokenType, verify_token
from ..crud.crud_users import crud_users
from ..models.language import Language
from ..models.user import User


router = APIRouter(prefix="/admin/tools", tags=["admin-tools"])


async def _require_admin_from_token(
    token: Annotated[str, Query(description="Bearer access token for admin")],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict:
    token_data = await verify_token(token, TokenType.ACCESS, db)
    if token_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Look up user by username/email
    if "@" in token_data.username_or_email:
        user = await crud_users.get(db=db, email=token_data.username_or_email, is_deleted=False)
    else:
        user = await crud_users.get(db=db, username=token_data.username_or_email, is_deleted=False)

    if not user or not (user.get("is_superuser") if isinstance(user, dict) else getattr(user, "is_superuser", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")

    return {"token": token}


@router.get("/users/{user_id}/languages", response_class=HTMLResponse)
async def edit_user_languages_page(
    request: Request,
    user_id: int,
    auth: Annotated[dict, Depends(_require_admin_from_token)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
):
    # Fetch catalog languages
    result = await db.execute(select(Language).order_by(Language.name))
    all_langs = result.scalars().all()

    # Fetch user's existing language names
    result = await db.execute(
        select(Language.name).join(User.languages).where(User.id == user_id)
    )
    user_langs = {row[0] for row in result.all()}

    token = auth["token"]

    # Render a minimal HTML form
    items_html = "".join(
        f'<label style="display:block;margin:4px 0">'
        f'<input type="checkbox" name="language_names" value="{lang.name}"'
        f' {"checked" if lang.name in user_langs else ""}> {lang.name}'
        f"</label>"
        for lang in all_langs
    )

    html = f"""
    <html>
      <head>
        <title>Assign Languages</title>
        <meta charset="utf-8" />
        <style>
          body {{ font-family: sans-serif; margin: 24px; }}
          .container {{ max-width: 640px; }}
          input[type=text] {{ width: 100%; padding: 8px; margin-top: 8px; }}
          button {{ padding: 8px 12px; margin-top: 12px; }}
        </style>
      </head>
      <body>
        <div class="container">
          <h2>Assign Languages to User #{user_id}</h2>
          <form method="post" action="/admin-tools/users/{user_id}/languages?token={token}">
            <h3>Catalog Languages</h3>
            <div>{items_html}</div>
            <h3>Add New Languages (comma-separated)</h3>
            <input type="text" name="new_language_names" placeholder="e.g., Efik, Bini" />
            <div>
              <button type="submit">Save</button>
              <a href="/admin/User/update/{user_id}" style="margin-left:8px">Back to Admin</a>
            </div>
          </form>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/users/{user_id}/languages")
async def update_user_languages_action(
    request: Request,
    user_id: int,
    auth: Annotated[dict, Depends(_require_admin_from_token)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    language_names: list[str] | None = Form(default=None),
    new_language_names: str | None = Form(default=None),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    names: set[str] = set(language_names or [])
    if new_language_names:
        for part in new_language_names.split(","):
            name = part.strip()
            if name:
                names.add(name)

    # Resolve or create languages
    resolved: list[Language] = []
    for name in sorted(names):
        lang = await db.get(Language, name)
        if not lang:
            lang = Language(name=name)
            db.add(lang)
            await db.flush()
        resolved.append(lang)

    # Replace associations
    user.languages.clear()
    for lang in resolved:
        user.languages.append(lang)

    await db.commit()

    # Redirect back to admin user page
    return RedirectResponse(url=f"/admin/User/update/{user_id}", status_code=status.HTTP_303_SEE_OTHER)
