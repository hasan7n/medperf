from medperf.utils import dict_pretty_print, approval_prompt
from medperf.entities.result import Result
from medperf.entities.dataset import Dataset
from medperf.enums import Status
from medperf import config


class ResultSubmission:
    @classmethod
    def run(cls, benchmark_uid, data_uid, model_uid, approved=False):

        dset = Dataset.from_generated_uid(data_uid)
        result = Result.from_entities_uids(benchmark_uid, model_uid, dset.uid)
        dict_pretty_print(result.results)
        config.ui.print("Above are the results generated by the model")
        approved = (
            approved
            or result.status == Status.APPROVED
            or approval_prompt(
                "Do you approve uploading the presented results to the MLCommons comms? [Y/n]"
            )
        )

        if approved:
            updated_result_dict = result.upload()
            result = Result(updated_result_dict)
            result.write()
        else:
            config.ui.print("Results upload operation cancelled")
