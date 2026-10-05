# -*- coding: utf-8 -*-
"""This command lists all Glosses and a list of each Glosses GlossVideos"""
from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from signbank.dictionary.models import Gloss
from storages.backends.s3boto3 import S3Boto3Storage
from pprint import pprint
from signbank.video.models import GlossVideo


class Command(BaseCommand):

    help = (
        "Report Gloss IDs and their GlossVideo urls. Can also update GlossVideo urls to newer 'canonical' versions. "
        "By default this is dry-run, but '--commit' will write the changes back to storage (eg. S3) and the database. "
        "A DATABASE_URL must be defined. "
        "If using S3 an AWS_PROFILE must be defined. The S3 bucket used will be the one defined in django settings."
    )

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
            help=f"Print the GlossVideo url and its 'canonical' url, comma separated",
        )
        parser.add_argument(
            "--sameonly",
            default=False,
            required=False,
            action="store_true",
            help=f"Only show GlossVideo's where url and 'canonical' url match",
        )
        parser.add_argument(
            "--convert",
            default=False,
            required=False,
            action="store_true",
            help=f"Rename the GlossVideo file on Storage, and overwrite the old GlossVideo url with the 'canonical' url, in the database (default dry-run)",
        )
        parser.add_argument(
            "--commit",
            default=False,
            required=False,
            action="store_true",
            help=f"WARNING, DESTRUCTIVE: With '--convert' actually perform the actions rather than just dry-running them",
        )
        parser.add_argument(
            "--s3",
            default=False,
            required=False,
            action="store_true",
            help=f"Just print out the S3 bucket name and return, if S3 is in use",
        )

    def handle(self, *args, **options):

        # If using S3, print the bucket name
        instance = GlossVideo.objects.first()
        if instance:
            storage = instance.videofile.storage
            if isinstance(storage, S3Boto3Storage):
                print(f"S3 Storage: {storage.bucket_name}")
            else:
                print("S3 not in use")
        else:
            print("No GlossVideo instances found, unable to determine custom storage backend.")

        if options["s3"]:
            return

        for gloss in Gloss.objects.all():

            if not options["noid"]:
                print(gloss.id)

            for glossvideo in gloss.glossvideo_set.all():
                storage = glossvideo.videofile.storage
                orig_name = glossvideo.videofile.name
                canon_name = storage.get_valid_name(glossvideo.create_filename())

                same = orig_name == canon_name
                if not options["sameonly"] or (options["sameonly"] and same):
                    print(orig_name, end="")
                    print(f",{canon_name}" if options["compare"] else "")

                if options["convert"]:
                    if same:
                        print(f"NO CHANGE: {orig_name}")
                    else:
                        # Prove the stored item exists
                        if storage.exists(orig_name):
                            print(f"Object exists: {orig_name}")
                        else:
                            print(f"IGNORE: Storage could not find {orig_name}")
                            continue

                        # Move it to the new name, in storage and db
                        if options["commit"]:
                            glossvideo.rename_video()
                            glossvideo.save()
                            pprint(glossvideo.__dict__)
                            print(f"RENAMED: {orig_name} --> {canon_name}")
                        else:
                            print(f"(DRY-RUN) {orig_name} --> {canon_name}")
