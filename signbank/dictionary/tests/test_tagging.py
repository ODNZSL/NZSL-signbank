# -*- coding: utf-8 -*-
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse
from django_comments.models import Comment
from guardian.shortcuts import assign_perm
from taggit.models import Tag

from signbank.dictionary.models import Dataset, Gloss, GlossRelation, SignLanguage
from signbank.tagging.utils import add_tag, normalize_tag_name, tags_for_object


class NormalizeTagNameTestCase(TestCase):
    def test_force_lowercase_and_strip(self):
        self.assertEqual(normalize_tag_name('  Foo Bar  '), 'foo bar')


class GlossTaggingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.user.user_permissions.add(Permission.objects.get(codename='change_gloss'))
        self.user.save()
        self.client = Client()
        self.client.force_login(self.user)

        self.signlanguage = SignLanguage.objects.create(
            pk=2, name='testsignlanguage', language_code_3char='tst'
        )
        self.dataset = Dataset.objects.create(
            name='testdataset', signlanguage=self.signlanguage
        )
        assign_perm('view_dataset', self.user, self.dataset)
        self.gloss = Gloss.objects.create(
            idgloss='test-gloss',
            dataset=self.dataset,
            created_by=self.user,
            updated_by=self.user,
        )
        self.tag, _ = Tag.objects.get_or_create(name='ready for validation')

    def test_add_and_remove_tag_with_spaces(self):
        self.gloss.tags.add(normalize_tag_name(self.tag.name))
        self.assertTrue(self.gloss.tags.filter(name='ready for validation').exists())

        response = self.client.post(
            reverse('dictionary:add_tag', args=[self.gloss.pk]),
            {'tag': self.tag.name, 'delete': 'true'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'deleted')
        self.assertFalse(self.gloss.tags.filter(name='ready for validation').exists())

    def test_gloss_relation_tags(self):
        target = Gloss.objects.create(
            idgloss='target-gloss',
            dataset=self.dataset,
            created_by=self.user,
            updated_by=self.user,
        )
        relation = GlossRelation.objects.create(source=self.gloss, target=target)
        relation.tags.add('variant')
        self.assertEqual(list(relation.tag()), list(relation.tags.all()))
        self.assertEqual(relation.tags.get().name, 'variant')


class CommentTaggingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='commenter', password='test')
        self.signlanguage = SignLanguage.objects.create(
            pk=2, name='testsignlanguage', language_code_3char='tst'
        )
        self.dataset = Dataset.objects.create(
            name='testdataset', signlanguage=self.signlanguage
        )
        self.gloss = Gloss.objects.create(
            idgloss='comment-gloss',
            dataset=self.dataset,
            created_by=self.user,
            updated_by=self.user,
        )
        from django.contrib.sites.models import Site
        site = Site.objects.get_current()
        self.comment = Comment.objects.create(
            content_type=ContentType.objects.get_for_model(Gloss),
            object_pk=str(self.gloss.pk),
            site=site,
            user=self.user,
            user_name=self.user.username,
            comment='A comment',
        )

    def test_add_tag_via_gfk_helper(self):
        add_tag(self.comment, 'Needs Review')
        tags = tags_for_object(self.comment)
        self.assertEqual([t.name for t in tags], ['needs review'])
