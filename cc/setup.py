from setuptools import find_packages, setup


def read_requirements(path):
    with open(path, "r") as f:
        requires = []
        for line in f:
            req = line.split("#", 1)[0].strip()
            if req and not req.startswith("--"):
                requires.append(req)
    return requires


setup(
    name="medperf-cc",
    version="1.0.0",
    description="Confidential computing components used by MedPerf",
    url="https://github.com/mlcommons/medperf",
    author="MLCommons",
    license="Apache 2.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    # Kept small on purpose: a key broker depends on this package and needs
    # nothing but the protocol, so the cloud libraries live behind an extra.
    install_requires=read_requirements("requirements.txt"),
    extras_require={"gcp": read_requirements("requirements-gcp.txt")},
    python_requires=">=3.9",
)
