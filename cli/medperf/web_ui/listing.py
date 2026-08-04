from typing import Optional

from medperf.web_ui.utils import (
    apply_listing_search,
    build_listing_filters,
    build_pagination_context,
)


def fetch_listing_page(
    entity_cls,
    *,
    page: int,
    page_size: int,
    ordering: str,
    mine_only: bool,
    my_user_id: int,
    search: Optional[str] = None,
):
    filters = {}
    if mine_only:
        filters["owner"] = my_user_id

    filters, search_query = apply_listing_search(filters, search)
    total_count = entity_cls.get_count(filters=filters)

    filters.update(
        build_listing_filters(page=page, page_size=page_size, ordering=ordering)
    )
    items = entity_cls.all(filters=filters)

    pagination_context = build_pagination_context(
        page=page,
        page_size=page_size,
        ordering=ordering,
        total_count=total_count,
        page_items_count=len(items),
    )

    return items, search_query, pagination_context
