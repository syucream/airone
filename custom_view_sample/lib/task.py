import enum


@enum.unique
class JobOperationCustom(enum.IntEnum):
    # The value from ones place to tems place describes same meaning of JobOperation.
    # (e.g. 1 = CREATE_ENTRY, 2 = EDIT_ENTRY, ...)
    #
    # The hundreds place values are set to identify each operations in CustomView.
    CREATE_PORT_ENTRY = 101
    REMOVE_PORT_ENTRY = 202
    UPDATE_PORTS_NAME = 203
    UPDATE_RACK_ENTRY = 302
    UPDATE_NW_CIDR_TREE = 401
    SYNC_GSPREAD = 501


CUSTOM_HIDDEN_OPERATIONS: list[JobOperationCustom] = [JobOperationCustom.UPDATE_NW_CIDR_TREE]
CUSTOM_CANCELABLE_OPERATIONS: list[JobOperationCustom] = [
    JobOperationCustom.SYNC_GSPREAD,
]
CUSTOM_PARALLELIZABLE_OPERATIONS: list[JobOperationCustom] = []
CUSTOM_DOWNLOADABLE_OPERATIONS: list[JobOperationCustom] = []
CUSTOM_TASKS: dict[JobOperationCustom, str] = {
    JobOperationCustom.CREATE_PORT_ENTRY: "create_entry_attrs_port",
    JobOperationCustom.REMOVE_PORT_ENTRY: "remove_facing_related_link",
    JobOperationCustom.SYNC_GSPREAD: "sync_google_spreadsheet",
    JobOperationCustom.UPDATE_PORTS_NAME: "update_ports_name",
    JobOperationCustom.UPDATE_RACK_ENTRY: "update_facing_rack",
    JobOperationCustom.UPDATE_NW_CIDR_TREE: "update_nw_cidr_tree",
}
