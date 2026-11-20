from __future__ import annotations

from typing import NotRequired, TypedDict

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from group.models import Group


class GroupTreeNode(TypedDict):
    id: int
    name: str
    display_name: NotRequired[str]
    children: NotRequired[list[GroupTreeNode]]


class GroupTreeSerializer(serializers.Serializer[GroupTreeNode]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    children = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_children(self, obj: GroupTreeNode) -> list[GroupTreeNode]:
        return obj.get("children", [])


class GroupTreeAPI(APIView):
    serializer_class = GroupTreeSerializer

    def get(self, request: Request, format: str | None = None) -> Response:
        def _make_hierarchical_group(groups: QuerySet[Group]) -> list[GroupTreeNode]:
            return [
                {
                    "id": g.id,
                    "name": g.name,
                    "display_name": g.display_name,
                    "children": _make_hierarchical_group(g.subordinates.filter(is_active=True)),
                }
                for g in groups
            ]

        return Response(
            _make_hierarchical_group(
                Group.objects.filter(parent_group__isnull=True, is_active=True)
            )
        )
