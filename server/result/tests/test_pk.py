from rest_framework import status

from medperf.tests import MedPerfTest

from parameterized import parameterized, parameterized_class


class ResultsTest(MedPerfTest):
    def generic_setup(self):
        # setup users
        data_owner = "data_owner"
        model_owner = "model_owner"
        bmk_owner = "bmk_owner"
        bmk_prep_mlcube_owner = "bmk_prep_mlcube_owner"
        ref_model_owner = "ref_model_owner"
        eval_mlcube_owner = "eval_mlcube_owner"
        committee_user = "committee_user"
        other_user = "other_user"

        self.create_user(data_owner)
        self.create_user(model_owner)
        self.create_user(bmk_owner)
        self.create_user(bmk_prep_mlcube_owner)
        self.create_user(ref_model_owner)
        self.create_user(eval_mlcube_owner)
        committee_user_info = self.create_user(committee_user)
        self.create_user(other_user)

        # create benchmark
        prep, _, _, benchmark = self.shortcut_create_benchmark(
            bmk_prep_mlcube_owner,
            ref_model_owner,
            eval_mlcube_owner,
            bmk_owner,
            committee_member_emails=[committee_user_info["email"]],
        )

        # create dataset
        self.set_credentials(data_owner)
        dataset = self.mock_dataset(
            data_preparation_mlcube=prep["id"], state="OPERATION"
        )
        dataset = self.create_dataset(dataset).data

        # create dataset assoc
        assoc = self.mock_dataset_association(
            benchmark["id"], dataset["id"], approval_status="APPROVED"
        )
        self.create_dataset_association(assoc, data_owner, bmk_owner)

        # create model model
        self.set_credentials(model_owner)
        model = self.mock_model(state="OPERATION")
        model = self.create_model(model).data

        # create model assoc
        assoc = self.mock_model_association(
            benchmark["id"], model["id"], approval_status="APPROVED"
        )
        self.create_model_association(assoc, model_owner, bmk_owner)

        # setup globals
        self.data_owner = data_owner
        self.model_owner = model_owner
        self.bmk_owner = bmk_owner
        self.bmk_prep_mlcube_owner = bmk_prep_mlcube_owner
        self.ref_model_owner = ref_model_owner
        self.eval_mlcube_owner = eval_mlcube_owner
        self.committee_user = committee_user
        self.other_user = other_user

        self.bmk_id = benchmark["id"]
        self.dataset_id = dataset["id"]
        self.model_id = model["id"]

        self.url = self.api_prefix + "/results/{0}/"
        self.set_credentials(None)

    def confidential_setup(self, topology="end_to_end_script", asset_url="local"):
        """A benchmark whose script computes the metrics inside a confidential
        VM, over a model whose weights are not public.

        Both are what make an execution's result attested, and so submittable by
        somebody other than the dataset owner. The arguments exist so a test can
        take one of them away."""
        self.set_credentials(self.bmk_prep_mlcube_owner)
        prep = self.create_mlcube(
            self.mock_mlcube(
                name="ccprep",
                container_config={"ccprep": "ccprep"},
                state="OPERATION",
            )
        ).data

        self.set_credentials(self.ref_model_owner)
        ref_model = self.create_model(
            self.mock_asset_model(name="cc_ref_model", state="OPERATION")
        ).data

        self.set_credentials(self.eval_mlcube_owner)
        # Every topology but end_to_end_script scores the predictions in a
        # container of its own.
        evaluator = None
        if topology != "end_to_end_script":
            evaluator = self.create_mlcube(
                self.mock_mlcube(
                    name="cceval",
                    container_config={"cceval": "cceval"},
                    state="OPERATION",
                )
            ).data["id"]

        self.set_credentials(self.bmk_owner)
        script = self.create_mlcube(
            self.mock_mlcube(
                name="ccscript",
                container_config={"ccscript": "ccscript"},
                state="OPERATION",
            )
        ).data
        benchmark = self.create_benchmark(
            self.mock_benchmark(
                prep["id"],
                ref_model["id"],
                evaluator,
                name="ccbenchmark",
                topology=topology,
                benchmark_script=script["id"],
            )
        ).data

        self.set_credentials(self.data_owner)
        dataset = self.create_dataset(
            self.mock_dataset(
                data_preparation_mlcube=prep["id"],
                state="OPERATION",
                name="ccdataset",
                generated_uid="ccdataset",
            )
        ).data
        self.create_dataset_association(
            self.mock_dataset_association(
                benchmark["id"], dataset["id"], approval_status="APPROVED"
            ),
            self.data_owner,
            self.bmk_owner,
        )

        self.set_credentials(self.model_owner)
        model = self.create_model(
            self.mock_asset_model(
                name="cc_model", state="OPERATION", asset_url=asset_url
            )
        ).data
        self.create_model_association(
            self.mock_model_association(
                benchmark["id"], model["id"], approval_status="APPROVED"
            ),
            self.model_owner,
            self.bmk_owner,
        )

        self.set_credentials(None)
        return benchmark, dataset, model


@parameterized_class(
    [
        {"actor": "data_owner"},
        {"actor": "bmk_owner"},
        {"actor": "committee_user"},
    ]
)
class ResultGetTest(ResultsTest):
    """Test module for GET /results/<pk>"""

    def setUp(self):
        super(ResultGetTest, self).setUp()
        self.generic_setup()
        self.set_credentials(self.actor)

    def test_generic_get_result(self):
        # Arrange
        result = self.mock_result(
            self.bmk_id, self.model_id, self.dataset_id, results={"r": 1}
        )
        self.set_credentials(self.data_owner)
        result = self.create_result(result).data
        self.set_credentials(self.actor)

        url = self.url.format(result["id"])

        # Act
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for k, v in response.data.items():
            if k in result:
                self.assertEqual(result[k], v, f"Unexpected value for {k}")

    def test_result_not_found(self):
        # Arrange
        invalid_id = 9999
        url = self.url.format(invalid_id)

        # Act
        response = self.client.get(url)

        # Assert
        # TODO: fixme after refactoring permissions. should be 404
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@parameterized_class(
    [
        {"actor": "api_admin"},
        {"actor": "data_owner"},
    ]
)
class ResultPutTest(ResultsTest):
    """Test module for PUT /results/<pk>"""

    def setUp(self):
        super(ResultPutTest, self).setUp()
        self.generic_setup()
        self.set_credentials(self.actor)

    def test_put_does_not_modify_readonly_fields(self):
        # Arrange
        result = self.mock_result(
            self.bmk_id, self.model_id, self.dataset_id, results={"r": 1}
        )
        self.set_credentials(self.data_owner)
        result = self.create_result(result).data
        self.set_credentials(self.actor)

        newtestresult = {
            "owner": 10,
            "approved_at": "some time",
            "created_at": "some time",
            "modified_at": "some time",
            "benchmark": 44,
            "model": 444,
            "dataset": 55,
            "finalized": True,
            "finalized_at": "some_time",
        }
        url = self.url.format(result["id"])

        # Act
        response = self.client.put(url, newtestresult, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for k, v in newtestresult.items():
            self.assertNotEqual(v, response.data[k], f"{k} was modified")

    def test_adding_results_turns_result_object_finalized(self):
        # Arrange
        modelresult = self.mock_result(
            self.bmk_id, self.model_id, self.dataset_id, results={}
        )
        self.set_credentials(self.data_owner)
        result = self.create_result(modelresult).data
        self.set_credentials(self.actor)

        newtestresult = {
            "results": {"res": 1},
        }
        url = self.url.format(result["id"])

        # Act
        response = self.client.put(url, newtestresult, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(True, response.data["finalized"], "It's still not finalized")

    def test_put_is_not_allowed_with_finalized_result_objects(self):
        # Arrange
        modelresult = self.mock_result(
            self.bmk_id, self.model_id, self.dataset_id, results={"r": 1}
        )
        self.set_credentials(self.data_owner)
        result = self.create_result(modelresult).data
        newtestresult = {
            "results": {"res": 1},
        }
        url = self.url.format(result["id"])
        response = self.client.put(url, newtestresult, format="json")

        self.set_credentials(self.actor)

        newtestresult = {
            "results": {"newr": 3},
            "model_report": {"rep": "t"},
            "evaluation_report": {"rep": "t"},
            "partial": False,
        }
        url = self.url.format(result["id"])

        for key, val in newtestresult.items():
            # Act
            response = self.client.put(url, {key: val}, format="json")

            # Assert
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@parameterized_class(
    [
        {"actor": "other_user"},
    ],
)
class ConfidentialResultPutTest(ResultsTest):
    """Test module for PUT /results/<pk> of a confidential execution

    Ownership follows whoever ran it, not whose data it ran on, so reporting
    what came back is theirs to do.
    """

    def setUp(self):
        super(ConfidentialResultPutTest, self).setUp()
        self.generic_setup()
        benchmark, dataset, model = self.confidential_setup()

        self.set_credentials(self.actor)
        result = self.create_result(
            self.mock_result(benchmark["id"], model["id"], dataset["id"])
        ).data
        self.url = self.url.format(result["id"])

    def test_the_operator_may_report_what_they_collected(self):
        # Arrange
        new_results = {"auc": 0.9}

        # Act
        response = self.client.put(self.url, {"results": new_results}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], new_results)


class ConfidentialCollectorTest(ResultsTest):
    """Test module for a confidential execution whose collector is not its
    operator

    The results were encrypted for the collector's key and written to their
    storage, so reporting them is theirs to do -- and the operator, who cannot
    open them, must not be the only one who can.
    """

    def setUp(self):
        super(ConfidentialCollectorTest, self).setUp()
        self.generic_setup()
        self.cc = self.confidential_setup()

        self.data_owner_id = self.__user_id(self.data_owner)
        self.model_owner_id = self.__user_id(self.model_owner)
        self.bmk_owner_id = self.__user_id(self.bmk_owner)

        # other_user operates; the data owner collects
        self.set_credentials(self.other_user)
        self.url_template = self.url
        result = self.__create_confidential_result()
        self.url = self.url.format(result["id"])
        self.client.put(
            self.url, {"result_collector": self.data_owner_id}, format="json"
        )
        self.set_credentials(None)

    def __user_id(self, username):
        self.set_credentials(username)
        return self.client.get(self.api_prefix + "/me/").data["id"]

    def __create_confidential_result(self):
        benchmark, dataset, model = self.cc
        return self.create_result(
            self.mock_result(benchmark["id"], model["id"], dataset["id"])
        ).data

    def test_the_collector_may_report_what_only_they_could_open(self):
        # Arrange
        self.set_credentials(self.data_owner)

        # Act
        response = self.client.put(self.url, {"results": {"auc": 0.9}}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], {"auc": 0.9})

    def test_the_collector_may_read_an_execution_they_did_not_create(self):
        # Arrange
        self.set_credentials(self.data_owner)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_collector_cannot_be_pointed_at_somebody_else(self):
        """Write-once: whoever it was recorded as is who can open the results"""
        # Arrange
        self.set_credentials(self.other_user)

        # Act
        response = self.client.put(
            self.url, {"result_collector": self.model_owner_id}, format="json"
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_an_asset_owner_may_be_named_as_the_collector(self):
        """The operator states this and the server would otherwise take their
        word for it. Only the two asset owners have a key published to the
        other parties, so nobody else could have had results encrypted for
        them -- and naming them would hand a stranger read and write here"""
        # Arrange -- a second execution, with nobody recorded on it yet
        self.set_credentials(self.other_user)
        result = self.__create_confidential_result()

        # Act
        response = self.client.put(
            self.url_template.format(result["id"]),
            {"result_collector": self.bmk_owner_id},
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ConfidentialCollectorPermissionTest(ResultsTest):
    """Test module for permissions of /results/{pk} once a collector is named

    Non-permitted actions:
        PUT: for all users except the operator, the collector and admin
        GET: for unauthenticated users
    """

    def setUp(self):
        super(ConfidentialCollectorPermissionTest, self).setUp()
        self.generic_setup()
        benchmark, dataset, model = self.confidential_setup()

        self.set_credentials(self.data_owner)
        data_owner_id = self.client.get(self.api_prefix + "/me/").data["id"]

        self.set_credentials(self.other_user)
        result = self.create_result(
            self.mock_result(benchmark["id"], model["id"], dataset["id"])
        ).data
        self.url = self.url.format(result["id"])
        self.client.put(self.url, {"result_collector": data_owner_id}, format="json")
        self.set_credentials(None)

    @parameterized.expand(
        [
            ("model_owner", status.HTTP_403_FORBIDDEN),
            ("bmk_owner", status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]
    )
    def test_put_permissions(self, user, expected_status):
        """Naming a collector grants that one party something, and nobody
        else anything"""
        # Arrange
        self.set_credentials(user)

        # Act
        response = self.client.put(self.url, {"results": {"r": 2}}, format="json")

        # Assert
        self.assertEqual(response.status_code, expected_status)


class ConfidentialResultPutPermissionTest(ResultsTest):
    """Test module for permissions of PUT /results/{pk} of a confidential
    execution somebody other than the dataset owner ran

    Non-permitted actions:
        PUT: for all users except the execution owner and admin -- the dataset
            owner included, since the execution is not theirs
    """

    def setUp(self):
        super(ConfidentialResultPutPermissionTest, self).setUp()
        self.generic_setup()
        benchmark, dataset, model = self.confidential_setup()

        self.set_credentials(self.other_user)
        result = self.create_result(
            self.mock_result(benchmark["id"], model["id"], dataset["id"])
        ).data
        self.url = self.url.format(result["id"])
        self.set_credentials(None)

    @parameterized.expand(
        [
            ("data_owner", status.HTTP_403_FORBIDDEN),
            ("model_owner", status.HTTP_403_FORBIDDEN),
            ("bmk_owner", status.HTTP_403_FORBIDDEN),
            ("committee_user", status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]
    )
    def test_put_permissions(self, user, expected_status):
        # Arrange
        self.set_credentials(user)

        # Act
        response = self.client.put(self.url, {"results": {"r": 2}}, format="json")

        # Assert
        self.assertEqual(response.status_code, expected_status)


@parameterized_class(
    [
        {"actor": "api_admin"},
    ]
)
class ResultDeleteTest(ResultsTest):
    """Test module for DELETE /results/<pk>"""

    def setUp(self):
        super(ResultDeleteTest, self).setUp()
        self.generic_setup()
        self.set_credentials(self.actor)

    def test_deletion_works_as_expected(self):
        # Arrange
        result = self.mock_result(
            self.bmk_id, self.model_id, self.dataset_id, results={"r": 1}
        )
        self.set_credentials(self.data_owner)
        result = self.create_result(result).data
        self.set_credentials(self.actor)

        url = self.url.format(result["id"])

        # Act
        response = self.client.delete(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(url)

        # TODO: fixme after refactoring permissions. should just like this:
        # self.assertEqual(response.status_code, status.HTTP_404_FORBIDDEN)
        if self.actor == self.data_owner:
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        else:
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PermissionTest(ResultsTest):
    """Test module for permissions of /results/{pk} endpoint
    Non-permitted actions:
        GET: for all users except bmk_owner, committee members, the execution
            owner, and admin
        DELETE: for all users except admin (committee members included)
        PUT: for all users except admin and the execution owner (committee
            members included)

    The execution here is one the data owner ran on their own dataset, which
    is every execution but a confidential end to end one.
    """

    def setUp(self):
        super(PermissionTest, self).setUp()
        self.generic_setup()
        result = self.mock_result(
            self.bmk_id, self.model_id, self.dataset_id, results={"r": 1}
        )
        self.set_credentials(self.data_owner)
        result = self.create_result(result).data
        self.url = self.url.format(result["id"])

        self.result = result
        self.set_credentials(None)

    @parameterized.expand(
        [
            ("model_owner", status.HTTP_403_FORBIDDEN),
            ("bmk_prep_mlcube_owner", status.HTTP_403_FORBIDDEN),
            ("ref_model_owner", status.HTTP_403_FORBIDDEN),
            ("eval_mlcube_owner", status.HTTP_403_FORBIDDEN),
            ("other_user", status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]
    )
    def test_get_permissions(self, user, expected_status):
        # Arrange
        self.set_credentials(user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, expected_status)

    @parameterized.expand(
        [
            ("bmk_owner", status.HTTP_403_FORBIDDEN),
            ("committee_user", status.HTTP_403_FORBIDDEN),
            ("model_owner", status.HTTP_403_FORBIDDEN),
            ("bmk_prep_mlcube_owner", status.HTTP_403_FORBIDDEN),
            ("ref_model_owner", status.HTTP_403_FORBIDDEN),
            ("eval_mlcube_owner", status.HTTP_403_FORBIDDEN),
            ("other_user", status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]
    )
    def test_put_permissions(self, user, expected_status):
        # Arrange

        # create new assets to edit with
        prep, refmodel, _, newbenchmark = self.shortcut_create_benchmark(
            self.bmk_prep_mlcube_owner,
            self.ref_model_owner,
            self.eval_mlcube_owner,
            self.bmk_owner,
            prep_mlcube_kwargs={
                "name": "newprep",
                "container_config": {"newprephash": "newprephash"},
            },
            ref_model_kwargs={
                "name": "newref",
                "container_config": {"newrefhash": "newrefhash"},
            },
            eval_mlcube_kwargs={
                "name": "neweval",
                "container_config": {"newevalhash": "newevalhash"},
            },
            name="newbmk",
        )
        self.set_credentials(self.data_owner)
        newdataset = self.mock_dataset(prep["id"], generated_uid="newgen")
        newdataset = self.create_dataset(newdataset).data

        newtestresult = {
            "name": "new",
            "owner": 55,
            "benchmark": newbenchmark["id"],
            "model": refmodel["id"],
            "dataset": newdataset["id"],
            "results": {"new": "t"},
            "metadata": {"new": "t"},
            "user_metadata": {"new": "t"},
            "approval_status": "APPROVED",
            "is_valid": False,
            "approved_at": "time",
            "created_at": "time",
            "modified_at": "time",
            "finalized_at": "time",
            "finalized": True,
            "model_report": {"new": "t"},
            "evaluation_report": {"new": "t"},
        }

        self.set_credentials(user)

        for key in newtestresult:
            # Act
            response = self.client.put(
                self.url, {key: newtestresult[key]}, format="json"
            )

            # Assert
            self.assertEqual(
                response.status_code, expected_status, f"{key} was modified"
            )

    @parameterized.expand(
        [
            ("bmk_owner", status.HTTP_403_FORBIDDEN),
            ("committee_user", status.HTTP_403_FORBIDDEN),
            ("model_owner", status.HTTP_403_FORBIDDEN),
            ("data_owner", status.HTTP_403_FORBIDDEN),
            ("bmk_prep_mlcube_owner", status.HTTP_403_FORBIDDEN),
            ("ref_model_owner", status.HTTP_403_FORBIDDEN),
            ("eval_mlcube_owner", status.HTTP_403_FORBIDDEN),
            ("other_user", status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]
    )
    def test_delete_permissions(self, user, expected_status):
        # Arrange
        self.set_credentials(user)

        # Act
        response = self.client.delete(self.url)

        # Assert
        self.assertEqual(response.status_code, expected_status)
