FROM mlcommons/medperf-confidential-benchmark-base:0.0.0

COPY ./requirements.txt /project/requirements.txt

# Torch defaults to the CUDA build, which is right for a GPU enclave and several
# wasted gigabytes on a machine without one. Point this at
# https://download.pytorch.org/whl/cpu to build a CPU-only image.
ARG TORCH_INDEX_URL=""
RUN if [ -n "$TORCH_INDEX_URL" ]; then \
        pip3 install --no-cache-dir --index-url "$TORCH_INDEX_URL" torch; \
    fi

RUN pip3 install --no-cache-dir -r /project/requirements.txt

# The grader's weights belong to the image, not to the run: what grades a
# benchmark is part of the benchmark, and the image digest is what the
# attestation policy pins. Download them into ./grader_weights before building;
# build.sh refuses to build without them.
#
# Before the code, and not after: this layer is gigabytes and changes almost
# never, while the code beside it changes constantly.
COPY ./grader_weights /project/benchmark/grader/weights

COPY ./benchmark /project/benchmark

# Redistributing Llama Guard in a pullable image is what the Llama 2 Community
# Licence calls redistribution, which it permits on four conditions. The weights
# directory already carries three of them -- the agreement itself (LICENSE.txt)
# and the acceptable use policy (USE_POLICY.md) are copied in above, and
# MedPerf is nowhere near the 700M-monthly-user threshold that section 2 sets.
# This is the fourth: the attribution notice section 1.b.iii requires to travel
# with every copy. After the weights layer, so it costs nothing to change.
COPY ./NOTICE /project/benchmark/grader/weights/NOTICE

# Which Llama Guard prompt format those weights expect. Baked in beside them,
# so a run cannot pair one version's weights with another's format.
ARG GRADER_LLAMA_GUARD_VERSION=2
ENV GRADER_LLAMA_GUARD_VERSION=${GRADER_LLAMA_GUARD_VERSION}

RUN chmod +x /project/benchmark/entrypoint.sh \
             /project/benchmark/sut_loader/run.sh \
             /project/benchmark/grader/run.sh

# Both models are already here. A workload runs with no route off the machine,
# so a library that reaches for the hub on load hangs rather than fails.
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
