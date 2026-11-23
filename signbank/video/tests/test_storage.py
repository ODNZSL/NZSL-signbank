from io import StringIO
from unittest.mock import MagicMock, PropertyMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from storages.backends.s3boto3 import S3Boto3Storage

from signbank.dictionary.models import Dataset, FieldChoice, Gloss, SignLanguage
from signbank.video.models import GlossVideo, GlossVideoStorageMixin


class S3TestStorage(GlossVideoStorageMixin, S3Boto3Storage):
    """The production storage shape; tests otherwise run on local file storage."""


class GlossVideoS3StorageTestCase(TestCase):
    def setUp(self):
        self.storage = S3TestStorage(bucket_name='test-bucket')
        self.bucket = MagicMock()
        self.bucket.name = 'test-bucket'
        self.client = self.bucket.meta.client
        bucket_patcher = patch.object(
            S3TestStorage, 'bucket', new_callable=PropertyMock, return_value=self.bucket)
        bucket_patcher.start()
        self.addCleanup(bucket_patcher.stop)

    def test_set_public_sets_acl_and_visibility_tag(self):
        self.storage.set_public('glossvideo/1-a.mp4', True)
        self.client.put_object_acl.assert_called_once_with(
            ACL='public-read', Bucket='test-bucket', Key='glossvideo/1-a.mp4')
        self.client.put_object_tagging.assert_called_once_with(
            Bucket='test-bucket', Key='glossvideo/1-a.mp4',
            Tagging={'TagSet': [{'Key': 'visibility', 'Value': 'public'}]})

    def test_set_private_sets_acl_and_visibility_tag(self):
        self.storage.set_public('glossvideo/1-a.mp4', False)
        self.client.put_object_acl.assert_called_once_with(
            ACL='private', Bucket='test-bucket', Key='glossvideo/1-a.mp4')
        self.client.put_object_tagging.assert_called_once_with(
            Bucket='test-bucket', Key='glossvideo/1-a.mp4',
            Tagging={'TagSet': [{'Key': 'visibility', 'Value': 'private'}]})

    def test_set_public_without_name_is_noop(self):
        self.storage.set_public('', True)
        self.client.put_object_acl.assert_not_called()
        self.client.put_object_tagging.assert_not_called()

    def test_get_visibility_reads_tag(self):
        self.client.get_object_tagging.return_value = {
            'TagSet': [{'Key': 'other', 'Value': 'x'}, {'Key': 'visibility', 'Value': 'public'}]}
        self.assertEqual(self.storage.get_visibility('k.mp4'), 'public')

    def test_get_visibility_untagged_is_none(self):
        self.client.get_object_tagging.return_value = {'TagSet': []}
        self.assertIsNone(self.storage.get_visibility('k.mp4'))

    @override_settings(CLOUDFRONT_MEDIA_DOMAIN=None)
    def test_public_url_falls_back_to_s3_without_cloudfront(self):
        self.assertIsNone(self.storage.cdn_url('glossvideo/1-a.mp4'))
        self.assertEqual(
            self.storage.public_url('glossvideo/1-a.mp4'),
            'https://test-bucket.s3.amazonaws.com/glossvideo/1-a.mp4')

    @override_settings(CLOUDFRONT_MEDIA_DOMAIN='media.example.com')
    def test_public_url_uses_cloudfront_and_encodes_key(self):
        self.assertEqual(
            self.storage.public_url('glossvideo/1-kōrero tahi.mp4'),
            'https://media.example.com/glossvideo/1-k%C5%8Drero%20tahi.mp4')

    @override_settings(CLOUDFRONT_MEDIA_DISTRIBUTION_ID='DIST123')
    @patch('signbank.video.models.boto3.client')
    def test_invalidate_cdn_cache(self, mock_boto_client):
        self.storage.invalidate_cdn_cache(['glossvideo/1-a.mp4', '', 'glossvideo/1-a.mp4'])
        mock_boto_client.assert_called_once_with('cloudfront')
        kwargs = mock_boto_client.return_value.create_invalidation.call_args.kwargs
        self.assertEqual(kwargs['DistributionId'], 'DIST123')
        self.assertEqual(
            kwargs['InvalidationBatch']['Paths'],
            {'Quantity': 1, 'Items': ['/glossvideo/1-a.mp4']})

    @override_settings(CLOUDFRONT_MEDIA_DISTRIBUTION_ID=None)
    @patch('signbank.video.models.boto3.client')
    def test_invalidate_cdn_cache_without_distribution_is_noop(self, mock_boto_client):
        self.storage.invalidate_cdn_cache(['glossvideo/1-a.mp4'])
        mock_boto_client.assert_not_called()

    @override_settings(CLOUDFRONT_MEDIA_DISTRIBUTION_ID='DIST123')
    @patch('signbank.video.models.boto3.client')
    def test_invalidate_cdn_cache_swallows_errors(self, mock_boto_client):
        mock_boto_client.return_value.create_invalidation.side_effect = Exception('boom')
        with self.assertLogs('signbank.video.models', level='ERROR'):
            self.storage.invalidate_cdn_cache(['glossvideo/1-a.mp4'])


class GlossVideoTestDataMixin:
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.signlanguage = SignLanguage.objects.create(
            pk=2, name='testsignlanguage', language_code_3char='tst')
        self.dataset = Dataset.objects.create(
            name='testdataset', signlanguage=self.signlanguage)
        self.testgloss = Gloss.objects.create(
            idgloss='testgloss', dataset=self.dataset,
            created_by=self.user, updated_by=self.user)
        self.video_type = FieldChoice.objects.create(
            field='video_type', machine_value=1000, english_name='Test')

    def create_video(self, is_public):
        return GlossVideo.objects.create(
            gloss=self.testgloss, dataset=self.dataset,
            videofile=SimpleUploadedFile('clip.mp4', b'video-bytes', content_type='video/mp4'),
            video_type=self.video_type, is_public=is_public)


@patch('signbank.video.models.GlossVideoDynamicStorage.set_public')
class GlossVideoCdnTestCase(GlossVideoTestDataMixin, TestCase):
    @patch('signbank.video.models.GlossVideoDynamicStorage.cdn_url', return_value='https://cdn/x.mp4')
    def test_public_video_url_uses_cdn(self, mock_cdn_url, mock_set_public):
        video = self.create_video(is_public=True)
        self.assertEqual(video.get_absolute_url(), 'https://cdn/x.mp4')
        mock_cdn_url.assert_called_once_with(video.videofile.name)

    @patch('signbank.video.models.GlossVideoDynamicStorage.cdn_url', return_value='https://cdn/x.mp4')
    def test_private_video_url_uses_storage_url(self, mock_cdn_url, mock_set_public):
        video = self.create_video(is_public=False)
        self.assertEqual(video.get_absolute_url(), video.videofile.url)
        mock_cdn_url.assert_not_called()

    def test_public_video_url_without_cdn_uses_storage_url(self, mock_set_public):
        video = self.create_video(is_public=True)
        self.assertEqual(video.get_absolute_url(), video.videofile.url)

    @patch('signbank.video.models.GlossVideoDynamicStorage.invalidate_cdn_cache')
    def test_making_video_private_invalidates_cdn(self, mock_invalidate, mock_set_public):
        video = self.create_video(is_public=True)
        mock_invalidate.assert_not_called()
        video.set_public(False)
        mock_invalidate.assert_called_once()
        self.assertIn(video.videofile.name, mock_invalidate.call_args[0][0])

    @patch('signbank.video.models.GlossVideoDynamicStorage.invalidate_cdn_cache')
    def test_making_video_public_does_not_invalidate_cdn(self, mock_invalidate, mock_set_public):
        video = self.create_video(is_public=False)
        video.set_public(True)
        mock_invalidate.assert_not_called()


@patch('signbank.video.models.GlossVideoDynamicStorage.set_public')
class SyncGlossVideoS3AclsCommandTestCase(GlossVideoTestDataMixin, TestCase):
    def run_command(self, *args):
        out, err = StringIO(), StringIO()
        with patch('sys.stderr', err):
            call_command('sync_glossvideo_s3_acls', *args, stdout=out)
        return out.getvalue(), err.getvalue()

    def test_sync_sets_visibility_from_is_public(self, mock_set_public):
        public = self.create_video(is_public=True)
        private = self.create_video(is_public=False)
        mock_set_public.reset_mock()
        self.run_command()
        calls = {c.args[0]: c.args[1] for c in mock_set_public.call_args_list}
        self.assertEqual(calls, {public.videofile.name: True, private.videofile.name: False})

    def test_sync_continues_after_failure_and_exits_with_error(self, mock_set_public):
        self.create_video(is_public=True)
        self.create_video(is_public=True)
        mock_set_public.reset_mock()
        mock_set_public.side_effect = [Exception('NoSuchKey'), None]
        with patch('sys.stderr', StringIO()) as err:
            with self.assertRaises(CommandError):
                call_command('sync_glossvideo_s3_acls', stdout=StringIO())
        self.assertEqual(mock_set_public.call_count, 2)
        self.assertIn('processed=1', err.getvalue())
        self.assertIn('failed=1', err.getvalue())

    @patch('signbank.video.models.GlossVideoDynamicStorage.get_visibility')
    def test_verify_reports_mismatches_without_writing(self, mock_get_visibility, mock_set_public):
        matching = self.create_video(is_public=True)
        mismatched = self.create_video(is_public=False)
        mock_set_public.reset_mock()
        mock_get_visibility.side_effect = lambda name: 'public'
        out = StringIO()
        with patch('sys.stderr', StringIO()):
            with self.assertRaises(CommandError):
                call_command('sync_glossvideo_s3_acls', '--verify', stdout=out)
        mock_set_public.assert_not_called()
        self.assertIn(f'video_id={mismatched.pk} ', out.getvalue())
        self.assertNotIn(f'video_id={matching.pk} ', out.getvalue())

    @patch('signbank.video.models.GlossVideoDynamicStorage.get_visibility', return_value='public')
    def test_verify_passes_when_all_match(self, mock_get_visibility, mock_set_public):
        self.create_video(is_public=True)
        out, _err = self.run_command('--verify')
        self.assertNotIn('MISMATCH', out)
