class SearchableOrderingListMixin:
    """Shared search and ordering configuration for entity list endpoints."""

    search_fields = ["name"]
    ordering_fields = ["name", "-name", "created_at", "-created_at"]
