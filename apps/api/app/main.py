from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.database import build_engine, build_session_factory
from app.middleware.body_limit import BodyLimitMiddleware
from app.middleware.error_handler import register_error_handlers
from app.middleware.rate_limit import FixedWindowLimiter, RateLimitMiddleware, Rule
from app.middleware.request_context import RequestContextMiddleware
from app.routers import admin, health, photos, safety, spots
from app.schemas.common import ErrorResponse
from app.services.cloudinary_service import CloudinaryUploader, UnconfiguredUploader, Uploader
from app.services.firebase_auth import FirebaseTokenVerifier, TokenVerifier, UnconfiguredVerifier
from app.utils.log import configure_logging

JSON_BODY_LIMIT = 64 * 1024
MULTIPART_OVERHEAD = 64 * 1024


def default_rate_limit_overrides() -> dict[tuple[str, str], Rule]:
    # Per-IP ceilings. Deliberately above the per-user limits: carrier NAT puts many Nigerian
    # mobile users behind one address, and the per-user limit is the one that bites abusers.
    return {
        ("POST", "/api/spots"): Rule(30, 3600),
        ("POST", "/api/safety-reports"): Rule(60, 3600),
        ("POST", "/api/photos"): Rule(60, 3600),
    }


def create_app(
    settings: Settings | None = None,
    *,
    token_verifier: TokenVerifier | None = None,
    uploader: Uploader | None = None,
    rate_limit_overrides: dict[tuple[str, str], Rule] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings)

    if token_verifier is None:
        token_verifier = (
            FirebaseTokenVerifier(settings.firebase_project_id)
            if settings.firebase_project_id
            else UnconfiguredVerifier()
        )
    if uploader is None:
        uploader = (
            CloudinaryUploader(
                settings.cloudinary_cloud_name,
                settings.cloudinary_api_key.get_secret_value(),
                settings.cloudinary_api_secret.get_secret_value(),
            )
            if settings.cloudinary_cloud_name
            and settings.cloudinary_api_key
            and settings.cloudinary_api_secret
            else UnconfiguredUploader()
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()
        if isinstance(token_verifier, FirebaseTokenVerifier):
            await token_verifier.aclose()

    production = settings.environment == "production"
    app = FastAPI(
        title="Spotfinder API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if production else "/api/docs",
        redoc_url=None,
        openapi_url=None if production else "/api/openapi.json",
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.token_verifier = token_verifier
    app.state.uploader = uploader
    app.state.limiter = FixedWindowLimiter()

    register_error_handlers(app)

    # add_middleware wraps outward: the last one added runs first. Order, outermost first:
    # CORS, request context, rate limit, body limit.
    app.add_middleware(
        BodyLimitMiddleware,
        default_limit=JSON_BODY_LIMIT,
        overrides={"/api/photos": settings.max_upload_bytes + MULTIPART_OVERHEAD},
    )
    app.add_middleware(
        RateLimitMiddleware,
        limiter=app.state.limiter,
        default=Rule(settings.write_rate_limit_per_minute, 60),
        overrides=(
            default_rate_limit_overrides() if rate_limit_overrides is None else rate_limit_overrides
        ),
        trusted_proxy_count=settings.trusted_proxy_count,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # bearer tokens travel in a header, never in cookies
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )

    app.include_router(health.router)
    app.include_router(spots.router)
    app.include_router(safety.router)
    app.include_router(photos.router)
    app.include_router(admin.router)
    return app
