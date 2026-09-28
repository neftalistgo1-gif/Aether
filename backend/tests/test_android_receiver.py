import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANDROID_ROOT = PROJECT_ROOT / "android-receiver" / "app" / "src" / "main"


class AndroidReceiverSourceTestCase(unittest.TestCase):
    def test_manifest_accepts_images_and_pdf_without_storage_permission(self) -> None:
        manifest = (ANDROID_ROOT / "AndroidManifest.xml").read_text(
            encoding="utf-8"
        )

        self.assertIn("android.intent.action.SEND", manifest)
        self.assertIn('android:mimeType="image/*"', manifest)
        self.assertIn('android:mimeType="application/pdf"', manifest)
        self.assertIn('android:usesCleartextTraffic="false"', manifest)
        self.assertNotIn("READ_EXTERNAL_STORAGE", manifest)
        self.assertNotIn("READ_MEDIA_IMAGES", manifest)

    def test_session_is_encrypted_and_upload_uses_native_bridge(self) -> None:
        token_vault = (
            ANDROID_ROOT
            / "java"
            / "com"
            / "aetheramr"
            / "receiver"
            / "TokenVault.java"
        ).read_text(encoding="utf-8")
        activity = (
            ANDROID_ROOT
            / "java"
            / "com"
            / "aetheramr"
            / "receiver"
            / "MainActivity.java"
        ).read_text(encoding="utf-8")

        self.assertIn("AndroidKeyStore", token_vault)
        self.assertIn("AES/GCM/NoPadding", token_vault)
        self.assertIn("/api/v1/payments/shared-receipts", activity)
        self.assertIn("Bearer ", activity)
        self.assertIn("X-Aether-Session", activity)


if __name__ == "__main__":
    unittest.main()
