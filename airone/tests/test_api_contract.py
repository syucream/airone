"""Bounded, reproducible read-only OpenAPI contracts for the generated client."""

import json

import schemathesis
from django.core.handlers.wsgi import WSGIHandler
from django.test import override_settings
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.settings import patched_settings
from hypothesis import given, seed, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase
from rest_framework.authtoken.models import Token
from schemathesis.checks import not_a_server_error
from schemathesis.core.failures import FailureGroup
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_headers_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from airone.lib.types import AttrType
from airone.settings import DRFSpectacularExcludeCustomView
from entity.models import Entity, EntityAttr
from user.models import User

READ_PATHS = (
    "/user/api/v2/me",
    "/entity/api/v2/",
    "/entity/api/v2/{id}/",
)
LABELS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=16)
CONTRACT_SETTINGS = settings(max_examples=12, deadline=None, database=None)
RESPONSE_CHECKS = [
    not_a_server_error,
    status_code_conformance,
    content_type_conformance,
    response_headers_conformance,
    response_schema_conformance,
]


@override_settings(
    ALLOWED_HOSTS=["localhost", "testserver"],
)
class ReadAPIContractTest(TestCase):
    """Use Hypothesis's Django isolation without starting search or queue services."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Match npm run generate:client, including its endpoint exclusion hook.
        with patched_settings(DRFSpectacularExcludeCustomView.SPECTACULAR_SETTINGS):
            raw_schema = SchemaGenerator().get_schema(public=True)
        cls.schema = schemathesis.openapi.from_dict(raw_schema)
        cls.application = WSGIHandler()
        # Index every operation explicitly: removing a path or GET must fail discovery.
        cls.operations = {path: cls.schema[path]["GET"] for path in READ_PATHS}

    def make_data(self, label="example"):
        user = User.objects.create(username="contract-reader", email="reader@example.com")
        token = Token.objects.create(user=user)
        entity = Entity.objects.create(
            name=f"contract-{label}", created_user=user, status=Entity.STATUS_TOP_LEVEL
        )
        attribute = EntityAttr.objects.create(
            name="hostname", type=AttrType.STRING, created_user=user, parent_entity=entity
        )
        return user, entity, attribute, {"Authorization": f"Token {token.key}"}

    def call_and_validate(self, case, headers):
        self.assertEqual(case.method.upper(), "GET")
        self.assertIn(case.path, READ_PATHS)
        response = case.call(app=self.application, headers=headers)
        # Scope this pilot to response contracts; ACL/auth semantics have explicit tests.
        case.validate_response(response, checks=RESPONSE_CHECKS, headers=headers)
        self.assertEqual(response.status_code, 200)
        return response

    @seed(20261114)
    @CONTRACT_SETTINGS
    @given(data=st.data(), label=LABELS)
    def test_current_user(self, data, label):
        user, _, _, headers = self.make_data(label)
        case = data.draw(self.operations[READ_PATHS[0]].as_strategy())
        body = self.call_and_validate(case, headers).json()
        self.assertEqual(body["user_id"], user.id)
        self.assertEqual(body["username"], user.username)

    @seed(20261114)
    @CONTRACT_SETTINGS
    @given(data=st.data(), label=LABELS, limit=st.integers(min_value=1, max_value=5))
    def test_entity_list(self, data, label, limit):
        _, entity, _, headers = self.make_data(label)
        query = {
            "limit": limit,
            "offset": 0,
            "ordering": "name",
            "search": entity.name,
            "is_toplevel": True,
        }
        case = data.draw(self.operations[READ_PATHS[1]].as_strategy(query=query))
        body = self.call_and_validate(case, headers).json()
        self.assertGreater(body["count"], 0)
        self.assertIn(entity.id, [row["id"] for row in body["results"]])

    @seed(20261114)
    @CONTRACT_SETTINGS
    @given(data=st.data(), label=LABELS)
    def test_entity_detail(self, data, label):
        _, entity, attribute, headers = self.make_data(label)
        case = data.draw(
            self.operations[READ_PATHS[2]].as_strategy(
                path_parameters={"id": entity.id}, query={"is_toplevel": True}
            )
        )
        body = self.call_and_validate(case, headers).json()
        self.assertEqual(body["id"], entity.id)
        self.assertIn(attribute.id, [row["id"] for row in body["attrs"]])

    def test_wrong_response_type_is_rejected(self):
        _, _, _, headers = self.make_data()
        case = self.operations[READ_PATHS[0]].Case()
        response = self.call_and_validate(case, headers)
        body = response.json()
        body["user_id"] = "not-an-integer"
        invalid = schemathesis.Response(
            status_code=200,
            headers=response.headers,
            content=json.dumps(body).encode(),
            request=response.request,
            elapsed=response.elapsed,
            verify=False,
        )
        with self.assertRaises(FailureGroup):
            case.validate_response(invalid, checks=RESPONSE_CHECKS, headers=headers)

    def test_server_error_is_rejected(self):
        _, _, _, headers = self.make_data()
        case = self.operations[READ_PATHS[0]].Case()
        response = self.call_and_validate(case, headers)
        invalid = schemathesis.Response(
            status_code=500,
            headers=response.headers,
            content=response.content,
            request=response.request,
            elapsed=response.elapsed,
            verify=False,
        )
        with self.assertRaises(FailureGroup):
            case.validate_response(invalid, checks=RESPONSE_CHECKS, headers=headers)
