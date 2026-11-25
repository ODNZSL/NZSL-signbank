from unittest.mock import MagicMock, PropertyMock, patch
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from storages.backends.s3boto3 import S3Boto3Storage

from signbank.video.models import export_media_url


def generate_pem_private_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@override_settings(
    AWS_S3_CUSTOM_DOMAIN='signbank-media.example.com',
    AWS_CLOUDFRONT_KEY_ID='KTESTKEYID',
    AWS_CLOUDFRONT_KEY=generate_pem_private_key(),
)
class CloudFrontSignedUrlTestCase(TestCase):
    """Production uses S3Boto3Storage; tests otherwise run on local file storage."""

    def setUp(self):
        # S3Boto3Storage reads its settings on construction.
        self.storage = S3Boto3Storage(bucket_name='test-bucket')
        bucket = MagicMock()
        bucket.name = 'test-bucket'
        self.client = bucket.meta.client
        patcher = patch.object(
            S3Boto3Storage, 'bucket', new_callable=PropertyMock, return_value=bucket)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_url_is_cloudfront_signed(self):
        url = urlsplit(self.storage.url('glossvideo/1-kōrero tahi.mp4'))
        self.assertEqual(url.netloc, 'signbank-media.example.com')
        self.assertEqual(url.path, '/glossvideo/1-k%C5%8Drero%20tahi.mp4')
        query = parse_qs(url.query)
        self.assertEqual(query['Key-Pair-Id'], ['KTESTKEYID'])
        self.assertIn('Signature', query)
        self.assertIn('Expires', query)
        self.client.generate_presigned_url.assert_not_called()


class ExportMediaUrlTestCase(TestCase):
    @override_settings(EXPORT_MEDIA_BASE_URL='https://test-bucket.s3.amazonaws.com')
    def test_uses_export_base_url(self):
        self.assertEqual(
            export_media_url('glossvideo/1-a.mp4'),
            'https://test-bucket.s3.amazonaws.com/glossvideo/1-a.mp4')

    @override_settings(
        EXPORT_MEDIA_BASE_URL='https://test-bucket.s3.amazonaws.com',
        AWS_S3_CUSTOM_DOMAIN='signbank-media.example.com',
        AWS_CLOUDFRONT_KEY_ID='KTESTKEYID',
        AWS_CLOUDFRONT_KEY=generate_pem_private_key(),
    )
    def test_unaffected_by_signbank_media_access(self):
        # Exported URLs are stored long-term by the dictionary scripts, so they must not
        # follow Signbank's own signed CloudFront domain.
        self.assertEqual(
            export_media_url('glossvideo/1-a.mp4'),
            'https://test-bucket.s3.amazonaws.com/glossvideo/1-a.mp4')

    @override_settings(EXPORT_MEDIA_BASE_URL='')
    def test_local_storage_falls_back_to_site_domain(self):
        self.assertEqual(
            export_media_url('glossvideo/1-a.mp4'),
            f"{Site.objects.get_current().domain}{settings.MEDIA_URL}glossvideo/1-a.mp4")
