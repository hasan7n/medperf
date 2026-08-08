from enum import Enum


class Role(Enum):
    BENCHMARK_OWNER = "BenchmarkOwner"
    DATA_OWNER = "DataOwner"
    MODEL_OWNER = "ModelOwner"
    NONE = None


class Status(Enum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class AutoApprovalMode(Enum):
    NEVER = "NEVER"
    ALWAYS = "ALWAYS"
    ALLOWLIST = "ALLOWLIST"


class ContainerTypes(Enum):
    MLCUBE = "mlcube"
    SINGULARITY_FILE = "SingularityFile"
    DOCKER_IMAGE = "DockerImage"
    DOCKER_ARCHIVE = "DockerArchive"
    ENCRYPTED_DOCKER_ARCHIVE = "EncryptedDockerArchive"
    ENCRYPTED_SINGULARITY_FILE = "EncryptedSingularityFile"


class ModelType(Enum):
    ASSET = "ASSET"
    CONTAINER = "CONTAINER"


class CryptoKeyType(Enum):
    RSA = "RSA"
    EC = "EC"


class BenchmarkTopology(Enum):
    """How a benchmark's parts fit together: who produces predictions and who
    evaluates them. This is a property of the benchmark, independent of where
    the execution physically happens (see `ExecutionMedium`)."""

    # Models bring their own inference container. The benchmark only supplies
    # the evaluator that consumes their predictions.
    BYO_INFERENCE_SCRIPT = "byo_inference_script"

    # Models are assets (weights). A single benchmark-owned script container
    # loads the asset, runs inference and computes the metrics in one step.
    END_TO_END_SCRIPT = "end_to_end_script"

    # Models are assets (weights). A benchmark-owned script container loads the
    # asset and produces predictions; a separate evaluator container scores them.
    INFERENCE_SCRIPT = "inference_script"

    @property
    def uses_asset_models(self) -> bool:
        """Whether associated models (and the reference model) are assets."""
        return self is not BenchmarkTopology.BYO_INFERENCE_SCRIPT

    @property
    def requires_evaluator(self) -> bool:
        return self is not BenchmarkTopology.END_TO_END_SCRIPT

    @property
    def requires_benchmark_script(self) -> bool:
        return self is not BenchmarkTopology.BYO_INFERENCE_SCRIPT


class ExecutionMedium(Enum):
    """Where an execution physically runs. Orthogonal to `BenchmarkTopology`."""

    LOCAL = "local"
    CONFIDENTIAL = "confidential"
