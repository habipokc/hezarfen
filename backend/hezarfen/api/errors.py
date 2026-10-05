"""ICD §7.1: every non-2xx API response is {"error": {"code", "message", "details"}}."""

import logging

from django.db import OperationalError
from django.http import Http404, JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

log = logging.getLogger(__name__)

# ValidationError codes that are promoted to the top-level error code (ICD §7.1 table);
# any other validation failure is reported as invalid_parameter.
PROMOTED_CODES = {"invalid_bbox", "invalid_parameter", "window_too_large", "invalid_geometry"}


class ApiError(exceptions.APIException):
    """An API error with an explicit ICD code; raise it from views and helpers."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str, message: str, details: dict | None = None, status_code=None):
        super().__init__(detail=message, code=code)
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code


def error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _flat_codes(codes) -> list[str]:
    if isinstance(codes, dict):
        return [c for v in codes.values() for c in _flat_codes(v)]
    if isinstance(codes, list):
        return [c for v in codes for c in _flat_codes(v)]
    return [str(codes)]


def _first_message(detail) -> str:
    if isinstance(detail, dict):
        for key, value in detail.items():
            msg = _first_message(value)
            return msg if key == "non_field_errors" else f"{key}: {msg}"
    if isinstance(detail, list) and detail:
        return _first_message(detail[0])
    return str(detail)


def exception_handler(exc, context):
    if isinstance(exc, ApiError):
        return Response(error_body(exc.code, exc.message, exc.details), status=exc.status_code)

    if isinstance(exc, exceptions.ValidationError):
        codes = _flat_codes(exc.get_codes())
        code = next((c for c in codes if c in PROMOTED_CODES), "invalid_parameter")
        return Response(
            error_body(code, _first_message(exc.detail), exc.detail),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, OperationalError):
        log.error("database unavailable: %s", exc)
        return Response(
            error_body("unavailable", "database unavailable"),
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # unexpected error: let Django log it and answer 500
    if isinstance(exc, Http404 | exceptions.NotFound):
        code, message = "not_found", "not found"
    else:
        code = getattr(exc, "default_code", "error")
        message = str(getattr(exc, "detail", exc))
    response.data = error_body(code, message)
    return response


def not_found(request, *args, **kwargs):
    """Catch-all for unknown /api/ paths, so even a typo gets the ICD error shape."""
    return JsonResponse(error_body("not_found", f"no such endpoint: {request.path}"), status=404)
