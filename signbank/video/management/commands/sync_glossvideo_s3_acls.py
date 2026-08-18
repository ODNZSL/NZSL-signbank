# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import sys

from django.core.management.base import BaseCommand

from signbank.video.models import GlossVideo


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class Command(BaseCommand):
    help = (
        "Sync S3 canned ACLs for GlossVideo rows to match each row's is_public flag. "
        "Use after deploying ACL sync fixes or to repair mismatched production records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--gloss-id',
            type=int,
            default=None,
            help='Only sync GlossVideos for this gloss primary key.',
        )
        parser.add_argument(
            '--video-id',
            type=int,
            default=None,
            help='Only sync this GlossVideo primary key.',
        )
        parser.add_argument(
            '--public-only',
            action='store_true',
            help='Only sync rows where is_public=True.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List rows that would be synced without calling S3.',
        )

    def handle(self, *args, **options):
        queryset = GlossVideo.objects.exclude(videofile='').order_by('pk')
        if options['gloss_id'] is not None:
            queryset = queryset.filter(gloss_id=options['gloss_id'])
        if options['video_id'] is not None:
            queryset = queryset.filter(pk=options['video_id'])
        if options['public_only']:
            queryset = queryset.filter(is_public=True)

        total = queryset.count()
        eprint(f"GlossVideos to process: {total}")

        synced = 0
        skipped = 0
        for glossvideo in queryset.iterator():
            if not glossvideo.videofile.name:
                skipped += 1
                continue
            acl = 'public-read' if glossvideo.is_public else 'private'
            message = (
                f"video_id={glossvideo.pk} gloss_id={glossvideo.gloss_id} "
                f"key={glossvideo.videofile.name} acl={acl}"
            )
            if options['dry_run']:
                print(message)
                synced += 1
                continue
            glossvideo._sync_s3_acl()
            print(message)
            synced += 1

        eprint(f"Done. processed={synced} skipped_empty={skipped}")
