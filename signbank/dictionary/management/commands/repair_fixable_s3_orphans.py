#!/usr/bin/env -S python3 -u
#
# Given a CSV file containing S3 objects that can be matched back to NZSL entries.
# Updates the database to repair the NZSL entries.
# Essentially repairs one form of import error.
#
# Bang line above passes '-u' to python, for unbuffered output
# Permissions required:
#  psql - access to heroku app's postgres
#  aws s3 - NZSL IAM access
#  s3:GetObjectAcl permissions or READ_ACP access to the object
#  https://docs.aws.amazon.com/cli/latest/reference/s3api/get-object-acl.html

from django.core.management.base import BaseCommand
from signbank.dictionary.models import (
    FieldChoice,
    Gloss,
)
from signbank.video.models import GlossVideo
from django.core.exceptions import ObjectDoesNotExist
from signbank.dictionary.management.commands.apis import *


# Other globals
DO_COMMIT = False
CSV_INPUT_FILENAME = "-"


# Returns a list of dictionaries, one for each CSV row
def read_csv(csv_filename):
    if csv_filename == "-":
        f = sys.stdin.read().splitlines()
    else:
        f = open(csv_filename, "r")
    return csv.DictReader(f)


def process_csv():
    main_video_type = FieldChoice.objects.filter(
        field="video_type", english_name="main"
    ).first()

    csv_rows = read_csv(CSV_INPUT_FILENAME)

    out = csv.writer(
        sys.stdout, delimiter=CSV_DELIMITER, quoting=csv.QUOTE_ALL, escapechar="/"
    )

    for csv_row in csv_rows:
        gloss_id = csv_row[GLOSS_ID_COLUMN]
        gloss_idgloss = csv_row[GLOSS_COLUMN]
        video_key = csv_row[GLOSS_VIDEO_COLUMN]
        out.writerow([gloss_id, gloss_idgloss, video_key])
        gloss_id = int(gloss_id)

        try:
            gloss = Gloss.objects.get(id=gloss_id)
        except ObjectDoesNotExist as e:
            print(e)
            continue

        try:
            GlossVideo.objects.get(videofile=video_key)
            print(f"Ignoring: GlossVideo already exists: {video_key}")
            continue
        except ObjectDoesNotExist:
            pass

        gloss_video = GlossVideo(
            gloss=gloss,
            dataset=gloss.dataset,
            videofile=video_key,
            title=video_key,
            version=0,
            is_public=False,
            video_type=main_video_type,
        )
        print(gloss)
        print(gloss_video)

        if not DO_COMMIT:
            print("Dry run, no changes (use --commit flag to make changes)")
            continue

        # At this point we complete the repair
        # We use bulk_create() because we cannot allow save() to run
        if len(GlossVideo.objects.bulk_create([gloss_video])) < 1:
            print(f"Error: could not create {gloss_video}")


class Command(BaseCommand):
    help = (
        f"Given a CSV file containing S3 objects that can be matched back to NZSL entries: "
        f"Update the database to repair the NZSL entries. "
        f"CSV Column headings {GLOBAL_COLUMN_HEADINGS}. "
        f"You must have setup: An AWS auth means, eg. AWS_PROFILE env var. "
        f"Postgres access details, eg. DATABASE_URL env var."
    )

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument(
            "csv_filename", help="Name of CSV input file, or '-' for STDIN"
        )

        # Optional arguments
        parser.add_argument(
            "--commit",
            default=DO_COMMIT,
            required=False,
            action="store_true",
            help=f"Actually make changes, instead of just outputting what would happen (default)",
        )

    def handle(self, *args, **options):
        global CSV_INPUT_FILENAME, DO_COMMIT
        CSV_INPUT_FILENAME = options["csv_filename"]
        DO_COMMIT = options["commit"]

        print(f"Input file:  {options['csv_filename']}", file=sys.stderr)
        print(f"Mode:        {'Commit' if DO_COMMIT else 'Dry-run'}", file=sys.stderr)

        process_csv()
