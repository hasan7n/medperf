from setuptools import find_packages, setup

with open("requirements.txt", "r") as f:
    requires = []
    for line in f:
        req = line.split("#", 1)[0].strip()
        if req and not req.startswith("--"):
            requires.append(req)

setup(
    name="medperf-kbs",
    version="1.0.0",
    description="An on-prem key broker for MedPerf confidential computing",
    url="https://github.com/mlcommons/medperf",
    author="MLCommons",
    license="Apache 2.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    # Also needs medperf-cc, a sibling package in this repo, for the protocol
    # and nothing else. Left out of install_requires only because it is not
    # published to PyPI: install it with `pip install -e ../cc`.
    #
    # Deliberately not the MedPerf client: depending on it would pull a
    # dashboard, a dataframe library and the whole google-cloud stack into a
    # service whose job is to hold one key and refuse most requests for it.
    install_requires=requires,
    python_requires=">=3.9",
    entry_points="""
        [console_scripts]
        medperf_kbs=medperf_kbs.__main__:main
        """,
)
