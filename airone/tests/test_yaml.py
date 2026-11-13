import io
import json
from unittest.mock import Mock, patch

import yaml
from django.test import SimpleTestCase
from rest_framework.exceptions import ParseError

from airone.lib.drf import EnvelopeYAMLParser, YAMLParser
from airone.lib.yaml import (
    MAX_YAML_BYTES,
    MAX_YAML_DEPTH,
    MAX_YAML_NUMERIC_CHARS,
    safe_load_yaml,
)


def alias_tree(depth: int = 18, *, merge: bool = False) -> str:
    """Build a compact graph whose expanded size grows exponentially."""
    rows = ["a0: &a0 {value: leaf}" if merge else "a0: &a0 [leaf]"]
    for index in range(1, depth):
        aliases = f"[*a{index - 1}, *a{index - 1}]"
        value = "{<<: " + aliases + "}" if merge else aliases
        rows.append(f"a{index}: &a{index} {value}")
    return "\n".join(rows)


class BoundedYAMLTest(SimpleTestCase):
    def test_normal_yaml_and_shared_references_preserve_safe_loader_behavior(self):
        source = (
            "defaults: &defaults {name: 日本語, active: true, ids: [1, 2]}\n"
            "copy: *defaults\n"
            "merged: {<<: *defaults, name: override}\n"
            "empty: null\n"
        )

        loaded = safe_load_yaml(source)

        self.assertEqual(loaded, yaml.safe_load(source))
        self.assertIs(loaded["defaults"], loaded["copy"])
        self.assertEqual(json.loads(json.dumps(loaded)), loaded)

    def test_empty_yaml_preserves_safe_loader_behavior(self):
        self.assertIsNone(safe_load_yaml(""))

    def test_invalid_scalars_and_encoding_raise_yaml_errors(self):
        for source in ("date: 2026-99-99", "number: " + "1" * 4400, b"\xff"):
            with self.subTest(source=source[:30]), self.assertRaises(yaml.YAMLError):
                safe_load_yaml(source)

    def test_alias_expansion_is_rejected_before_any_construction(self):
        for merge in (False, True):
            with (
                self.subTest(merge=merge),
                patch.object(yaml.SafeLoader, "construct_document") as build,
            ):
                with self.assertRaisesRegex(yaml.YAMLError, "expanded node limit"):
                    safe_load_yaml(alias_tree(merge=merge))
                build.assert_not_called()

    def test_recursive_aliases_are_rejected_before_any_construction(self):
        for source in ("&a [*a]", "&a {self: *a}", "&a {nested: [*a]}"):
            with (
                self.subTest(source=source),
                patch.object(yaml.SafeLoader, "construct_document") as build,
            ):
                with self.assertRaisesRegex(yaml.YAMLError, "Recursive YAML"):
                    safe_load_yaml(source)
                build.assert_not_called()

    def test_many_references_to_large_scalar_are_bounded(self):
        source = "a: &a " + "x" * 100 + "\nb: [*a, *a, *a]"
        with patch("airone.lib.yaml.MAX_YAML_BYTES", 300):
            with self.assertRaisesRegex(yaml.YAMLError, "expanded scalar size"):
                safe_load_yaml(source)

    def test_sexagesimal_numbers_are_rejected_before_scalar_construction(self):
        for source in ("value: 1" + ":00" * MAX_YAML_NUMERIC_CHARS, "!!float " + "1" * 4400):
            with (
                self.subTest(source=source[:30]),
                patch.object(yaml.SafeLoader, "construct_document") as build,
            ):
                with self.assertRaisesRegex(yaml.YAMLError, "numeric scalar size"):
                    safe_load_yaml(source)
                build.assert_not_called()

    def test_numeric_scalar_size_boundary_preserves_normal_numbers(self):
        for source in ("1234567890", "0.12345678", "1:00:00:00"):
            with self.subTest(source=source):
                with patch("airone.lib.yaml.MAX_YAML_NUMERIC_CHARS", 10):
                    self.assertEqual(safe_load_yaml(source), yaml.safe_load(source))
                with patch("airone.lib.yaml.MAX_YAML_NUMERIC_CHARS", 9):
                    with self.assertRaisesRegex(yaml.YAMLError, "numeric scalar size"):
                        safe_load_yaml(source)

    def test_expanded_scalar_size_boundary(self):
        source = "a: &a " + "x" * 100 + "\nb: [*a]"
        with patch("airone.lib.yaml.MAX_YAML_BYTES", 202):
            self.assertEqual(safe_load_yaml(source)["b"], ["x" * 100])
        with patch("airone.lib.yaml.MAX_YAML_BYTES", 201):
            with self.assertRaisesRegex(yaml.YAMLError, "expanded scalar size"):
                safe_load_yaml(source)

    def test_node_count_boundary_includes_alias_targets(self):
        source = "[&a x, *a]"
        with patch("airone.lib.yaml.MAX_YAML_NODES", 3):
            self.assertEqual(safe_load_yaml(source), ["x", "x"])
        with patch("airone.lib.yaml.MAX_YAML_NODES", 2):
            with self.assertRaisesRegex(yaml.YAMLError, "node limit"):
                safe_load_yaml(source)

    def test_expanded_node_count_boundary(self):
        source = "[&a [x], *a]"
        with patch("airone.lib.yaml.MAX_YAML_NODES", 5):
            self.assertEqual(safe_load_yaml(source), [["x"], ["x"]])
        with patch("airone.lib.yaml.MAX_YAML_NODES", 4):
            with self.assertRaisesRegex(yaml.YAMLError, "expanded node limit"):
                safe_load_yaml(source)

    def test_plain_nesting_is_bounded_during_composition(self):
        source = "[" * MAX_YAML_DEPTH + "x" + "]" * MAX_YAML_DEPTH
        with patch.object(yaml.SafeLoader, "construct_document") as build:
            with self.assertRaisesRegex(yaml.YAMLError, "nesting depth"):
                safe_load_yaml(source)
            build.assert_not_called()

    def test_plain_depth_boundary(self):
        with patch("airone.lib.yaml.MAX_YAML_DEPTH", 3):
            self.assertEqual(safe_load_yaml("[[x]]"), [["x"]])
            with self.assertRaisesRegex(yaml.YAMLError, "nesting depth"):
                safe_load_yaml("[[[x]]]")

    def test_alias_target_depth_counts_toward_expanded_depth(self):
        with patch("airone.lib.yaml.MAX_YAML_DEPTH", 4):
            self.assertEqual(safe_load_yaml("a: &a [[x]]\nb: *a")["b"], [["x"]])
            with self.assertRaisesRegex(yaml.YAMLError, "expanded nesting depth"):
                safe_load_yaml("a: &a [[x]]\nb: [*a]")

    def test_source_size_boundary(self):
        for source in ("abcd", b"abcd", io.BytesIO(b"abcd")):
            with self.subTest(source=source), patch("airone.lib.yaml.MAX_YAML_BYTES", 4):
                self.assertEqual(safe_load_yaml(source), "abcd")
        for source in ("abcde", b"abcde", io.BytesIO(b"abcde")):
            with self.subTest(source=source), patch("airone.lib.yaml.MAX_YAML_BYTES", 4):
                with self.assertRaisesRegex(yaml.YAMLError, "input size"):
                    safe_load_yaml(source)

    def test_unicode_input_size_is_measured_in_bytes(self):
        with patch("airone.lib.yaml.MAX_YAML_BYTES", 5):
            with self.assertRaisesRegex(yaml.YAMLError, "input size"):
                safe_load_yaml("日本")

    def test_stream_read_is_bounded_before_parser_work(self):
        stream = Mock()
        stream.read.return_value = b"x" * (MAX_YAML_BYTES + 1)
        with patch("airone.lib.yaml._BoundedSafeLoader") as loader:
            with self.assertRaisesRegex(yaml.YAMLError, "input size"):
                safe_load_yaml(stream)
            stream.read.assert_called_once_with(MAX_YAML_BYTES + 1)
            loader.assert_not_called()


class YAMLParserTest(SimpleTestCase):
    def test_all_yaml_failures_become_parse_errors(self):
        sources = (
            "key: [",
            "key: @",
            "*missing",
            "[&a one, &a two]",
            "!!python/name:os.system",
            "&a [*a]",
            alias_tree(),
            "[" * MAX_YAML_DEPTH + "x" + "]" * MAX_YAML_DEPTH,
        )
        for parser in (YAMLParser(), EnvelopeYAMLParser()):
            for source in sources:
                with self.subTest(parser=type(parser).__name__, source=source[:30]):
                    with self.assertRaises(ParseError):
                        parser.parse(io.BytesIO(source.encode()))

    def test_invalid_encoding_becomes_parse_error(self):
        with self.assertRaises(ParseError):
            YAMLParser().parse(io.BytesIO(b"\xff"))

    def test_declared_encoding_is_preserved(self):
        self.assertEqual(
            YAMLParser().parse(
                io.BytesIO("name: 日本".encode("shift-jis")),
                parser_context={"encoding": "shift-jis"},
            ),
            {"name": "日本"},
        )

    def test_envelope_unwraps_normal_aliased_data(self):
        source = b"import_type: role\ndata: [&a {name: role}, *a]"
        self.assertEqual(
            EnvelopeYAMLParser().parse(io.BytesIO(source)), [{"name": "role"}, {"name": "role"}]
        )

    def test_unknown_envelope_fields_are_checked_before_unwrapping(self):
        source = "import_type: role\ndata: []\nignored:\n  " + alias_tree().replace("\n", "\n  ")
        with self.assertRaises(ParseError):
            EnvelopeYAMLParser().parse(io.BytesIO(source.encode()))
