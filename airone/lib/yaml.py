"""Load untrusted YAML without allowing aliases to amplify downstream work."""

from typing import IO, Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

# Match the existing 10 MiB dashboard import limit. Expanded limits also apply
# to aliases, including scalar aliases and YAML merge keys, before construction.
MAX_YAML_BYTES = 10 * 1024 * 1024
MAX_YAML_NODES = 100_000
MAX_YAML_DEPTH = 64
MAX_YAML_NUMERIC_CHARS = 4_300


class _YAMLValueError(yaml.YAMLError, ValueError):
    """Normalize scalar/encoding errors while preserving legacy ValueError handling."""


class _BoundedSafeLoader(yaml.SafeLoader):
    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self._depth = 0
        self._composed_nodes = 0
        self._costs: dict[Node, tuple[int, int, int]] = {}

    def compose_node(self, parent: Node | None, index: Any) -> Node:
        self._depth += 1
        self._composed_nodes += 1
        try:
            if self._depth > MAX_YAML_DEPTH:
                raise yaml.YAMLError("YAML nesting depth limit exceeded")
            if self._composed_nodes > MAX_YAML_NODES:
                raise yaml.YAMLError("YAML node limit exceeded")

            is_alias = self.check_event(yaml.events.AliasEvent)  # type: ignore[no-untyped-call]
            node = super().compose_node(parent, index)
            if node is None:
                raise yaml.YAMLError("Expected a YAML node")
            if is_alias:
                # An anchor is registered before its children are composed. A
                # reference to an unfinished node is necessarily a cycle.
                if node not in self._costs:
                    raise yaml.YAMLError("Recursive YAML aliases are not supported")
                return node

            nodes, scalar_bytes, depth = 1, 0, 1
            children: list[Node] = []
            if isinstance(node, ScalarNode):
                # YAML 1.1 sexagesimal integers bypass Python's decimal digit
                # limit and construct a growing big integer once per component.
                if node.tag in ("tag:yaml.org,2002:int", "tag:yaml.org,2002:float"):
                    if len(node.value) > MAX_YAML_NUMERIC_CHARS:
                        raise yaml.YAMLError("YAML numeric scalar size limit exceeded")
                scalar_bytes = len(node.value.encode("utf-8"))
            elif isinstance(node, SequenceNode):
                children = node.value
            elif isinstance(node, MappingNode):
                children = [child for pair in node.value for child in pair]

            # Costs are memoized, but counted at every reference. This measures
            # expansion in linear time without traversing an alias tree or
            # invoking constructors (which themselves expand YAML merge keys).
            for child in children:
                child_nodes, child_bytes, child_depth = self._costs[child]
                nodes += child_nodes
                scalar_bytes += child_bytes
                depth = max(depth, child_depth + 1)
                if nodes > MAX_YAML_NODES:
                    raise yaml.YAMLError("YAML expanded node limit exceeded")
                if scalar_bytes > MAX_YAML_BYTES:
                    raise yaml.YAMLError("YAML expanded scalar size limit exceeded")
                if depth > MAX_YAML_DEPTH:
                    raise yaml.YAMLError("YAML expanded nesting depth limit exceeded")

            self._costs[node] = (nodes, scalar_bytes, depth)
            return node
        finally:
            self._depth -= 1


def safe_load_yaml(stream: str | bytes | IO[bytes], encoding: str = "utf-8") -> Any:
    """Bound the input and expanded graph before constructing Python objects.

    Acyclic aliases and merge keys remain supported within the limits. Scalar
    bytes are counted as UTF-8; JSON escaping can add a constant factor later.
    """
    data = stream if isinstance(stream, (str, bytes)) else stream.read(MAX_YAML_BYTES + 1)
    if len(data) > MAX_YAML_BYTES:
        raise yaml.YAMLError("YAML input size limit exceeded")
    try:
        if isinstance(data, bytes):
            data = data.decode(encoding)
        if len(data.encode("utf-8")) > MAX_YAML_BYTES:
            raise yaml.YAMLError("YAML input size limit exceeded")
        return yaml.load(data, Loader=_BoundedSafeLoader)
    except ValueError as exc:
        raise _YAMLValueError(str(exc)) from exc
