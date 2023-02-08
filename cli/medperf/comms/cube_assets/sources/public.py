import requests
from medperf.exceptions import CommunicationRetrievalError
from medperf import config
from medperf.utils import log_response_error


class PublicSource:
    prefix = "public"

    def __init__(self):
        pass

    def authenticate(self):
        pass

    def download(self, resource_identifier: str, output_path: str):
        """Downloads a direct-download-link file by streaming its contents. source:
        https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
        """
        with requests.get(resource_identifier, stream=True) as res:
            if res.status_code != 200:
                log_response_error(res)
                msg = (
                    "There was a problem retrieving the specified file at "
                    + resource_identifier
                )
                raise CommunicationRetrievalError(msg)

            with open(output_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=config.ddl_stream_chunk_size):
                    # NOTE: if the response is chunk-encoded, this may not work
                    # check whether this is common.
                    f.write(chunk)