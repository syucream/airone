"""Bound user-controlled regular expressions without dropping Python regex syntax."""

import re
from re import _constants, _parser  # type: ignore[attr-defined]
from time import thread_time

import regex

MAX_PATTERN_LENGTH = 1024
MAX_PATTERN_COMPLEXITY = 10_000
MAX_MATCH_LENGTH = 1_000_000
REGEX_TIMEOUT_SECONDS = 0.1


class RegexValidationError(ValueError):
    """A pattern is invalid or exceeds the regular expression resource budget."""


def _check_complexity(pattern: _parser.SubPattern) -> int:
    """Bound counted-repeat expansion before the regex compiler allocates it.

    Use CPython 3.13+'s parser so escaped braces, character classes, scoped flags,
    branches and assertions are handled exactly like the existing re syntax.
    Unknown parser operations fail closed if a later Python version adds syntax.
    Unbounded repetitions need no compiler expansion; execution has a timeout.
    """
    cost = 0
    for operation, arguments in pattern:
        if operation in (
            _constants.MAX_REPEAT,
            _constants.MIN_REPEAT,
            _constants.POSSESSIVE_REPEAT,
        ):
            minimum, maximum, child = arguments
            repetitions = minimum if maximum == _constants.MAXREPEAT else maximum
            cost += max(1, repetitions) * _check_complexity(child)
        elif operation == _constants.SUBPATTERN:
            cost += _check_complexity(arguments[-1])
        elif operation == _constants.BRANCH:
            cost += sum(_check_complexity(branch) for branch in arguments[1])
        elif operation in (_constants.ASSERT, _constants.ASSERT_NOT):
            cost += _check_complexity(arguments[1])
        elif operation == _constants.ATOMIC_GROUP:
            cost += _check_complexity(arguments)
        elif operation == _constants.GROUPREF_EXISTS:
            cost += _check_complexity(arguments[1])
            if arguments[2] is not None:
                cost += _check_complexity(arguments[2])
        elif operation in (
            _constants.LITERAL,
            _constants.NOT_LITERAL,
            _constants.ANY,
            _constants.IN,
            _constants.AT,
            _constants.CATEGORY,
            _constants.GROUPREF,
            _constants.SUCCESS,
            _constants.FAILURE,
        ):
            cost += 1
        else:
            raise RegexValidationError("Unsupported regular expression operation.")

        if cost > MAX_PATTERN_COMPLEXITY:
            raise RegexValidationError("Regular expression is too complex.")

    return max(cost, 1)


class RegexBudget:
    """Share a CPU budget across compilation and all matches in one operation."""

    def __init__(self) -> None:
        self._remaining = REGEX_TIMEOUT_SECONDS

    def _check_remaining(self) -> None:
        if self._remaining <= 0:
            raise RegexValidationError("Regular expression evaluation timed out.")

    def compile(self, pattern: str) -> regex.Pattern[str]:
        if not isinstance(pattern, str):
            raise RegexValidationError("Regular expression must be a string.")
        if len(pattern) > MAX_PATTERN_LENGTH:
            raise RegexValidationError(
                f"Regular expression exceeds {MAX_PATTERN_LENGTH} characters."
            )

        self._check_remaining()
        started = thread_time()
        try:
            # Also rejects regex-only syntax (recursion, fuzzy matching, etc.).
            re.compile(pattern)
            _check_complexity(_parser.parse(pattern, 0))
            compiled = regex.compile(pattern, flags=regex.VERSION0, cache_pattern=False)
        except (re.error, regex.error, OverflowError, RecursionError) as exc:
            raise RegexValidationError("Invalid regular expression.") from exc
        finally:
            self._remaining -= thread_time() - started

        self._check_remaining()
        return compiled

    def match(self, pattern: regex.Pattern[str], value: str) -> bool:
        if len(value) > MAX_MATCH_LENGTH:
            raise RegexValidationError(
                f"Regular expression input exceeds {MAX_MATCH_LENGTH} characters."
            )

        self._check_remaining()
        started = thread_time()
        try:
            matched = pattern.match(value, timeout=self._remaining) is not None
        except TimeoutError as exc:
            raise RegexValidationError("Regular expression evaluation timed out.") from exc
        finally:
            # Charge only regex work, not time spent waiting for database queries.
            self._remaining -= thread_time() - started

        self._check_remaining()
        return matched
