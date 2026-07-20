import os

import medperf.config as config
from medperf.exceptions import InvalidArgumentError
from medperf.utils import sanitize_path, validate_and_normalize_emails


class UpdateCommitteeMembers:
    @classmethod
    def run(
        cls,
        benchmark_uid: int,
        committee_emails_file: str = None,
        committee_emails: str = None,
    ):
        """
        committee_emails: a string containing space-separated list of emails
        """
        update_members = cls(
            benchmark_uid,
            committee_emails_file,
            committee_emails,
        )
        update_members.validate()
        update_members.read_emails()
        update_members.validate_emails()
        update_members.update()

    def __init__(
        self,
        benchmark_uid: int,
        committee_emails_file: str = None,
        committee_emails: str = None,
    ):
        self.benchmark_uid = benchmark_uid
        self.committee_emails_file = sanitize_path(committee_emails_file)
        self.committee_emails = committee_emails
        self.committee_emails_list = None

    def validate(self):
        if self.committee_emails_file is not None and self.committee_emails is not None:
            raise InvalidArgumentError("Both a file and a list of emails are provided.")
        if self.committee_emails_file is None and self.committee_emails is None:
            raise InvalidArgumentError("No emails provided.")

        if self.committee_emails_file and not os.path.isfile(
            self.committee_emails_file
        ):
            raise InvalidArgumentError(
                f"File {self.committee_emails_file} does not exist or is a directory"
            )

    def __read_emails_file(self, file):
        with open(file) as f:
            contents = f.read()
        return contents.strip().split("\n")

    def read_emails(self):
        if self.committee_emails_file is not None:
            self.committee_emails_list = self.__read_emails_file(
                self.committee_emails_file
            )
        else:
            self.committee_emails_list = self.committee_emails.strip().split(" ")

    def validate_emails(self):
        self.committee_emails_list = validate_and_normalize_emails(
            self.committee_emails_list
        )

    def update(self):
        config.comms.update_benchmark(
            self.benchmark_uid,
            {"committee_member_emails": self.committee_emails_list},
        )
