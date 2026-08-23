from rest_framework import status

from medperf.tests import MedPerfTest


class UserTest(MedPerfTest):
    def test_me_returns_current_user(self):
        url = self.api_prefix + "/me/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data["username"], user1)
        self.assertEqual(response2.data["username"], user2)


class BenchmarksTest(MedPerfTest):
    def __create_asset(self, user):
        _, _, _, benchmark = self.shortcut_create_benchmark(
            user,
            user,
            user,
            user,
            prep_mlcube_kwargs={
                "name": f"{user}prep",
                "container_config": {f"{user}prep": f"{user}prep"},
            },
            ref_model_kwargs={
                "name": f"{user}ref",
                "container_config": {f"{user}ref": f"{user}ref"},
            },
            eval_mlcube_kwargs={
                "name": f"{user}eval",
                "container_config": {f"{user}eval": f"{user}eval"},
            },
            name=f"{user}name",
        )
        return benchmark

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/benchmarks/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        benchmark1 = self.__create_asset(user1)
        benchmark2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], benchmark1["id"])
        self.assertEqual(resp2[0]["id"], benchmark2["id"])

    def test_endpoint_returns_committee_managed_benchmarks(self):
        url = self.api_prefix + "/me/benchmarks/"

        # setup users
        owner = "owner"
        committee = "committee"
        self.create_user(owner)
        committee_info = self.create_user(committee)

        # owner creates a benchmark and adds the committee member
        _, _, _, benchmark = self.shortcut_create_benchmark(
            owner,
            owner,
            owner,
            owner,
            prep_mlcube_kwargs={
                "name": "committeeprep",
                "container_config": {"committeeprep": "committeeprep"},
            },
            ref_model_kwargs={
                "name": "committeeref",
                "container_config": {"committeeref": "committeeref"},
            },
            eval_mlcube_kwargs={
                "name": "committeeeval",
                "container_config": {"committeeeval": "committeeeval"},
            },
            name="committeename",
            committee_member_emails=[committee_info["email"]],
        )

        # Act
        self.set_credentials(committee)
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        benchmark_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(benchmark["id"], benchmark_ids)


class DatasetsTest(MedPerfTest):
    def __create_asset(self, user):
        self.set_credentials(user)
        prep = self.mock_mlcube(
            name=f"{user}name", container_config={f"{user}hash": f"{user}hash"}
        )
        prep = self.create_mlcube(prep).data
        dataset = self.mock_dataset(prep["id"], generated_uid=f"{user}genid")
        dataset = self.create_dataset(dataset).data
        return dataset

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/datasets/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        dataset1 = self.__create_asset(user1)
        dataset2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], dataset1["id"])
        self.assertEqual(resp2[0]["id"], dataset2["id"])


class MlCubesTest(MedPerfTest):
    def __create_asset(self, user):
        self.set_credentials(user)
        mlcube = self.mock_mlcube(
            name=f"{user}name", container_config={f"{user}hash": f"{user}hash"}
        )
        mlcube = self.create_mlcube(mlcube).data
        return mlcube

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/mlcubes/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        mlcube1 = self.__create_asset(user1)
        mlcube2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], mlcube1["id"])
        self.assertEqual(resp2[0]["id"], mlcube2["id"])


class ResultsTest(MedPerfTest):
    def setUp(self):
        super(ResultsTest, self).setUp()
        bmk_owner = "bmk_owner"
        self.create_user(bmk_owner)
        prep, refmodel, _, benchmark = self.shortcut_create_benchmark(
            bmk_owner, bmk_owner, bmk_owner, bmk_owner
        )
        self.bmk_owner = bmk_owner
        self.benchmark = benchmark
        self.prep = prep
        self.refmodel = refmodel

    def __create_asset(self, user):
        self.set_credentials(user)
        dataset = self.mock_dataset(
            self.prep["id"], generated_uid=f"{user}genid", state="OPERATION"
        )
        dataset = self.create_dataset(dataset).data
        assoc = self.mock_dataset_association(
            self.benchmark["id"], dataset["id"], approval_status="APPROVED"
        )
        self.create_dataset_association(assoc, user, self.bmk_owner)
        result = self.mock_result(
            self.benchmark["id"], self.refmodel["id"], dataset["id"]
        )
        result = self.create_result(result).data
        return result

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/results/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        result1 = self.__create_asset(user1)
        result2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], result1["id"])
        self.assertEqual(resp2[0]["id"], result2["id"])


class BenchmarkDatasetTest(MedPerfTest):
    def __create_asset(self, user):
        prep, _, _, benchmark = self.shortcut_create_benchmark(
            user,
            user,
            user,
            user,
            prep_mlcube_kwargs={
                "name": f"{user}prep",
                "container_config": {f"{user}prep": f"{user}prep"},
            },
            ref_model_kwargs={
                "name": f"{user}ref",
                "container_config": {f"{user}ref": f"{user}ref"},
            },
            eval_mlcube_kwargs={
                "name": f"{user}eval",
                "container_config": {f"{user}eval": f"{user}eval"},
            },
            name=f"{user}name",
        )
        self.set_credentials(user)
        dataset = self.mock_dataset(
            prep["id"], generated_uid=f"{user}genuid", state="OPERATION"
        )
        dataset = self.create_dataset(dataset).data

        assoc = self.mock_dataset_association(benchmark["id"], dataset["id"])
        assoc = self.create_dataset_association(assoc, user, user).data

        return assoc

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/datasets/associations/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        assoc1 = self.__create_asset(user1)
        assoc2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], assoc1["id"])
        self.assertEqual(resp2[0]["id"], assoc2["id"])

    def test_endpoint_returns_committee_managed_associations(self):
        url = self.api_prefix + "/me/datasets/associations/"

        # setup users
        owner = "owner"
        committee = "committee"
        data_owner = "data_owner"
        self.create_user(owner)
        committee_info = self.create_user(committee)
        self.create_user(data_owner)

        # owner creates a benchmark with a committee member
        prep, _, _, benchmark = self.shortcut_create_benchmark(
            owner,
            owner,
            owner,
            owner,
            prep_mlcube_kwargs={
                "name": "committeeprep",
                "container_config": {"committeeprep": "committeeprep"},
            },
            ref_model_kwargs={
                "name": "committeeref",
                "container_config": {"committeeref": "committeeref"},
            },
            eval_mlcube_kwargs={
                "name": "committeeeval",
                "container_config": {"committeeeval": "committeeeval"},
            },
            name="committeename",
            committee_member_emails=[committee_info["email"]],
        )

        # data owner requests an association
        self.set_credentials(data_owner)
        dataset = self.mock_dataset(
            prep["id"], generated_uid="committeegenuid", state="OPERATION"
        )
        dataset = self.create_dataset(dataset).data
        assoc = self.mock_dataset_association(benchmark["id"], dataset["id"])
        assoc = self.create_dataset_association(assoc, data_owner, owner).data

        # Act
        self.set_credentials(committee)
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assoc_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(assoc["id"], assoc_ids)


class BenchmarkModelTest(MedPerfTest):
    def __create_asset(self, user):
        _, _, _, benchmark = self.shortcut_create_benchmark(
            user,
            user,
            user,
            user,
            prep_mlcube_kwargs={
                "name": f"{user}prep",
                "container_config": {f"{user}prep": f"{user}prep"},
            },
            ref_model_kwargs={
                "name": f"{user}ref",
                "container_config": {f"{user}ref": f"{user}ref"},
            },
            eval_mlcube_kwargs={
                "name": f"{user}eval",
                "container_config": {f"{user}eval": f"{user}eval"},
            },
            name=f"{user}name",
        )
        self.set_credentials(user)
        model = self.mock_model(
            name=f"{user}name",
            container_config={f"{user}hash": f"{user}hash"},
            state="OPERATION",
        )
        model = self.create_model(model).data

        assoc = self.mock_model_association(benchmark["id"], model["id"])
        assoc = self.create_model_association(assoc, user, user).data

        return assoc

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/models/associations/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        assoc1 = self.__create_asset(user1)
        assoc2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], assoc1["id"])
        self.assertEqual(resp2[0]["id"], assoc2["id"])

    def test_endpoint_returns_committee_managed_associations(self):
        url = self.api_prefix + "/me/models/associations/"

        # setup users
        owner = "owner"
        committee = "committee"
        model_owner = "model_owner"
        self.create_user(owner)
        committee_info = self.create_user(committee)
        self.create_user(model_owner)

        # owner creates a benchmark with a committee member
        _, _, _, benchmark = self.shortcut_create_benchmark(
            owner,
            owner,
            owner,
            owner,
            prep_mlcube_kwargs={
                "name": "committeeprep",
                "container_config": {"committeeprep": "committeeprep"},
            },
            ref_model_kwargs={
                "name": "committeeref",
                "container_config": {"committeeref": "committeeref"},
            },
            eval_mlcube_kwargs={
                "name": "committeeeval",
                "container_config": {"committeeeval": "committeeeval"},
            },
            name="committeename",
            committee_member_emails=[committee_info["email"]],
        )

        # model owner requests an association
        self.set_credentials(model_owner)
        model = self.mock_model(
            name="committeemodel",
            container_config={"committeemodel": "committeemodel"},
            state="OPERATION",
        )
        model = self.create_model(model).data
        assoc = self.mock_model_association(benchmark["id"], model["id"])
        assoc = self.create_model_association(assoc, model_owner, owner).data

        # Act
        self.set_credentials(committee)
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assoc_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(assoc["id"], assoc_ids)


class CertificatesTest(MedPerfTest):
    def __create_asset(self, user):
        self.set_credentials(user)
        # Create CA
        ca = self.mock_ca(name=f"{user}ca")
        ca = self.create_ca(ca).data
        # Create Certificate
        certificate = self.mock_certificate(ca=ca["id"], name=f"{user}cert")
        certificate = self.create_certificate(certificate).data
        return certificate

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/certificates/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        certificate1 = self.__create_asset(user1)
        certificate2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], certificate1["id"])
        self.assertEqual(resp2[0]["id"], certificate2["id"])


class EncryptedKeysTest(MedPerfTest):
    def __create_asset(self, user):
        self.set_credentials(user)
        # Create CA
        ca = self.mock_ca(name=f"{user}ca")
        ca = self.create_ca(ca).data
        # Create Certificate
        certificate = self.mock_certificate(ca=ca["id"], name=f"{user}cert")
        certificate = self.create_certificate(certificate).data
        # Create Container (mlcube)
        container = self.mock_mlcube(
            name=f"{user}container", container_config={f"{user}hash": "value"}
        )
        container = self.create_mlcube(container).data
        # Create EncryptedKey
        keys_data = [
            {
                "name": f"{user}key",
                "certificate": certificate["id"],
                "container": container["id"],
                "encrypted_key_base64": f"{user}a2V5X2Jhc2U2NA==",
                "is_valid": True,
                "metadata": {},
            }
        ]
        keys = self.create_encrypted_keys(keys_data).data
        return keys[0]

    def test_endpoint_returns_current_user_assets(self):
        url = self.api_prefix + "/me/encrypted_keys/"

        # setup users
        user1 = "user1"
        user2 = "user2"
        self.create_user(user1)
        self.create_user(user2)

        # create an asset for each user
        key1 = self.__create_asset(user1)
        key2 = self.__create_asset(user2)

        # Act
        self.set_credentials(user1)
        response1 = self.client.get(url)
        self.set_credentials(user2)
        response2 = self.client.get(url)

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        resp1 = response1.data["results"]
        resp2 = response2.data["results"]
        self.assertEqual(len(resp1), 1)
        self.assertEqual(len(resp2), 1)
        self.assertEqual(resp1[0]["id"], key1["id"])
        self.assertEqual(resp2[0]["id"], key2["id"])
