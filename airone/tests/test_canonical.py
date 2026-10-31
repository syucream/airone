from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase, override_settings

from airone.lib.canonical import get_canonical_url_parts


class CanonicalUrlPartsTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/")

    def test_canonical_base_url_overrides_request_host(self):
        # The client-controlled Host header must never leak into links.
        self.request.META["HTTP_HOST"] = "attacker.example"
        with override_settings(CANONICAL_BASE_URL="https://pagoda.example.com"):
            parts = get_canonical_url_parts(self.request)

        self.assertEqual(parts["domain"], "pagoda.example.com")
        self.assertEqual(parts["site_name"], "pagoda.example.com")
        self.assertEqual(parts["protocol"], "https")

    def test_canonical_base_url_accepts_schemeless_value(self):
        with override_settings(CANONICAL_BASE_URL="pagoda.example.com"):
            parts = get_canonical_url_parts(self.request)

        self.assertEqual(parts["domain"], "pagoda.example.com")
        self.assertEqual(parts["protocol"], "https")

    def test_canonical_base_url_invalid_value(self):
        for invalid in (
            "pagoda.example.com/path",
            "javascript://x",
            "://",
            "https://user:password@pagoda.example.com",
            "https://pagoda.example.com?a=1",
            "https://pagoda.example.com/#fragment",
        ):
            with self.subTest(invalid=invalid), override_settings(CANONICAL_BASE_URL=invalid):
                with self.assertRaises(ImproperlyConfigured):
                    get_canonical_url_parts(self.request)

    def test_fallback_uses_request_host(self):
        self.request.META["HTTP_HOST"] = "localhost:8000"
        with override_settings(CANONICAL_BASE_URL="", CANONICAL_URL_FALLBACK=True):
            parts = get_canonical_url_parts(self.request)

        self.assertEqual(parts["domain"], "localhost:8000")
        self.assertEqual(parts["protocol"], "http")

    def test_no_fallback_in_production(self):
        self.request.META["HTTP_HOST"] = "attacker.example"
        with override_settings(CANONICAL_BASE_URL="", CANONICAL_URL_FALLBACK=False):
            with self.assertRaises(ImproperlyConfigured):
                get_canonical_url_parts(self.request)

    def test_use_https_for_fallback(self):
        self.request = self.factory.get("/", secure=True)
        with override_settings(CANONICAL_BASE_URL="", CANONICAL_URL_FALLBACK=True):
            parts = get_canonical_url_parts(self.request, use_https=True)

        self.assertEqual(parts["protocol"], "https")
