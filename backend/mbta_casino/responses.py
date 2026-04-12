from rest_framework.response import Response


def error_response(display_message, detail=None, status_code=400):
    """
    Build a consistent error response envelope.

    display_message  -- human-readable message safe to show in the UI
    detail           -- optional extra context for debugging; the UI must not rely on this
    status_code      -- HTTP status code
    """
    body = {"error_display_message": display_message}
    if detail is not None:
        body["error_detail"] = detail
    return Response(body, status=status_code)
