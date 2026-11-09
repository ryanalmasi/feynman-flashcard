from typing import cast

from fastapi import Request

from feynman_api.auth.breach import BreachChecker


def get_breach_checker(request: Request) -> BreachChecker:
    return cast(BreachChecker, request.app.state.breach_checker)
