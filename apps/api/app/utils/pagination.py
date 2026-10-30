from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_OFFSET = 100_000


@dataclass(frozen=True)
class PageParams:
    limit: int
    offset: int


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Items per page.")] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET, description="Items to skip.")] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


Pagination = Annotated[PageParams, Depends(page_params)]
