#!/usr/bin/env -S python3 -u
#
# Finds orphaned S3 objects that can be matched back to NZSL entries that are missing S3 objects.
# Essentially finds one form of import error.
#
# Bang line above passes '-u' to python, for unbuffered output
# Permissions required:
#  psql - access to heroku app's postgres
#  aws s3 - NZSL IAM access
#  s3:GetObjectAcl permissions or READ_ACP access to the object
#  https://docs.aws.amazon.com/cli/latest/reference/s3api/get-object-acl.html

from django.core.management.base import BaseCommand
from signbank.dictionary.models import Gloss
from signbank.dictionary.management.commands.apis import *


def find_orphans(aws_s3_bucket):
    all_keys_dict = create_all_keys_dict(
        get_nzsl_raw_keys_dict(), get_s3_bucket_raw_keys_list(aws_s3_bucket)
    )
    print("Finding fixable S3 orphans", file=sys.stderr)

    out = csv.writer(
        sys.stdout, delimiter=CSV_DELIMITER, quoting=csv.QUOTE_ALL, escapechar="/"
    )
    out.writerow(GLOBAL_COLUMN_HEADINGS)

    # Traverse all the NZSL Signbank glosses that are missing S3 objects
    for video_key, [
        key_in_nzsl,
        key_in_s3,
        gloss_idgloss,
        gloss_created_at,
        gloss_id,
        video_id,
        gloss_public,
        video_public,
    ] in all_keys_dict.items():

        if not key_in_nzsl:
            # This is an S3 object, not a Signbank record
            continue

        if key_in_s3:
            # This Signbank record already has an S3 object, all is well
            continue

        # The gloss_id is the only reliable retrieval key at the Signbank end
        gloss = Gloss.objects.get(id=gloss_id)
        gloss_name = gloss.idgloss.split(":")[0].strip()

        # Skip any that already have a video path
        # These should have an S3 object but don't: For some reason the video never made it to S3
        # These will have to have their videos reinstated (separate operation)
        if gloss.glossvideo_set.exists():
            continue

        # We try to find the orphaned S3 object, if it exists
        # TODO We could improve on brute-force by installing new libraries eg. rapidfuzz
        for test_key, [key_nzsl_yes, key_s3_yes, *_] in all_keys_dict.items():
            if test_key.startswith(FAKEKEY_PREFIX):
                continue
            if gloss_name in test_key:
                if str(gloss_id) in test_key:
                    if key_nzsl_yes:
                        print(f"Anomaly (in NZSL): {gloss.idgloss}", file=sys.stderr)
                        continue
                    if not key_s3_yes:
                        print(f"Anomaly (not in S3): {gloss.idgloss}", file=sys.stderr)
                        continue
                    out.writerow([gloss_id, gloss.idgloss, str(gloss_public), test_key])


class Command(BaseCommand):
    help = (
        "Find orphaned S3 objects that can be matched back to NZSL entries that are missing S3 objects. "
        "You must setup: An AWS auth means, eg. AWS_PROFILE env var. "
        "Postgres access details, eg. DATABASE_URL env var."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--env",
            default="uat",
            required=False,
            help="Environment to run against, eg 'production, 'uat', etc (default: '%(default)s')",
        )

    def handle(self, *args, **options):
        global PGCLI, AWS_S3_BUCKET
        PGCLI = options["pgcli"]
        AWS_S3_BUCKET = f"nzsl-signbank-media-{options['env']}"

        print(f"Env:         {options['env']}", file=sys.stderr)
        print(f"S3 bucket:   {AWS_S3_BUCKET}", file=sys.stderr)
        print(f"PGCLI:       {PGCLI}", file=sys.stderr)
        print(f"AWS profile: {os.environ.get('AWS_PROFILE', '')}", file=sys.stderr)

        find_orphans(AWS_S3_BUCKET)
