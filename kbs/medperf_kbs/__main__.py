"""Run the broker: `python -m medperf_kbs`."""

import os

import uvicorn

from medperf_kbs.app import create_app


def main():
    uvicorn.run(
        create_app(),
        host=os.getenv("MEDPERF_KBS_HOST", "0.0.0.0"),
        port=int(os.getenv("MEDPERF_KBS_PORT", "8200")),
        ssl_keyfile=os.getenv("MEDPERF_KBS_TLS_KEY"),
        ssl_certfile=os.getenv("MEDPERF_KBS_TLS_CERT"),
    )


if __name__ == "__main__":
    main()
