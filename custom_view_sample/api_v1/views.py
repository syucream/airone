import ipaddress
from copy import deepcopy

from rest_framework import status
from rest_framework.response import Response

from airone.lib.acl import ACLType
from api_v1.serializers import PostEntrySerializer
from api_v1.views import EntryAPI
from custom_view.lib import constant
from custom_view.lib.cidr import create_nw_cidr_tree_job
from custom_view.lib.entry_has_equipped_rack_or_rackspaces import (
    update_equipped_rackinfo_in_appliance,
    update_rackspace_in_rack,
)
from custom_view.lib.entry_has_ipaddresses import update_ipaddress_info
from custom_view.lib.entry_has_link_or_related_link import (
    cancel_status_reserved,
    create_recv_data,
    is_clear_configured_link,
    is_link_updatable,
    may_unset_link_at_facing_port,
    may_unset_related_link_at_facing_port,
    set_facing_ports_link,
    set_facing_ports_related_link,
)
from custom_view.lib.procedure import may_set_blank_due_to_status_change
from custom_view.lib.settings import ADAPTED_ENTITY
from custom_view.lib.util_ipaddress import update_network_attr
from custom_view.views.LBVirtualServer import _update_category_attr
from custom_view.views.Transceiver import _updata_status, _validate_rack_or_container
from entity.models import Entity
from entry.models import Entry

EQUIPPED_RACKNAME = ADAPTED_ENTITY["entry_in_rack"].get_attr("equipped_rack")["name"]
UNIT_COUNT_NAME = ADAPTED_ENTITY["rack"].get_attr("capacity")["name"]


class CustomEntryAPI(EntryAPI):
    def post(self, request, format=None):
        # Use deepcopy because it only verification without conversion
        raw_request_data = deepcopy(request.data)
        PostEntrySerializer(data=raw_request_data, context={"_user": request.user}).is_valid(
            raise_exception=True
        )

        # Preprocessing when link or related_link exists
        if not self._clear_link_and_related_link_of_opposite_port(request):
            return Response(
                {"result": "The input content of the opposite port is invalid [link]"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # For (IPv6 Address) check entry name
        if request.data.get("entity", "") == "(IPv6 Address)":
            entry_name = request.data.get("name")

            # Use IPv6 compression format.
            # (e.g. 2001:0db8:85a3:0000:0000:8a2e:0370:1234 -> 2001:db8:85a3::8a2e:370:1234)
            # A single IPv6 address can be defined in different ways.
            # Unify to compression format so that IPv6 does not duplicated.
            request.data["name"] = str(ipaddress.IPv6Address(entry_name))

        # For Transceiver check rack xor container
        if request.data.get("entity", "") == "Transceiver":
            entry = Entry.objects.filter(
                name=request.data.get("name"),
                schema__name="Transceiver",
                is_active=True,
            ).first()

            err = _validate_rack_or_container(entry, request.data)
            if err:
                return Response(
                    {"result": "Only one rack or container must be specified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ラックエントリより大きい値だったらエラーにする
        if (
            EQUIPPED_RACKNAME in request.data.get("attrs", {})
            and len(request.data["attrs"][EQUIPPED_RACKNAME]) > 0
            and isinstance(request.data["attrs"][EQUIPPED_RACKNAME][0], dict)
        ):
            req_param = request.data["attrs"][EQUIPPED_RACKNAME][0]
            rack_no = req_param["name"]
            rack_entry = Entry.objects.get(
                name=req_param["id"],
                schema__name=ADAPTED_ENTITY["rack"].name,
                is_active=True,
            )
            rack_attrv = rack_entry.get_attrv(UNIT_COUNT_NAME)
            if not rack_attrv:
                return Response(
                    {"result": constant.ERROR_MSG["entry_in_rack"]["failed_to_get_unit_num"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not rack_no.isdigit() or int(rack_no) > int(rack_attrv.value):
                return Response(
                    {"result": constant.ERROR_MSG["entry_in_rack"]["invalid_unit_number"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        resp = super(CustomEntryAPI, self).post(request)

        if resp.status_code == status.HTTP_200_OK:
            if EQUIPPED_RACKNAME in request.data["attrs"]:
                user, entry = self._get_user_and_entry(request, resp)
                if self._check_permission(user, entry, EQUIPPED_RACKNAME):
                    update_rackspace_in_rack(user, entry)

            if "RackSpace" in request.data["attrs"]:
                user, entry = self._get_user_and_entry(request, resp)
                if self._check_permission(user, entry, "RackSpace"):
                    update_equipped_rackinfo_in_appliance(user, entry)

            if "a-01 | ステータス" in request.data["attrs"]:
                user, entry = self._get_user_and_entry(request, resp)
                if self._check_permission(user, entry, "a-01 | ステータス"):
                    may_set_blank_due_to_status_change(user, entry)
                    update_rackspace_in_rack(user, entry)

            if "IP Addresses" in request.data["attrs"]:
                user, entry = self._get_user_and_entry(request, resp)
                if self._check_permission(user, entry, "IP Addresses"):
                    update_ipaddress_info(user, entry)

            # Post-processing when there is link or related_link
            self._set_attr_of_the_opposite_port(request, resp)

            if request.data.get("entity", "") in [
                "(Network)",
                "(IPv6 Network)",
                "(VLAN)",
            ]:
                user, entry = self._get_user_and_entry(request, resp)
                create_nw_cidr_tree_job(user, entry)

            # For update network attr
            if request.data.get("entity", "") == "(IPaddress)":
                user, entry = self._get_user_and_entry(request, resp)
                update_network_attr(entry, user, False)
            if request.data.get("entity", "") == "(IPv6 Address)":
                user, entry = self._get_user_and_entry(request, resp)
                update_network_attr(entry, user, True)

            # For update category attr
            if request.data.get("entity", "") == "LBVirtualServer":
                user, entry = self._get_user_and_entry(request, resp)
                _update_category_attr(entry, user)

            # For Transceiver update status
            if request.data.get("entity", "") == "Transceiver":
                user, entry = self._get_user_and_entry(request, resp)
                _updata_status(entry, user)

        return resp

    def _check_permission(self, user, entry, name):
        # If user doesn't have readable permission for target Attribute, it won't be created.
        if not entry.attrs.filter(name=name).exists():
            return False

        attr = entry.attrs.get(name=name)
        if user.has_permission(attr.schema, ACLType.Writable):
            return True

        return False

    def _get_user_and_entry(self, request, resp):
        entry = Entry.objects.get(id=resp.data["result"])
        return request.user, entry

    def _clear_link_and_related_link_of_opposite_port(self, request):
        if "link" in request.data.get("attrs", []) or "related_link" in request.data.get("attrs", []):
            entity = Entity.objects.filter(name=request.data["entity"]).first()
            entry = Entry.objects.filter(name=request.data["name"], schema=entity).first()

            if (
                "link" in request.data["attrs"]
                and entity
                and entry
                and self._check_permission(request.user, entry, "link")
            ):
                # Check if the link update is valid
                facing_port = Entry.objects.filter(
                    name=request.data["attrs"]["link"], schema=entity, is_active=True
                ).first()
                if facing_port and not is_link_updatable(entry, facing_port):
                    return False

                # Get current link attribute value and updated link attribute value
                attr_link = entry.attrs.filter(schema__name="link", is_active=True).first()
                link_currently_set = attr_link.get_latest_value().referral if attr_link else None
                updated_link = facing_port.id if facing_port else None

                # When changing the attribute value of link,
                # cancel the mutual link of the link of the opposite port
                if is_clear_configured_link(link_currently_set, updated_link):
                    entry_facing_port = Entry.objects.filter(id=link_currently_set.id, is_active=True).first()
                    if entry_facing_port:
                        entry_facing_port.complement_attrs(request.user)
                        may_unset_link_at_facing_port(request.user, entry_facing_port)

            if (
                "related_link" in request.data["attrs"]
                and entity
                and entry
                and self._check_permission(request.user, entry, "related_link")
            ):
                # When changing the attribute value of related_link,
                # cancel the mutual link of the related_link of the opposite port
                may_unset_related_link_at_facing_port(
                    request.user,
                    entry,
                    create_recv_data(
                        entity,
                        entry,
                        request.data["attrs"]["related_link"],
                        "related_link",
                    ),
                )

        return True

    def _set_attr_of_the_opposite_port(self, request, resp):
        if ("link" in request.data["attrs"]) or ("related_link" in request.data["attrs"]):
            user, entry = self._get_user_and_entry(request, resp)
            if self._check_permission(user, entry, "status"):
                cancel_status_reserved(user, entry)

            if "link" in request.data["attrs"] and self._check_permission(user, entry, "link"):
                # Set the link attribute value of the opposite port that is mutual linked from link
                set_facing_ports_link(user, entry)

            if "related_link" in request.data["attrs"] and self._check_permission(
                user, entry, "related_link"
            ):
                # Set the related_link attribute value of the opposite port that is mutual linked
                # from related_link
                set_facing_ports_related_link(user, entry)
