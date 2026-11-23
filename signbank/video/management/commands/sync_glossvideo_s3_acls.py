# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import sys

from django.core.management.base import BaseCommand, CommandError

from signbank.video.models import GlossVideo, visibility_tag_value


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class Command(BaseCommand):
    help = (
        "Sync S3 canned ACLs and visibility tags for GlossVideo rows to match each row's "
        "is_public flag. Use to backfill existing objects or repair mismatched records. "
        "With --verify, only reads each object's visibility tag and reports mismatches."
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
        parser.add_argument(
            '--verify',
            action='store_true',
            help="Read each object's visibility tag and report rows where it doesn't match "
                 "is_public. Makes no changes.",
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

        processed = 0
        skipped = 0
        mismatched = 0
        failed = 0
        for glossvideo in queryset.iterator():
            if not glossvideo.videofile.name:
                skipped += 1
                continue
            expected = visibility_tag_value(glossvideo.is_public)
            message = (
                f"video_id={glossvideo.pk} gloss_id={glossvideo.gloss_id} "
                f"key={glossvideo.videofile.name} visibility={expected}"
            )
            if options['dry_run']:
                self.stdout.write(message)
                processed += 1
                continue
            try:
                if options['verify']:
                    actual = glossvideo.videofile.storage.get_visibility(glossvideo.videofile.name)
                    if actual != expected:
                        mismatched += 1
                        self.stdout.write(f"MISMATCH {message} actual={actual}")
                else:
                    glossvideo._sync_s3_acl()
                    self.stdout.write(message)
            except Exception as e:
                # Keep going: one missing or inaccessible object shouldn't stop a full backfill.
                failed += 1
                eprint(f"FAILED {message} error={e!r}")
                continue
            processed += 1

        eprint(
            f"Done. processed={processed} skipped_empty={skipped} "
            f"mismatched={mismatched} failed={failed}"
        )
        if mismatched or failed:
            raise CommandError(f"{mismatched} mismatched and {failed} failed GlossVideo(s); see output above.")
