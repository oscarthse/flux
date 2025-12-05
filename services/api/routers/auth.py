from fastapi import APIRouter, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from services.api.database import db_service
from services.api.logging_config import get_logger
from services.api import security, seeding
import uuid

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="services/api/templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("auth/signup.html", {"request": request})

from services.api.config import settings

@router.post("/signup")
async def signup(
    request: Request,
    restaurant_name: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        # Atomic Transaction: Tenant -> User -> Seed Data
        # use_rls=False initially because we are creating the tenant
        with db_service.get_connection(use_rls=False) as conn:
            with conn.cursor() as cur:
                # 1. Create Tenant
                tenant_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO tenants (id, name) VALUES (%s, %s) RETURNING id",
                    (tenant_id, restaurant_name)
                )

                # 2. Set RLS Context IMMEDIATELY (CRITICAL for user insert to work)
                cur.execute("SET app.current_tenant = %s", (tenant_id,))

                # 3. Create User (now RLS policy will pass)
                user_id = str(uuid.uuid4())
                password_hash = security.get_password_hash(password)

                # Insert user (RLS now sees current_tenant matching tenant_id)
                cur.execute(
                    """
                    INSERT INTO users (id, tenant_id, email, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s, %s, 'owner')
                    """,
                    (user_id, tenant_id, email, password_hash, full_name)
                )

                # 4. Seed Initial Data
                seeding.seed_tenant_data(tenant_id, cursor=cur)

        logger.info(f"Created new tenant {restaurant_name} and user {email}")

        # 5. Auto-Login (Set Signed Cookie)
        session_data = {"user_id": user_id, "tenant_id": tenant_id}
        token = security.sign_session_cookie(session_data)

        # HTMX Redirect Support
        if request.headers.get("HX-Request"):
            response = Response(status_code=200)
            response.headers["HX-Redirect"] = "/dashboard"
        else:
            response = RedirectResponse(url="/dashboard", status_code=303)

        response.set_cookie(
            key="flux_session",
            value=token,
            httponly=True,
            secure=False, # FORCE FALSE as requested for debugging
            samesite="lax",
            max_age=86400 * 14
        )
        return response

    except Exception as e:
        logger.error(f"Signup failed: {e}")
        return templates.TemplateResponse("auth/signup.html", {
            "request": request,
            "error": f"Registration failed: {str(e)}"
        })

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        # use_rls=False to ensure we can lookup users without a tenant context
        with db_service.get_connection(use_rls=False) as conn:
            with conn.cursor() as cur:
                # Use SECURITY DEFINER function to bypass RLS for login lookup
                # (Even with use_rls=False, if the table has RLS, we need this or superuser)
                cur.callproc('get_user_by_email', (email,))
                user = cur.fetchone()

                logger.info(f"Login DEBUG - user result: {user}")

                if user and security.verify_password(password, user[2]):
                    user_id, tenant_id = user[0], user[1]
                    logger.info(f"Login DEBUG - Extracted user_id: {user_id}, tenant_id: {tenant_id}")

                    # HTMX Redirect Support
                    if request.headers.get("HX-Request"):
                        response = Response(status_code=200)
                        response.headers["HX-Redirect"] = "/dashboard"
                    else:
                        response = RedirectResponse(url="/dashboard", status_code=303)

                    session_data = {"user_id": str(user_id), "tenant_id": str(tenant_id)}
                    logger.info(f"Login DEBUG - session_data: {session_data}")
                    token = security.sign_session_cookie(session_data)

                    response.set_cookie(
                        key="flux_session",
                        value=token,
                        httponly=True,
                        secure=False, # FORCE FALSE as requested
                        samesite="lax",
                        max_age=86400 * 14
                    )
                    return response

                return templates.TemplateResponse("auth/login.html", {
                    "request": request,
                    "error": "Invalid credentials"
                })

    except Exception as e:
        logger.error(f"Login failed: {e}")
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Login failed"
        })

@router.api_route("/logout", methods=["GET", "POST"])
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("flux_session")
    return response
