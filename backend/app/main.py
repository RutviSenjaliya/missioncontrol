"""FastAPI application entry point."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.services.errors import ApprovalRequired, Conflict, DomainError, Forbidden, InvalidInput, NotFound

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

_STATUS = {NotFound: 404, Forbidden: 403, InvalidInput: 422, ApprovalRequired: 409, Conflict: 409}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MissionControl API", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError):
        return JSONResponse(status_code=_STATUS.get(type(exc), 400), content={"detail": exc.message, "code": exc.code})

    app.include_router(router)
    return app


app = create_app()
