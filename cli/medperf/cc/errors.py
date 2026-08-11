"""Presenting confidential computing failures as MedPerf ones.

`medperf_cc` raises its own exceptions, since it does not depend on the client.
The client only recognizes `MedperfException`, so the glue translates at the
boundary rather than letting a traceback reach the user.
"""

import functools

from medperf.exceptions import MedperfException
from medperf_cc.errors import CCError


def as_medperf_error(exception_class=MedperfException):
    """Re-raises any `CCError` the wrapped function lets out.

    Execution flows pass `ExecutionError`, which the benchmark runner reports
    per model instead of abandoning the whole run."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CCError as e:
                raise exception_class(str(e))

        return wrapper

    return decorator
