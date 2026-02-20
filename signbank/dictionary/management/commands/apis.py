# Globals and common methods for NZSL postgres/S3 management commands
import os
import sys
import subprocess
from uuid import uuid4
from pprint import pprint
import boto3
import csv


# Module globals
CSV_DELIMITER = ","
FAKEKEY_PREFIX = "this_is_not_a_key_"
DATABASE_URL = os.getenv("DATABASE_URL", "")
S3_CLIENT = boto3.client("s3")
S3_RESOURCE = boto3.resource("s3")
PGCLI = "/usr/bin/psql"
GLOSS_ID_COLUMN = "Gloss ID"
GLOSS_COLUMN = "Gloss"
GLOSS_PUBLIC_COLUMN = "Gloss public"
GLOSS_VIDEO_COLUMN = "Suggested Video key"
GLOBAL_COLUMN_HEADINGS = [
    GLOSS_ID_COLUMN,
    GLOSS_COLUMN,
    GLOSS_PUBLIC_COLUMN,
    GLOSS_VIDEO_COLUMN,
]


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


# Fake key is a hack to handle FULL JOIN
def maybe_fakekey(instring):
    return instring if instring else FAKEKEY_PREFIX + str(uuid4())


def filter_fakekey(instring):
    return "" if instring.startswith(FAKEKEY_PREFIX) else instring


# Get the video files info from NZSL Signbank postgres
def get_nzsl_raw_keys_dict():
    print(
        f"Getting raw list of video file info from NZSL Signbank postgres database ...",
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

        """
        Hack to handle FULL JOIN.
        We are storing data rows in a dictionary, indexed by video_key.
        Because we are doing a FULL JOIN on the NZSL Signbank database,
        we also get rows where there are gloss entries that do not have
        a corresponding video_glossvideo.
        (These are erroneous and one of the reasons this script exists,
        to find them.)
        Consequently there is no video_key, and we cannot use it to index
        the data row.
        Instead, we create a fake video_key that is unique and, theoretically,
        impossible for anything else to try and use. It also has a 'safe',
        easily filtered prefix, which means later code can easily tell
        a fake key from a real key.
        Always having a key, in this way, means that code, eg. loops,
        that depends on there being a dictionary key axis will not break.
        """
        video_key = maybe_fakekey(video_key.strip())

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


# Get all video keys from AWS S3
def get_s3_bucket_raw_keys_list(aws_s3_bucket):
    print(f"Getting raw AWS S3 keys recursively ({aws_s3_bucket}) ...", file=sys.stderr)

    s3_resource_bucket = S3_RESOURCE.Bucket(aws_s3_bucket)
    this_s3_bucket_raw_keys_list = [
        s3_object.key for s3_object in s3_resource_bucket.objects.all()
    ]

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

    # Find S3 keys that are present or absent in NZSL.
    # For speed we use pop(), so that each pass leaves a smaller subset of the rows.
    # This destroys the NZSL database keys list but we never use it again.
    dict_rows_ok = 0
    dict_rows_no_nzsl = 0
    for video_key in this_s3_bucket_raw_keys_list:
        dict_row = this_nzsl_raw_keys_dict.pop(video_key, None)
        if dict_row:
            this_all_keys_dict[video_key] = [
                True,  # NZSL PRESENT
                True,  # S3 PRESENT
            ] + dict_row
            dict_rows_ok += 1
        else:
            this_all_keys_dict[video_key] = [
                False,  # NZSL Absent
                True,  # S3 PRESENT
            ] + [""] * 6
            dict_rows_no_nzsl += 1

    print(
        f"{dict_rows_ok} OK, both NZSL and S3\n"
        f"{dict_rows_no_nzsl} S3 but no NZSL (S3 orphans)\n"
        f"{len(this_nzsl_raw_keys_dict)} NZSL but no S3",
        file=sys.stderr,
    )

    # NZSL keys that are absent from S3
    for video_key, dict_row in this_nzsl_raw_keys_dict.items():
        this_all_keys_dict[video_key] = [
            True,  # NZSL PRESENT
            False,  # S3 Absent
        ] + dict_row

    # Find keys that are absent from both, oh, wait ...

    return this_all_keys_dict
