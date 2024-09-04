#!/usr/bin/env python3
# Permissions required:
#  psql - access to heroku app's postgres
#  aws s3 - NZSL IAM access
#  s3:GetObjectAcl permissions or READ_ACP access to the object
#  https://docs.aws.amazon.com/cli/latest/reference/s3api/get-object-acl.html

import os
import sys
import subprocess
import argparse
import json

parser = argparse.ArgumentParser(
    description="You must setup: An AWS auth means, eg. AWS_PROFILE environment variable. "
    "Postgres access details, eg. DATABASE_URL"
)
parser.add_argument(
    "--mode",
    default="uat",
    required=False,
    help="Mode to run in, eg 'production, 'uat', etc (default: '%(default)s')",
)
parser.add_argument(
    "--cached",
    default=False,
    required=False,
    action="store_true",
    help="Use keys generated on a previous non-cached run (default: %(default)s) "
    "(Don't mix PRODUCTION and STAGING!)",
)
parser.add_argument(
    "--pgclient",
    default="/usr/bin/psql",
    required=False,
    help=f"Postgres client path (default: %(default)s)",
)
parser.add_argument(
    "--awsclient",
    default="/usr/local/bin/aws",
    required=False,
    help=f"AWS client path (default: %(default)s)",
)
args = parser.parse_args()

# Globals
AWSCLIENT = args.awsclient
PGCLIENT = args.pgclient
DATABASE_URL = os.getenv("DATABASE_URL", None)
NEW_ENV = os.environ.copy()
CSV_DELIMITER = ","

# Vars
AWS_S3_BUCKET = f"nzsl-signbank-media-{args.mode}"
nzsl_raw_keys_dict = {}
s3_bucket_raw_keys_list = []
all_keys_dict = {}

# Files
TMPDIR = "/tmp/nzsl"
try:
    os.makedirs(TMPDIR, exist_ok=True)
except OSError as err:
    print(f"Error creating temporary directory: {TMPDIR} {err}", file=sys.stderr)
    exit()
NZSL_POSTGRES_RAW_KEYS_FILE = f"{TMPDIR}/nzsl_postgres_raw_keys.txt"
S3_BUCKET_RAW_KEYS_FILE = f"{TMPDIR}/s3_bucket_raw_keys.txt"
ALL_KEYS_FILE = f"{TMPDIR}/all_keys.csv"


# Truncate files, creating them if necessary
def init_files(files_list):
    for p in files_list:
        f = open(p, "a")
        f.truncate()
        f.close()


# Pull all info from existing file
def get_keys_from_cache_file(cache_file):
    nkeys_present = 0
    nkeys_absent = 0
    this_all_keys_dict = {}
    try:
        with open(cache_file, "r") as f_obj:
            for line in f_obj.readlines():
                (
                    video_key,
                    is_present_str,
                    db_id_str,
                    gloss_id_str,
                    is_public_str,
                ) = line.strip().split(CSV_DELIMITER)

                is_present = is_present_str.strip().lower() == "true"
                if is_present:
                    nkeys_present += 1
                    db_id = int(db_id_str)
                    # Some don't have gloss_id's
                    try:
                        gloss_id = int(gloss_id_str)
                    except ValueError:
                        gloss_id = None
                    is_public = is_public_str.strip().lower() == "true"
                else:
                    nkeys_absent += 1
                    db_id = None
                    gloss_id = None
                    is_public = None

                this_all_keys_dict[video_key] = [is_present, db_id, gloss_id, is_public]

        print(f"PRESENT: {nkeys_present} keys", file=sys.stderr)
        print(f"ABSENT:  {nkeys_absent} keys", file=sys.stderr)

        return this_all_keys_dict

    except FileNotFoundError:
        print(f"File not found: {cache_file}", file=sys.stderr)
        exit()


# Get all keys from AWS S3
def get_s3_bucket_raw_keys_list(s3_bucket, keys_file):
    print(f"Getting raw AWS S3 keys recursively ({s3_bucket}) ...", file=sys.stderr)
    with open(keys_file, "w") as f_obj:
        subprocess.run(
            [AWSCLIENT, "s3", "ls", f"s3://{s3_bucket}", "--recursive"],
            env=NEW_ENV,
            shell=False,
            check=True,
            text=True,
            stdout=f_obj,
        )

    # Separate out just the key (also strip newline) from date, time, size, key
    # Put the keys in an in-memory list
    with open(keys_file, "r") as f_obj:
        this_s3_bucket_raw_keys_list = [line.split()[3] for line in f_obj]
    print(
        f"{len(this_s3_bucket_raw_keys_list)} rows retrieved: {keys_file}",
        file=sys.stderr,
    )

    # Write the keys back to the file, for cleanliness
    with open(keys_file, "w") as f_obj:
        for line in this_s3_bucket_raw_keys_list:
            f_obj.write(f"{line}\n")

    return this_s3_bucket_raw_keys_list


# Get the video files info from NZSL Signbank
def get_nzsl_raw_keys_dict(keys_file):
    this_nzsl_raw_keys_dict = {}
    print(
        f"Getting raw list of video file info from NZSL Signbank ...",
        file=sys.stderr,
    )
    with open(keys_file, "w") as f_obj:
        subprocess.run(
            [
                PGCLIENT,
                "-t",
                "-c",
                "select id as db_id, gloss_id, is_public, videofile from video_glossvideo",
                f"{DATABASE_URL}",
            ],
            env=NEW_ENV,
            shell=False,
            check=True,
            text=True,
            stdout=f_obj,
        )
    with open(keys_file, "r") as f_obj:
        nzsl_raw_keys_list = f_obj.readlines()
    print(
        f"{len(nzsl_raw_keys_list)} rows retrieved: {keys_file}",
        file=sys.stderr,
    )

    # Separate out the NZSL db columns
    # Write them to a dictionary, so we can do fast operations
    for rawl in nzsl_raw_keys_list:
        rawl = rawl.strip()
        if not rawl:
            continue
        columns = rawl.split("|")
        db_id = columns[0].strip()
        gloss_id = columns[1].strip()
        is_public = columns[2].strip().lower() == "t"
        # 'videofile' data is also the key for S3
        video_key = columns[3].strip()
        # Each dictionary slot contains these values
        this_nzsl_raw_keys_dict[video_key] = [db_id, gloss_id, is_public]

    return this_nzsl_raw_keys_dict


# Get the s3 keys present and absent from our NZSL keys
def create_all_keys_dict(
    this_s3_bucket_raw_keys_list, this_nzsl_raw_keys_dict, all_keys_file
):
    print("Getting S3 keys present and absent from NZSL Signbank ...", file=sys.stderr)
    nkeys_present = 0
    nkeys_absent = 0
    this_all_keys_dict = {}
    for video_key in this_s3_bucket_raw_keys_list:
        if video_key in this_nzsl_raw_keys_dict:
            nkeys_present += 1
            # Add 'Present' column to start
            this_all_keys_dict[video_key] = [True] + this_nzsl_raw_keys_dict[video_key]
        else:
            nkeys_absent += 1
            # Add 'Present' (absent) column to start
            this_all_keys_dict[video_key] = [False, "", "", ""]
    print(f"PRESENT: {nkeys_present} keys", file=sys.stderr)
    print(f"ABSENT:  {nkeys_absent} keys", file=sys.stderr)

    # Write all keys back to a file
    with open(all_keys_file, "w") as f_obj:
        for video_key, item_list in this_all_keys_dict.items():
            outstr = (
                f"{video_key}{CSV_DELIMITER}{CSV_DELIMITER.join(map(str, item_list))}\n"
            )
            f_obj.write(outstr)

    return this_all_keys_dict


# From the keys present in NZSL, get all their ACL information
def output_csv(this_all_keys_dict):
    print(f"Getting ACLs for keys from S3 ({AWS_S3_BUCKET}) ...", file=sys.stderr)

    # CSV header
    csv_header_list = [
        "Video S3 Key",
        "Postgres ID",
        "Gloss ID",
        "Signbank Public",
        "Expected S3 Canned ACL",
        "Actual S3 Canned ACL",
    ]
    print(CSV_DELIMITER.join(csv_header_list))

    for video_key, [
        is_present,
        db_id,
        gloss_id,
        is_public,
    ] in this_all_keys_dict.items():
        canned_acl = ""
        canned_acl_expected = ""
        raw_acl = ""
        if is_present:
            # See signbank/video/models.py, line 59, in function set_public_acl()
            canned_acl_expected = "public-read" if is_public else "private"
            result = subprocess.run(
                [
                    AWSCLIENT,
                    "s3api",
                    "get-object-acl",
                    "--output",
                    "json",
                    "--bucket",
                    AWS_S3_BUCKET,
                    "--key",
                    video_key,
                ],
                env=NEW_ENV,
                shell=False,
                check=True,
                capture_output=True,
                text=True,
            )
            acls_grants_json = json.loads(result.stdout)["Grants"]
            if len(acls_grants_json) > 1:
                if (
                    acls_grants_json[0]["Permission"] == "FULL_CONTROL"
                    and acls_grants_json[1]["Permission"] == "READ"
                ):
                    canned_acl = "public-read"
                else:
                    canned_acl = "Unknown ACL"
            else:
                if acls_grants_json[0]["Permission"] == "FULL_CONTROL":
                    canned_acl = "private"
                else:
                    canned_acl = "Unknown ACL"

        # CSV columns
        print(f"{video_key}", end=CSV_DELIMITER)
        print(f"{db_id if is_present else ''}", end=CSV_DELIMITER)
        print(f"{gloss_id if is_present else ''}", end=CSV_DELIMITER)
        print(f"{is_public if is_present else ''}", end=CSV_DELIMITER)
        print(f"{canned_acl_expected}", end=CSV_DELIMITER)
        print(f"{canned_acl}")


print(f"Mode:        {args.mode}", file=sys.stderr)
print(f"S3 bucket:   {AWS_S3_BUCKET}", file=sys.stderr)
if "AWS_PROFILE" in NEW_ENV:
    print(f"AWS profile: {NEW_ENV['AWS_PROFILE']}", file=sys.stderr)
print(f"AWSCLIENT:   {AWSCLIENT}", file=sys.stderr)
print(f"PGCLIENT:    {PGCLIENT}", file=sys.stderr)
print(f"DATABASE_URL:\n{NEW_ENV['DATABASE_URL']}", file=sys.stderr)

if args.cached:
    print(
        "Using the video keys we recorded on the last non-cached run.", file=sys.stderr
    )
    all_keys_dict = get_keys_from_cache_file(ALL_KEYS_FILE)
else:
    print("Generating keys from scratch.", file=sys.stderr)
    init_files([NZSL_POSTGRES_RAW_KEYS_FILE, S3_BUCKET_RAW_KEYS_FILE, ALL_KEYS_FILE])
    s3_bucket_raw_keys_list = get_s3_bucket_raw_keys_list(
        AWS_S3_BUCKET, S3_BUCKET_RAW_KEYS_FILE
    )
    nzsl_raw_keys_dict = get_nzsl_raw_keys_dict(NZSL_POSTGRES_RAW_KEYS_FILE)
    all_keys_dict = create_all_keys_dict(
        s3_bucket_raw_keys_list, nzsl_raw_keys_dict, ALL_KEYS_FILE
    )

output_csv(all_keys_dict)