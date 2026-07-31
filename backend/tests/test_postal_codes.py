import unittest

from app.api.dependencies.auth import capability_for_operation
from app.api.v1.endpoints.postal_codes import list_postal_codes
from app.api.v1.endpoints.postal_codes import load_postal_code_catalog
from app.main import app
from app.models.auth import Capability


class PostalCodeEndpointTestCase(unittest.TestCase):
    def test_lookup_requires_explicit_service_read_capability(self) -> None:
        self.assertEqual(
            capability_for_operation("GET", "/api/v1/postal-codes"),
            Capability.services_read,
        )

    def test_lookup_returns_normalized_matches(self) -> None:
        catalog = load_postal_code_catalog()

        self.assertGreater(len(catalog), 0)
        matches = list_postal_codes("88520")

        self.assertGreaterEqual(len(matches), 1)
        self.assertTrue(all(item.postal_code == "88520" for item in matches))
        self.assertEqual(matches[0].state, "Tamaulipas")

    def test_route_is_registered_in_openapi(self) -> None:
        schema = app.openapi()

        self.assertIn("/api/v1/postal-codes", schema["paths"])
