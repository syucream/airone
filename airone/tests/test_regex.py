import re
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from airone.lib.regex import (
    MAX_MATCH_LENGTH,
    MAX_PATTERN_COMPLEXITY,
    MAX_PATTERN_LENGTH,
    RegexBudget,
    RegexValidationError,
)


class RegexBudgetTest(unittest.TestCase):
    def test_preserves_python_pattern_features(self):
        cases = [
            (r"^vm[0-9]+$|^template-.*", "vm123", True),
            (r"^vm[0-9]+$|^template-.*", "vm123-extra", False),
            (r"(?P<word>[a-z]+)-(?P=word)$", "host-host", True),
            (r"(?=host)host(?<=host)(?!-dev)", "host-prod", True),
            (r"(?i:host)-[0-9]{2,4}", "HOST-12-extra", True),
            (r"(a)?(?(1)b|c)", "ab", True),
            (r"(?>a{1,2})a*+", "aaa", True),
            (r"(?:a{2}){3}", "aaaaaa", True),
            (r"\{1000000000\}", "{1000000000}", True),
            (r"[a{1000000000}]+", "a{100}", True),
            (r"^\w+$", "日本語_123", True),
            (r".*suffix$", "prefix\nsuffix", False),
            (r".*(?s:suffix.*)", "prefixsuffix\n", True),
            (r".*^suffix", "prefixsuffix", False),
            ("", "anything", True),
        ]
        for pattern, value, expected in cases:
            with self.subTest(pattern=pattern, value=value):
                budget = RegexBudget()
                self.assertEqual(budget.match(budget.compile(pattern), value), expected)
                self.assertEqual(bool(re.match(pattern, value)), expected)

    def test_documents_unicode_engine_differences(self):
        # VERSION0 retains Python syntax but uses regex's Unicode classification.
        for pattern, value, old_result, new_result in [
            (r"^\w+$", "a\u0301", False, True),
            (r"^\w+$", "a\u200c", False, True),
            (r"(?i)^[a-z]+$", "\u0131", True, False),
        ]:
            with self.subTest(pattern=pattern, value=value):
                budget = RegexBudget()
                self.assertEqual(bool(re.match(pattern, value)), old_result)
                self.assertEqual(budget.match(budget.compile(pattern), value), new_result)

    def test_rejects_invalid_and_extended_syntax(self):
        for pattern in ("[", "(a", "a{3,2}", "(?R)", "(?V1)a", "(?<=a+)b"):
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(RegexValidationError, "Invalid regular expression"):
                    RegexBudget().compile(pattern)

    def test_compilation_limits_before_calling_unbounded_compiler(self):
        # The subprocess also makes a regression in the compiler guard safe to run.
        script = """
from airone.lib.regex import RegexBudget, RegexValidationError
patterns = [
    'a{1000000000}', '(a{1000}){1000}', '(?=a{1000000000})a',
    '(?!a{1000000000})a', '(?>a{1000000000})',
    '(a)?(?(1)b{1000000000}|c)', 'a|b{1000000000}',
    'a{1000000000}?', 'a{1000000000}+',
]
for pattern in patterns:
    try:
        RegexBudget().compile(pattern)
    except RegexValidationError as exc:
        assert 'too complex' in str(exc), (pattern, str(exc))
    else:
        raise AssertionError(pattern)
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=10
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_oversized_pattern_and_input(self):
        with self.assertRaisesRegex(RegexValidationError, "exceeds"):
            RegexBudget().compile("a" * (MAX_PATTERN_LENGTH + 1))
        budget = RegexBudget()
        with self.assertRaisesRegex(RegexValidationError, "input exceeds"):
            budget.match(budget.compile("a"), "a" * (MAX_MATCH_LENGTH + 1))

    def test_accepts_values_at_resource_limits(self):
        budget = RegexBudget()
        # Keep matches trivial: size limits are independent from the CPU budget.
        pattern = "(?#" + "x" * (MAX_PATTERN_LENGTH - 5) + ")a"
        self.assertTrue(budget.match(budget.compile(pattern), "a"))
        budget = RegexBudget()
        self.assertTrue(budget.match(budget.compile("a"), "a" * MAX_MATCH_LENGTH))
        RegexBudget().compile(f"a{{{MAX_PATTERN_COMPLEXITY}}}")
        with self.assertRaisesRegex(RegexValidationError, "too complex"):
            RegexBudget().compile(f"a{{{MAX_PATTERN_COMPLEXITY + 1}}}")

    def test_unknown_python_parser_operation_fails_closed(self):
        with patch("airone.lib.regex._parser") as parser:
            parser.parse.return_value = [("NEW_OPERATION", None)]
            with self.assertRaisesRegex(RegexValidationError, "Unsupported"):
                RegexBudget().compile("unique-pattern-for-parser-test")

    def test_matches_share_one_budget(self):
        pattern = Mock()
        pattern.match.return_value = None
        budget = RegexBudget()
        with patch("airone.lib.regex.thread_time", side_effect=[0, 0.06, 1, 1.06]):
            self.assertFalse(budget.match(pattern, "first"))
            with self.assertRaisesRegex(RegexValidationError, "timed out"):
                budget.match(pattern, "second")
        self.assertAlmostEqual(pattern.match.call_args.kwargs["timeout"], 0.04)
        with self.assertRaisesRegex(RegexValidationError, "timed out"):
            budget.match(pattern, "third")
        self.assertEqual(pattern.match.call_count, 2)
