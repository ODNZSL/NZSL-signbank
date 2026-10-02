# -*- coding: utf-8 -*-
"""This command lists all Glosses and a list of each Glosses GlossVideos"""
from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from signbank.dictionary.models import Gloss
from storages.backends.s3boto3 import S3Boto3Storage
from pprint import pprint

class Command(BaseCommand):
    help = 'generate a list of gloss IDs and their video URLs'
    args = ''

    def add_arguments(self, parser):
        parser.add_argument(
            "--noid",
            default=False,
            required=False,
            action="store_true",
            help=f"Dont print the Gloss Id",
        )
        parser.add_argument(
            "--compare",
            default=False,
            required=False,
            action="store_true",
            help=f"Print the url and the 'canonical' url, comma separated",
        )
        parser.add_argument(
            "--sameonly",
            default=False,
            required=False,
            action="store_true",
            help=f"Only show entries where url and 'canonical' url match",
        )
        parser.add_argument(
            "--convert",
            default=False,
            required=False,
            action="store_true",
            help=f"Rename the file on Storage, and overwrite the old url with the 'canonical' url, in the database (default dry-run)",
        )
        parser.add_argument(
            "--commit",
            default=False,
            required=False,
            action="store_true",
            help=f"WARNING, DESTRUCTIVE: With '--convert' actually perform the actions rather than just dry-running them",
        )

    def handle(self, *args, **options):
        for gloss in Gloss.objects.all():
            for glossvideo in gloss.glossvideo_set.all():
                storage = glossvideo.videofile.storage
                orig_name = glossvideo.videofile.name
                canon_name = storage.get_valid_name(glossvideo.create_filename())
                if not options["noid"]:
                    print(gloss.id)
                same = orig_name == canon_name
                if not options["sameonly"] or ( same and options["sameonly"] ):
                    print(orig_name, end="")
                    print(f",{canon_name}" if options["compare"] else "")
                    if isinstance(storage, S3Boto3Storage):
                        print(f"S3 Storage: {storage.bucket_name}")
                if options["convert"]:

                    # DEV safety, purely for testing
                    if storage.bucket_name != "nzsl-signbank-media-dev":
                        print("ABORT: Not DEV bucket!")
                        return

                    if same:
                        print(f"NO CHANGE: {orig_name}")
                    else:
                        # Prove the stored item exists
                        if storage.exists(orig_name):
                            print(f"Object exists: {orig_name}")
                        else:
                            print(f"ERROR: Storage could not find {orig_name}")
                            continue

                        # Move it to the new name, in storage and db
                        if options["commit"]:
                            glossvideo.rename_video()
                            glossvideo.save()
                            pprint(glossvideo.__dict__)
                            print(f"RENAMED: {orig_name} --> {canon_name}")
                        else:
                            print(f"(DRY-RUN) {orig_name} --> {canon_name}")
