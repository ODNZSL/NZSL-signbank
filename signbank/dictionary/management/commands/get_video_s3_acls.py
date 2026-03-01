#!/usr/bin/env -S python3 -u
# Bang line above passes '-u' to python, for unbuffered output
# Permissions required:
#  psql - access to heroku app's postgres
#  aws s3 - NZSL IAM access
#  s3:GetObjectAcl permissions or READ_ACP access to the object
#  https://docs.aws.amazon.com/cli/latest/reference/s3api/get-object-acl.html

from django.core.management.base import BaseCommand
from signbank.dictionary.management.commands.apis import *


def get_recommended_action(key_in_nzsl, key_in_s3):
    """
    Cases
    In S3     In NZSL     Action
      Is        Is          Update ACL
      Is        Not         Delete S3 Object
      Not       --          Review
    """
    if key_in_s3:
        if key_in_nzsl:
            return "Update ACL"
        else:
            return "Delete S3 Object"
    return "Review"


# Get S3 object's ACL
def get_s3_canned_acl(aws_s3_bucket, video_key):
    acls_grants = S3_CLIENT.get_object_acl(Bucket=aws_s3_bucket, Key=video_key)[
        "Grants"
    ]
    if len(acls_grants) > 1:
        if (
            acls_grants[0]["Permission"] == "FULL_CONTROL"
            and acls_grants[1]["Permission"] == "READ"
        ):
            return "public-read"
    elif acls_grants[0]["Permission"] == "FULL_CONTROL":
        return "private"

    return "unknown"


# Get S3 object's LastModified date/time
def get_s3_lastmodified(aws_s3_bucket, video_key):
    return S3_CLIENT.head_object(Bucket=aws_s3_bucket, Key=video_key)["LastModified"]


def build_csv_header():
    return [
        "Action",
        "S3 Video key",
        "S3 LastModified",
        "S3 Expected Canned ACL",
        "S3 Actual Canned ACL",
        "Sbank Gloss ID",
        "Sbank Video ID",
        "Sbank Gloss public",
        "Sbank Video public",
        "Sbank Gloss",
        "Sbank Gloss created at",
    ]


def build_csv_row(
    aws_s3_bucket,
    video_key,
    key_in_nzsl=False,
    key_in_s3=False,
    gloss_idgloss=None,
    gloss_created_at=None,
    gloss_id=None,
    video_id=None,
    gloss_public=False,
    video_public=False,
):
    # See signbank/video/models.py, line 59, function set_public_acl()
    canned_acl_expected = ""
    if key_in_nzsl:
        canned_acl_expected = "public-read" if video_public else "private"

    lastmodified = ""
    canned_acl = ""
    if key_in_s3:
        lastmodified = get_s3_lastmodified(aws_s3_bucket, video_key)
        canned_acl = get_s3_canned_acl(aws_s3_bucket, video_key)

    action = get_recommended_action(key_in_nzsl, key_in_s3)

    return [
        action,
        f"{filter_fakekey(video_key)}",
        f"{lastmodified}",
        f"{canned_acl_expected}",
        f"{canned_acl}",
        f"{gloss_id}",
        f"{video_id}",
        f"{gloss_public}",
        f"{video_public}",
        f"{gloss_idgloss}",
        f"{gloss_created_at}",
    ]


# From the keys present in NZSL, get all their S3 information
def process_keys(aws_s3_bucket, this_all_keys_dict):
    print(f"Getting detailed S3 data for keys ({aws_s3_bucket}) ...", file=sys.stderr)

    out = csv.writer(
        sys.stdout, delimiter=CSV_DELIMITER, quoting=csv.QUOTE_ALL, escapechar="\\"
    )
    out.writerow(build_csv_header())

    for video_key, dict_row in this_all_keys_dict.items():
        out_row = build_csv_row(aws_s3_bucket, video_key, *dict_row)
        try:
            out.writerow(out_row)
        except csv.Error as e:
            print(e, file=sys.stderr)
            pprint(out_row, stream=sys.stderr)
            out_row[0] = f"Error: csv.Error '{e}'"
            print(", ".join(out_row))
            continue


class Command(BaseCommand):
    help = (
        "Get all S3 bucket video object and recommends actions for them. "
        "You must setup: (1) An AWS auth means, eg. AWS_PROFILE env var. "
        "(2) Postgres access details, eg. DATABASE_URL env var."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--env",
            default="uat",
            required=False,
            help="Environment to run against, eg 'production, 'uat', etc (default: '%(default)s')",
        )
        parser.add_argument(
            "--dumpnzsl",
            default=False,
            required=False,
            action="store_true",
            help=f"Dump raw NZSL database output",
        )
        parser.add_argument(
            "--dumps3",
            default=False,
            required=False,
            action="store_true",
            help=f"Dump raw S3 keys output",
        )

    def handle(self, *args, **options):
        AWS_S3_BUCKET = f"nzsl-signbank-media-{options['env']}"

        print(f"Env:         {options['env']}", file=sys.stderr)
        print(f"S3 bucket:   {AWS_S3_BUCKET}", file=sys.stderr)
        print(f"PGCLI:       {PGCLI}", file=sys.stderr)
        print(f"AWS profile: {os.environ.get('AWS_PROFILE', '')}", file=sys.stderr)

        if options["dumpnzsl"]:
            pprint(get_nzsl_raw_keys_dict())
            exit()

        if options["dumps3"]:
            pprint(get_s3_bucket_raw_keys_list(AWS_S3_BUCKET))
            exit()

        process_keys(
            AWS_S3_BUCKET,
            create_all_keys_dict(
                get_nzsl_raw_keys_dict(), get_s3_bucket_raw_keys_list(AWS_S3_BUCKET)
            ),
        )
