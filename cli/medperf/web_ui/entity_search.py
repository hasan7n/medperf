from typing import List, Optional

from medperf.account_management import get_medperf_user_data
from medperf.entities.aggregator import Aggregator
from medperf.entities.benchmark import Benchmark
from medperf.entities.cube import Cube
from medperf.entities.model import Model
from medperf.entities.training_exp import TrainingExp
from medperf.web_ui.utils import (
    MIN_SEARCH_LENGTH,
    get_container_type,
    normalize_search_query,
)

ENTITY_TYPES = {
    "benchmark": Benchmark,
    "model": Model,
    "container": Cube,
    "aggregator": Aggregator,
    "training": TrainingExp,
}

CONTAINER_TYPE_FILTERS = {
    "data-prep-container",
    "metrics-container",
    "reference-container",
    "non-data-prep-container",
}


def _entity_option(entity, entity_type: str = "") -> dict:
    name = entity.name or ""
    label = f"{name} (ID: {entity.id})"
    if entity_type == "aggregator":
        address = getattr(entity, "address", None)
        port = getattr(entity, "port", None)
        if address is not None and port is not None:
            label = f"{name} (ID: {entity.id}) ({address}:{port})"
    return {"id": entity.id, "name": name, "label": label}


def _filter_container_type(containers: list, container_type: Optional[str]) -> list:
    if not container_type or container_type not in CONTAINER_TYPE_FILTERS:
        return containers

    typed = []
    for container in containers:
        ctype = get_container_type(container)
        if container_type == "non-data-prep-container":
            if ctype != "data-prep-container":
                typed.append(container)
        elif ctype == container_type:
            typed.append(container)
    return typed


def _filter_model_type(models: list, model_type: Optional[str]) -> list:
    """Restricts a model search to assets or containers.

    A benchmark's topology accepts only one kind, so the picker should not
    offer the other one."""
    if not model_type:
        return models
    return [model for model in models if model.type == model_type]


def _apply_allowed_ids(items: list, allowed_ids: Optional[List[int]]) -> list:
    if not allowed_ids:
        return items
    allowed = set(allowed_ids)
    return [item for item in items if item.id in allowed]


def search_entities(  # noqa
    entity_type: str,
    *,
    q: Optional[str] = None,
    mine_only: bool = False,
    container_type: Optional[str] = None,
    model_type: Optional[str] = None,
    limit: int = 20,
    selected_id: Optional[int] = None,
    allowed_ids: Optional[List[int]] = None,
) -> dict:
    if entity_type not in ENTITY_TYPES:
        return {"results": [], "error": f"Unknown entity type: {entity_type}"}

    entity_cls = ENTITY_TYPES[entity_type]
    query = normalize_search_query(q)
    limit = max(1, min(limit, 50))

    if selected_id is not None:
        try:
            entity = entity_cls.get(selected_id)
            if allowed_ids is not None and entity.id not in allowed_ids:
                return {"results": []}
            if entity_type == "container" and container_type:
                filtered = _filter_container_type([entity], container_type)
                if not filtered:
                    return {"results": []}
            if entity_type == "model" and model_type:
                if not _filter_model_type([entity], model_type):
                    return {"results": []}
            return {"results": [_entity_option(entity, entity_type)]}
        except Exception:
            return {"results": []}

    if len(query) < MIN_SEARCH_LENGTH:
        return {
            "results": [],
            "hint": f"Type at least {MIN_SEARCH_LENGTH} characters to search",
        }

    filters = {"search": query, "limit": limit, "offset": 0, "ordering": "name"}
    my_user_id = get_medperf_user_data()["id"]
    if mine_only:
        filters["owner"] = my_user_id

    items = entity_cls.all(filters=filters)
    items = _apply_allowed_ids(items, allowed_ids)

    if entity_type == "container":
        items = _filter_container_type(items, container_type)
        items = items[:limit]

    if entity_type == "model":
        items = _filter_model_type(items, model_type)
        items = items[:limit]

    return {"results": [_entity_option(item, entity_type) for item in items]}
