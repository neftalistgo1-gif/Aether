import unittest
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import UploadFile

from app.api.v1.endpoints.payments import (
    claim_native_receipt,
    receive_native_shared_receipt,
)
from app.services.native_shared_receipts import (
    ClaimedNativeReceipt,
    StoredNativeReceipt,
    claim_native_shared_receipt,
    cleanup_expired_native_receipts,
    store_native_shared_receipt,
)


class NativeSharedReceiptTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.storage_root = Path(self.temporary_directory.name)
        self.user_id = uuid4()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_receipt_is_private_single_use_and_preserves_content(self) -> None:
        content = b"\x89PNG\r\n\x1a\n" + b"payment-proof"
        upload = UploadFile(
            filename="../comprobante.png",
            file=BytesIO(content),
        )
        stored = store_native_shared_receipt(
            upload,
            user_id=self.user_id,
            storage_root=self.storage_root,
        )

        self.assertEqual(stored.filename, "comprobante.png")
        self.assertIsNone(
            claim_native_shared_receipt(
                stored.receipt_id,
                user_id=uuid4(),
                storage_root=self.storage_root,
            )
        )
        claimed = claim_native_shared_receipt(
            stored.receipt_id,
            user_id=self.user_id,
            storage_root=self.storage_root,
        )

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.content, content)
        self.assertEqual(claimed.content_type, "image/png")
        self.assertFalse((self.storage_root / str(stored.receipt_id)).exists())
        self.assertIsNone(
            claim_native_shared_receipt(
                stored.receipt_id,
                user_id=self.user_id,
                storage_root=self.storage_root,
            )
        )

    def test_expired_receipt_is_removed(self) -> None:
        created_at = datetime(2026, 9, 25, tzinfo=UTC)
        upload = UploadFile(
            filename="comprobante.pdf",
            file=BytesIO(b"%PDF-1.7\nproof"),
        )
        stored = store_native_shared_receipt(
            upload,
            user_id=self.user_id,
            storage_root=self.storage_root,
            now=created_at,
        )

        claimed = claim_native_shared_receipt(
            stored.receipt_id,
            user_id=self.user_id,
            storage_root=self.storage_root,
            now=created_at + timedelta(hours=25),
        )

        self.assertIsNone(claimed)
        self.assertFalse((self.storage_root / str(stored.receipt_id)).exists())

    def test_cleanup_ignores_unrelated_directories(self) -> None:
        unrelated = self.storage_root / "do-not-touch"
        unrelated.mkdir()
        (unrelated / "file.txt").write_text("keep", encoding="utf-8")

        cleanup_expired_native_receipts(
            storage_root=self.storage_root,
            now=datetime.now(UTC) + timedelta(days=2),
        )

        self.assertTrue((unrelated / "file.txt").is_file())

    def test_endpoints_use_the_authenticated_user_directly(self) -> None:
        receipt_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        upload = UploadFile(
            filename="comprobante.png",
            file=BytesIO(b"\x89PNG\r\n\x1a\nproof"),
        )
        user = SimpleNamespace(id=self.user_id)

        with patch(
            "app.api.v1.endpoints.payments.store_native_shared_receipt",
            return_value=StoredNativeReceipt(
                receipt_id=receipt_id,
                filename="comprobante.png",
                content_type="image/png",
                expires_at=expires_at,
            ),
        ) as store_receipt:
            stored = receive_native_shared_receipt(upload, user)

        store_receipt.assert_called_once_with(upload, user_id=self.user_id)
        self.assertEqual(stored.receipt_id, receipt_id)

        with patch(
            "app.api.v1.endpoints.payments.claim_native_shared_receipt",
            return_value=ClaimedNativeReceipt(
                filename="comprobante.png",
                content_type="image/png",
                content=b"proof-content",
            ),
        ) as claim_receipt:
            response = claim_native_receipt(receipt_id, user)

        claim_receipt.assert_called_once_with(
            receipt_id,
            user_id=self.user_id,
        )
        self.assertEqual(response.body, b"proof-content")


if __name__ == "__main__":
    unittest.main()
