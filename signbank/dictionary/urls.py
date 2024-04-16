# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.decorators import login_required, permission_required
from django.urls import path, re_path
from django.views.generic.base import RedirectView

# Views
from . import adminviews, csv_import, delete, publicviews, update, views

# Application namespace
app_name = 'dictionary'

urlpatterns = [
    # Public views for dictionary
    path('', publicviews.GlossListPublicView.as_view(), name='public_gloss_list'),
    path('gloss/<int:pk>', publicviews.GlossDetailPublicView.as_view(),
         name='public_gloss_view'),
    # Support old URLs, redirect them to new URLs.
    path('public/gloss/',
         RedirectView.as_view(pattern_name='dictionary:public_gloss_list', permanent=False)),
    path('public/gloss/<int:pk>',
         RedirectView.as_view(pattern_name='dictionary:public_gloss_view', permanent=False)),

    # Advanced search page
    path('advanced/', permission_required('dictionary.search_gloss')
         (adminviews.GlossListView.as_view()), name='admin_gloss_list'),

    # Main views for dictionary search page and gloss detail page, these used to be 'admin' views
    path('advanced/list/', permission_required('dictionary.search_gloss')
         (adminviews.GlossListView.as_view())),
    path('advanced/gloss/<int:pk>', permission_required('dictionary.search_gloss')
         (adminviews.GlossDetailView.as_view()), name='admin_gloss_view'),

    # GlossRelation search page
    path('advanced/glossrelation/', permission_required('dictionary.search_gloss')
         (adminviews.GlossRelationListView.as_view()), name='search_glossrelation'),
    # Redirect old URL
    path('search/glossrelation/', permission_required('dictionary.search_gloss')
         (RedirectView.as_view(pattern_name='dictionary:search_glossrelation', permanent=False))),

    # Manage lexicons
    path('lexicons/', login_required(views.ManageLexiconsListView.as_view()),
         name='manage_lexicons'),
    # Apply for lexicon permissions
    path('lexicons/apply/', login_required(views.ApplyLexiconPermissionsFormView.as_view()),
         name='apply_lexicon_permissions'),

    # Create
    path('advanced/gloss/create/', views.create_gloss, name='create_gloss'),

    # Urls used to update data
    path('update/gloss/<int:glossid>',
         update.update_gloss, name='update_gloss'),
    path('update/tag/<int:glossid>',
         update.add_tag, name='add_tag'),
    path('update/relation/',
         update.add_relation, name='add_relation'),
    path('update/relationtoforeignsign/',
         update.add_relationtoforeignsign, name='add_relationtoforeignsign'),
    path('update/morphologydefinition/',
         update.add_morphology_definition, name='add_morphologydefinition'),
    path('update/glossrelation/',
         update.gloss_relation, name='add_glossrelation'),

    path('advanced/delete/glossurl/<int:glossurl>',
         delete.glossurl, name='delete_glossurl'),

    path('update/lemma/<int:glossid>',
         update.add_lemma, name='add_lemma'),


    # CSV import urls
    path('advanced/import/csv/',
         csv_import.import_gloss_csv, name='import_gloss_csv'),
    path('advanced/import/csv/confirm/',
         csv_import.confirm_import_gloss_csv, name='confirm_import_gloss_csv'),
    path('advanced/import/csv/nzsl-share/',
         csv_import.import_nzsl_share_gloss_csv, name='import_nzsl_share_gloss_csv'),
    path('advanced/import/csv/nzsl-share/confirm/',
         csv_import.confirm_import_nzsl_share_gloss_csv, name='confirm_import_nzsl_share_gloss_csv'),
    path('advanced/import/csv/qualtrics/',
         csv_import.import_qualtrics_csv, name='import_qualtrics_csv'),
    path('advanced/import/csv/qualtrics/confirm/',
         csv_import.confirm_import_qualtrics_csv, name='confirm_import_qualtrics_csv'),
    path('advanced/import/csv/manual-validation/',
         csv_import.import_manual_validation, name='import_manual_validation_csv'),
    path('advanced/import/csv/manual-validation/confirm/',
         csv_import.confirm_import_manual_validation, name='confirm_import_manual_validation_csv'),

    # AJAX urls
    path('ajax/keyword/<str:prefix>',
         views.keyword_value_list),
    path('ajax/gloss/<str:prefix>',
         adminviews.gloss_ajax_complete, name='gloss_complete'),
    path('ajax/searchresults/',
         adminviews.gloss_ajax_search_results, name='ajax_search_results'),

    # XML ecv (externally controlled vocabulary) export for ELAN
    path('ecv/<int:dataset_id>',
         adminviews.gloss_list_xml, name='gloss_list_xml'),
    # Public ECV's
    path('public-ecv/<int:dataset_id>',
         publicviews.public_gloss_list_xml, name='public_gloss_list_xml'),
    path('package/', views.package, name="package"),
    path("info/", views.info, name="info"),
    re_path(r'protected_media/(?P<filename>.*)$', views.protected_media, name="protected_media"),

    path('csv/<int:dataset_id>',
         permission_required('dictionary.search_gloss')(adminviews.gloss_list_csv), name='gloss_list_csv'),

    # Network Graph of GlossRelations
    path('network-graph/',login_required(views.network_graph), name='network_graph'),
]
