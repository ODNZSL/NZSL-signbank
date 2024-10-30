#!/usr/bin/env -S python3 -u
# Bang line above passes '-u' to python, for unbuffered output
# Permissions required:
#  psql - access to heroku app's postgres
#  aws s3 - NZSL IAM access
#  s3:GetObjectAcl permissions or READ_ACP access to the object
#  https://docs.aws.amazon.com/cli/latest/reference/s3api/get-object-acl.html

import os
import sys
import subprocess
import argparse
import re
from time import sleep
from pprint import pprint
import boto3
import copy
import csv


parser = argparse.ArgumentParser(
    description="You must setup: An AWS auth means, eg. AWS_PROFILE env var. "
    "Postgres access details, eg. DATABASE_URL env var."
)
parser.add_argument(
    "--env",
    default="uat",
    required=False,
    help="Environment to run against, eg 'production, 'uat', etc (default: '%(default)s')",
)
parser.add_argument(
    "--pgcli",
    default="/usr/bin/psql",
    required=False,
    help=f"Postgres client path (default: %(default)s)",
)
parser.add_argument(
    "--awscli",
    default="/usr/local/bin/aws",
    required=False,
    help=f"AWS client path (default: %(default)s)",
)
parser.add_argument(
    "--tests",
    action="store_true",
    default=False,
    required=False,
    help="Run remote tests instead of generating CSV output",
)

args = parser.parse_args()


if args.tests:
    # Magic required to allow this script to use Signbank Django classes
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "signbank.settings.development")
    from django.core.wsgi import get_wsgi_application

    get_wsgi_application()

    from django.contrib.auth.models import Permission
    from django.contrib.auth import get_user_model

    User = get_user_model()

    from signbank.dictionary.models import (
        Dataset,
        FieldChoice,
        Gloss,
        GlossTranslations,
        Language,
        ManualValidationAggregation,
        ShareValidationAggregation,
        ValidationRecord,
    )
    from signbank.video.models import GlossVideo
    from django.test import Client
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse
    from django.db.utils import IntegrityError

# Globals
CSV_DELIMITER = ","
DATABASE_URL = os.getenv("DATABASE_URL", "")
AWSCLI = args.awscli
PGCLI = args.pgcli
AWS_S3_BUCKET = f"nzsl-signbank-media-{args.env}"


def pg_cli(args_list):
    try:
        return subprocess.run(
            [PGCLI, "-c"] + args_list + [f"{DATABASE_URL}"],
            env=os.environ,
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: subprocess.run returned code {e.returncode}", file=sys.stderr)
        print(e.cmd, file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        exit()


def aws_cli(args_list):
    # Try indefinitely
    output = None
    while not output:
        try:
            output = subprocess.run(
                [AWSCLI] + args_list,
                env=os.environ,
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(
                f"Error: subprocess.run returned code {e.returncode}", file=sys.stderr
            )
            print(e.cmd, file=sys.stderr)
            print(e.stdout, file=sys.stderr)
            print(e.stderr, file=sys.stderr)
            sleep(1)
    return output


# Get the video files info from NZSL Signbank
def get_nzsl_raw_keys_dict():
    print(
        f"Getting raw list of video file info from NZSL Signbank ...",
        file=sys.stderr,
    )
    this_nzsl_raw_keys_dict = {}
    # Column renaming is for readability
    # Special delimiter because columns might contain commas
    result = pg_cli(
        [
            "COPY ("
            "SELECT "
            "dg.id AS gloss_id, "
            "dg.idgloss AS gloss_idgloss, "
            "dg.created_at AS gloss_created_at, "
            "dg.published AS gloss_public, "
            "vg.is_public AS video_public, "
            "vg.id AS video_id, "
            "vg.videofile AS video_key "
            "FROM dictionary_gloss AS dg "
            "FULL JOIN video_glossvideo AS vg ON vg.gloss_id = dg.id"
            ") TO STDOUT WITH (FORMAT CSV, DELIMITER '|')",
        ]
    )

    # Separate the NZSL db columns
    # Write them to a dictionary, so we can do fast operations
    for rawl in result.stdout.split("\n"):
        rawl = rawl.strip()
        if not rawl:
            continue
        [
            gloss_id,
            gloss_idgloss,
            gloss_created_at,
            gloss_public,
            video_public,
            video_id,
            video_key,
        ] = rawl.split("|")

        # This sets the initial field ordering in the all_keys dictionary row
        this_nzsl_raw_keys_dict[video_key] = [
            gloss_idgloss.replace(CSV_DELIMITER, ""),
            gloss_created_at,
            gloss_id,
            video_id,
            gloss_public.lower() == "t",
            video_public.lower() == "t",
        ]

    print(
        f"{len(this_nzsl_raw_keys_dict)} rows retrieved",
        file=sys.stderr,
    )

    return this_nzsl_raw_keys_dict


# Get all keys from AWS S3
def get_s3_bucket_raw_keys_list(s3_bucket=AWS_S3_BUCKET):
    print(f"Getting raw AWS S3 keys recursively ({s3_bucket}) ...", file=sys.stderr)
    result = aws_cli(
        [
            "s3",
            "ls",
            f"s3://{s3_bucket}",
            "--recursive",
        ],
    )

    # Separate out just the key from date, time, size, key
    this_s3_bucket_raw_keys_list = []
    for line in result.stdout.split("\n"):
        if line:
            this_s3_bucket_raw_keys_list.append(re.split(r"\s+", line, 3)[3])

    print(
        f"{len(this_s3_bucket_raw_keys_list)} rows retrieved",
        file=sys.stderr,
    )

    return this_s3_bucket_raw_keys_list


# Get the keys present and absent across NZSL Signbank and S3, to dictionary
def create_all_keys_dict(this_nzsl_raw_keys_dict, this_s3_bucket_raw_keys_list):
    print(
        "Getting keys present and absent across NZSL Signbank and S3 ...",
        file=sys.stderr,
    )
    this_all_keys_dict = {}

    # Find S3 keys that are present in NZSL, or absent
    for video_key in this_s3_bucket_raw_keys_list:
        dict_row = this_nzsl_raw_keys_dict.get(video_key, None)
        if dict_row:
            this_all_keys_dict[video_key] = [
                True,  # NZSL PRESENT
                True,  # S3 PRESENT
            ] + dict_row
        else:
            this_all_keys_dict[video_key] = [
                False,  # NZSL Absent
                True,  # S3 PRESENT
            ] + [""] * 6

    # Find NZSL keys that are absent from S3 (present handled above)
    for video_key, dict_row in this_nzsl_raw_keys_dict.items():
        if video_key not in this_s3_bucket_raw_keys_list:
            this_all_keys_dict[video_key] = [
                True,  # NZSL PRESENT
                False,  # S3 Absent
            ] + dict_row

    return this_all_keys_dict


# Cases
# In S3     In NZSL     Action
#   Is        Not         Delete S3 Object
#   Is        Is          Update ACL
#   Not       Is          Review
def get_recommended_action(key_in_nzsl, key_in_s3):
    if key_in_s3:
        if key_in_nzsl:
            return "Update ACL"
        else:
            return "Delete S3 Object"
    return "Review"


# Get S3 object's ACL
def get_s3_canned_acl(video_key):
    result = aws_cli(
        [
            "s3api",
            "get-object-acl",
            "--output",
            "text",
            "--query",
            "Grants[*].Permission",
            "--bucket",
            AWS_S3_BUCKET,
            "--key",
            video_key,
        ]
    )
    acls_grants = result.stdout.strip().split("\t")

    if len(acls_grants) > 1:
        if acls_grants[0] == "FULL_CONTROL" and acls_grants[1] == "READ":
            return "public-read"
    elif acls_grants[0] == "FULL_CONTROL":
        return "private"

    return "unknown"


# Get S3 object's LastModified date/time
def get_s3_lastmodified(video_key):
    result = aws_cli(
        [
            "s3api",
            "head-object",
            "--output",
            "text",
            "--query",
            "LastModified",
            "--bucket",
            AWS_S3_BUCKET,
            "--key",
            video_key,
        ]
    )
    return result.stdout.strip()


def build_csv_header():
    return CSV_DELIMITER.join(
        [
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
    )


def build_csv_row(
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
        lastmodified = get_s3_lastmodified(video_key)
        canned_acl = get_s3_canned_acl(video_key)

    action = get_recommended_action(key_in_nzsl, key_in_s3)

    return CSV_DELIMITER.join(
        [
            action,
            f"{video_key}",
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
    )


# Run some tests against the remote endpoints
# This is a test-harness for now
# Takes advantage of the fact we have a lot of setup infrastructure in this script already
def do_tests():
    # Debugging safety
    if args.env != "dev":
        print("Error: tests must be in 'dev' environment")
        exit()
    if DATABASE_URL.find("@localhost") < 0:
        print("Error: database url must contain '@localhost'")
        exit()
    print(f"DATABASE_URL:{DATABASE_URL}")

    print("Running tests")
    #s3 = boto3.client("s3")
    # pprint(s3.list_objects(Bucket=AWS_S3_BUCKET))
    # get_nzsl_raw_keys_dict()
    # pprint(Gloss.objects.all())

    # This is a cut and paste of the mock tests, but we're doing it "live" on dev
    _csv_content = {
        "id": "111",
        "word": "Test",
        "maori": "maori, maori 2",
        "secondary": "test",
        "notes": "a note",
        "created_at": "2023-09-12 22:37:59 UTC",
        "contributor_email": "ops@ackama.com",
        "contributor_username": "Ackama Ops",
        "agrees": "0",
        "disagrees": "1",
        "topic_names": "Test Topic|Test",
        "videos": "/rails/active_storage/blobs/redirect/eyJfcmFpbHMiOnsibWVzc2FnZSI6IkJBaHBBc2pFIiwiZXhwIjoiMjAyNC0xMS0wM1QyMzoyNzo1Ni4yNDNaIiwicHVyIjoiYmxvYl9pZCJ9fQ==--53448dc4efcf056e7ba7fe6b711d6b1ae551d171/Zimbabwe.mp4",
        "illustrations": "/kiwifruit-2-6422.png",
        "usage_examples": "/fire.1923.finalexample1.mb.r480x360.mp4",
        "sign_comments": ("contribution_limit_test_1: Comment 0|Comment 33"),
    }
    file_name = "test.csv"
    csv_content = [copy.deepcopy(_csv_content)]
    csv_content[0]["id"] = "12345"
    with open(file_name, "w") as file:
        writer = csv.writer(file)
        writer.writerow(csv_content[0].keys())
        for row in csv_content:
            writer.writerow(row.values())
    data = open(file_name, "rb")
    file = SimpleUploadedFile(
        content=data.read(), name=data.name, content_type="content/multipart"
    )
    dataset = Dataset.objects.get(name="NZSL")

    try:
        Gloss.objects.get(idgloss="Share:11").delete()
    except ValueError:
        pass
    Gloss.objects.create(
        dataset=dataset,
        idgloss="Share:11",
        nzsl_share_id="12345",
    )

    # Create user and add permissions
    try:
        user = User.objects.create_user(username="test", email=None, password="test")
        csv_permission = Permission.objects.get(codename='import_csv')
        user.user_permissions.add(csv_permission)
    except IntegrityError:
        user = User.objects.get(username="test")

    # Create client with change_gloss permission.
    client = Client()
    client.force_login(user)
    s = client.session
    s.update({
        "dataset_id": dataset.pk,
        "glosses_new": csv_content
    })
    s.save()
    response = client.post(
        reverse("dictionary:confirm_import_nzsl_share_gloss_csv"),
        {"confirm": True}
    )

    # test to see if we have to wait for thread
    sleep(20)


# From the keys present in NZSL, get all their S3 information
def process_keys(this_all_keys_dict):
    print(f"Getting detailed S3 data for keys ({AWS_S3_BUCKET}) ...", file=sys.stderr)

    print(build_csv_header())

    for video_key, dict_row in this_all_keys_dict.items():
        print(build_csv_row(video_key, *dict_row))


print(f"Env:         {args.env}", file=sys.stderr)
print(f"S3 bucket:   {AWS_S3_BUCKET}", file=sys.stderr)
print(f"AWSCLI:      {AWSCLI}", file=sys.stderr)
print(f"PGCLI:       {PGCLI}", file=sys.stderr)
print(f"AWS profile: {os.environ.get('AWS_PROFILE', '')}", file=sys.stderr)

if args.tests:
    do_tests()
    exit()

process_keys(
    create_all_keys_dict(get_nzsl_raw_keys_dict(), get_s3_bucket_raw_keys_list())
)
