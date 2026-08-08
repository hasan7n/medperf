from medperf.entities.model import Model
from medperf.tests.mocks.cube import TestCube


class TestContainerModel(Model):
    __test__ = False

    def __init__(self, **kwargs):
        container = kwargs.pop("container", None) or TestCube(id=2).todict()
        defaults = {
            "id": 2,
            "name": "container_model",
            "type": "CONTAINER",
            "container": container,
            "state": "OPERATION",
            "is_valid": True,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class TestAssetModel(Model):
    __test__ = False

    def __init__(self, **kwargs):
        asset = kwargs.pop("asset", None) or {
            "id": 5,
            "name": "asset",
            "asset_hash": "asset_hash",
            "asset_url": "https://test.com/asset.tar.gz",
            "state": "OPERATION",
            "is_valid": True,
        }
        defaults = {
            "id": 4,
            "name": "asset_model",
            "type": "ASSET",
            "asset": asset,
            "state": "OPERATION",
            "is_valid": True,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
