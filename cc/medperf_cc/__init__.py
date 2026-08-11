"""Confidential computing components used by MedPerf.

Nothing here knows what a benchmark, a dataset or a model is. A caller
translates its own domain into a workload identity and an asset policy, and
these components take care of storing an encrypted asset, deciding which
workloads may have its key, and running one.
"""
