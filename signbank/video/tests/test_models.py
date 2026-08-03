from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from signbank.dictionary.models import Dataset, FieldChoice, Gloss, SignLanguage
from signbank.video.models import GlossVideo


class GlossVideoAclSyncTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.signlanguage = SignLanguage.objects.create(
            pk=2, name='testsignlanguage', language_code_3char='tst')
        self.dataset = Dataset.objects.create(
            name='testdataset', signlanguage=self.signlanguage)
        self.testgloss = Gloss.objects.create(
            idgloss='testgloss',
            dataset=self.dataset,
            created_by=self.user,
            updated_by=self.user,
        )
        self.video_type = FieldChoice.objects.create(
            field='video_type', machine_value=1000, english_name='Test')

    @patch('signbank.video.models.GlossVideoDynamicStorage.set_public')
    def test_upload_syncs_public_acl(self, mock_set_public):
        GlossVideo.objects.create(
            gloss=self.testgloss,
            dataset=self.dataset,
            videofile=SimpleUploadedFile(
                'clip.mp4', b'video-bytes', content_type='video/mp4'),
            video_type=self.video_type,
            is_public=True,
        )
        self.assertTrue(mock_set_public.called)
        self.assertTrue(mock_set_public.call_args[0][1])

    @patch('signbank.video.models.GlossVideoDynamicStorage.set_public')
    def test_toggle_is_public_syncs_acl(self, mock_set_public):
        glossvideo = GlossVideo.objects.create(
            gloss=self.testgloss,
            dataset=self.dataset,
            videofile=SimpleUploadedFile(
                'clip.mp4', b'video-bytes', content_type='video/mp4'),
            video_type=self.video_type,
            is_public=True,
        )
        mock_set_public.reset_mock()
        glossvideo.is_public = False
        glossvideo.save()
        mock_set_public.assert_called_once()
        self.assertFalse(mock_set_public.call_args[0][1])

    @patch('signbank.video.models.GlossVideoDynamicStorage.set_public')
    def test_set_public_false_syncs_private_acl(self, mock_set_public):
        glossvideo = GlossVideo.objects.create(
            gloss=self.testgloss,
            dataset=self.dataset,
            videofile=SimpleUploadedFile(
                'clip.mp4', b'video-bytes', content_type='video/mp4'),
            video_type=self.video_type,
            is_public=True,
        )
        mock_set_public.reset_mock()
        glossvideo.set_public(False)
        mock_set_public.assert_called_once()
        self.assertFalse(mock_set_public.call_args[0][1])


class GlossVideoSharedKeyDeleteTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.signlanguage = SignLanguage.objects.create(
            pk=2, name='testsignlanguage', language_code_3char='tst')
        self.dataset = Dataset.objects.create(
            name='testdataset', signlanguage=self.signlanguage)
        self.testgloss = Gloss.objects.create(
            idgloss='testgloss',
            dataset=self.dataset,
            created_by=self.user,
            updated_by=self.user,
        )
        self.video_type = FieldChoice.objects.create(
            field='video_type', machine_value=1000, english_name='Test')

    def test_delete_duplicate_row_keeps_shared_storage_object(self):
        drawing = GlossVideo.objects.create(
            gloss=self.testgloss,
            dataset=self.dataset,
            videofile=SimpleUploadedFile(
                'drawing.png', b'drawing-bytes', content_type='image/png'),
            video_type=self.video_type,
            is_public=True,
        )
        duplicate = GlossVideo.objects.create(
            gloss=self.testgloss,
            dataset=self.dataset,
            videofile=SimpleUploadedFile(
                'video.mp4', b'video-bytes', content_type='video/mp4'),
            video_type=self.video_type,
            is_public=False,
        )
        shared_key = drawing.videofile.name
        GlossVideo.objects.filter(pk=duplicate.pk).update(videofile=shared_key)
        duplicate.refresh_from_db()
        storage = drawing.videofile.storage
        duplicate_pk = duplicate.pk
        duplicate.delete()
        self.assertFalse(GlossVideo.objects.filter(pk=duplicate_pk).exists())
        self.assertTrue(GlossVideo.objects.filter(pk=drawing.pk).exists())
        self.assertTrue(storage.exists(shared_key))


class ChangeGlossVideoPublicityTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test')
        permission = Permission.objects.get(codename='change_glossvideo')
        self.user.user_permissions.add(permission)
        self.client = Client()
        self.client.login(username='test', password='test')

        self.signlanguage = SignLanguage.objects.create(
            pk=2, name='testsignlanguage', language_code_3char='tst')
        self.dataset = Dataset.objects.create(
            name='testdataset', signlanguage=self.signlanguage)
        self.testgloss = Gloss.objects.create(
            idgloss='testgloss',
            dataset=self.dataset,
            created_by=self.user,
            updated_by=self.user,
        )
        self.video_type = FieldChoice.objects.create(
            field='video_type', machine_value=1000, english_name='Test')
        assign_perm('view_dataset', self.user, self.dataset)
        self.glossvideo = GlossVideo.objects.create(
            gloss=self.testgloss,
            dataset=self.dataset,
            videofile=SimpleUploadedFile(
                'clip.mp4', b'video-bytes', content_type='video/mp4'),
            video_type=self.video_type,
            is_public=True,
        )

    @patch('signbank.video.models.GlossVideoDynamicStorage.set_public')
    def test_set_private_parses_false_string(self, mock_set_public):
        response = self.client.post(reverse('video:change_glossvideo_publicity'), {
            'videoid': self.glossvideo.pk,
            'is_public': 'False',
        })
        self.assertEqual(response.status_code, 302)
        self.glossvideo.refresh_from_db()
        self.assertFalse(self.glossvideo.is_public)
        self.assertTrue(any(call[0][1] is False for call in mock_set_public.call_args_list))
