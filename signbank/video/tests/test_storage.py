from unittest.mock import MagicMock, PropertyMock, patch
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from storages.backends.s3boto3 import S3Boto3Storage

from signbank.video.models import GlossVideoStorageMixin


class S3TestStorage(GlossVideoStorageMixin, S3Boto3Storage):
    """The production storage shape; tests otherwise run on local file storage."""


def generate_pem_private_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


class GlossVideoS3StorageTestCase(TestCase):
    def make_storage(self):
        # S3Boto3Storage reads its settings on construction.
        storage = S3TestStorage(bucket_name='test-bucket')
        bucket = MagicMock()
        bucket.name = 'test-bucket'
        patcher = patch.object(
            S3TestStorage, 'bucket', new_callable=PropertyMock, return_value=bucket)
        patcher.start()
        self.addCleanup(patcher.stop)
        return storage, bucket.meta.client

    def test_set_public_sets_acl_and_visibility_tag(self):
        storage, client = self.make_storage()
        storage.set_public('glossvideo/1-a.mp4', True)
        client.put_object_acl.assert_called_once_with(
            ACL='public-read', Bucket='test-bucket', Key='glossvideo/1-a.mp4')
        client.put_object_tagging.assert_called_once_with(
            Bucket='test-bucket', Key='glossvideo/1-a.mp4',
            Tagging={'TagSet': [{'Key': 'visibility', 'Value': 'public'}]})

    def test_set_private_sets_acl_and_visibility_tag(self):
        storage, client = self.make_storage()
        storage.set_public('glossvideo/1-a.mp4', False)
        client.put_object_acl.assert_called_once_with(
            ACL='private', Bucket='test-bucket', Key='glossvideo/1-a.mp4')
        client.put_object_tagging.assert_called_once_with(
            Bucket='test-bucket', Key='glossvideo/1-a.mp4',
            Tagging={'TagSet': [{'Key': 'visibility', 'Value': 'private'}]})

    def test_set_public_without_name_is_noop(self):
        storage, client = self.make_storage()
        storage.set_public('', True)
        client.put_object_acl.assert_not_called()
        client.put_object_tagging.assert_not_called()

    def test_url_is_cloudfront_signed_when_configured(self):
        with override_settings(
            AWS_S3_CUSTOM_DOMAIN='private-media.example.com',
            AWS_CLOUDFRONT_KEY_ID='KTESTKEYID',
            AWS_CLOUDFRONT_KEY=generate_pem_private_key(),
        ):
            storage, client = self.make_storage()
        url = urlsplit(storage.url('glossvideo/1-kōrero tahi.mp4'))
        self.assertEqual(url.netloc, 'private-media.example.com')
        self.assertEqual(url.path, '/glossvideo/1-k%C5%8Drero%20tahi.mp4')
        query = parse_qs(url.query)
        self.assertEqual(query['Key-Pair-Id'], ['KTESTKEYID'])
        self.assertIn('Signature', query)
        self.assertIn('Expires', query)
        client.generate_presigned_url.assert_not_called()

    @override_settings(CLOUDFRONT_PUBLIC_MEDIA_DOMAIN=None)
    def test_public_url_falls_back_to_s3(self):
        storage, _client = self.make_storage()
        self.assertEqual(
            storage.public_url('glossvideo/1-a.mp4'),
            'https://test-bucket.s3.amazonaws.com/glossvideo/1-a.mp4')

    def test_public_url_uses_unsigned_public_domain(self):
        # Exported to the dictionary scripts and stored long-term, so must never be signed,
        # even when url() signs with CloudFront.
        with override_settings(
            AWS_S3_CUSTOM_DOMAIN='private-media.example.com',
            AWS_CLOUDFRONT_KEY_ID='KTESTKEYID',
            AWS_CLOUDFRONT_KEY=generate_pem_private_key(),
            CLOUDFRONT_PUBLIC_MEDIA_DOMAIN='media.example.com',
        ):
            storage, _client = self.make_storage()
            self.assertEqual(
                storage.public_url('glossvideo/1-kōrero tahi.mp4'),
                'https://media.example.com/glossvideo/1-k%C5%8Drero%20tahi.mp4')
