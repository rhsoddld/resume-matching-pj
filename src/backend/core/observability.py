from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

try:
    from langsmith import traceable as _langsmith_traceable
    from langsmith import tracing_context as _langsmith_tracing_context
except Exception:
    _langsmith_traceable = None
    _langsmith_tracing_context = None

try:
    from ops.logging import request_id_ctx as _request_id_ctx
except Exception:
    _request_id_ctx = None


def _current_request_id() -> str | None:
    if _request_id_ctx is None:
        return None
    value = _request_id_ctx.get("-")
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token or token == "-":
        return None
    return token


def traceable_op(
    *,
    name: str,
    run_type: str = "chain",
    tags: list[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Safe LangSmith trace decorator.
    Falls back to a no-op decorator when LangSmith is unavailable.
    """
    if _langsmith_traceable is None:
        def _noop_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func
        return _noop_decorator

    base_decorator = _langsmith_traceable(name=name, run_type=run_type, tags=tags or [])

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        traced_func = base_decorator(func)

        if _langsmith_tracing_context is None:
            return traced_func

        if inspect.iscoroutinefunction(traced_func):
            @functools.wraps(traced_func)
            async def _async_wrapped(*args: Any, **kwargs: Any) -> Any:
                request_id = _current_request_id()
                if request_id is None:
                    return await traced_func(*args, **kwargs)
                with _langsmith_tracing_context(
                    metadata={"request_id": request_id},
                    tags=[f"request_id:{request_id}"],
                ):
                    return await traced_func(*args, **kwargs)

            return _async_wrapped

        @functools.wraps(traced_func)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            request_id = _current_request_id()
            if request_id is None:
                return traced_func(*args, **kwargs)
            with _langsmith_tracing_context(
                metadata={"request_id": request_id},
                tags=[f"request_id:{request_id}"],
            ):
                return traced_func(*args, **kwargs)

        return _wrapped

    return _decorator
