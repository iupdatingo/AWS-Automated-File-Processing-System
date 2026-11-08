import boto3
import csv
import io
import json
import logging
import re
from urllib.parse import unquote_plus

s3 = boto3.client("s3")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_FILE_SIZE = 1_000_000  # 1 MB

REQUIRED_COLUMNS = ["name", "email", "department"]

# Matches a literal period in the email address.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_csv(bucket, key):
    errors = []

    # 1. Check the file extension.
    if not key.lower().endswith(".csv"):
        return ["Invalid file type. Only CSV files are accepted."]

    # 2. Check the file size before downloading.
    metadata = s3.head_object(Bucket=bucket, Key=key)
    if metadata["ContentLength"] > MAX_FILE_SIZE:
        return ["File is too large. Maximum size is 1 MB."]

    # 3. Download and decode the file.
    content = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ["File encoding is invalid. Please use UTF-8."]

    try:
        reader = csv.reader(io.StringIO(text), strict=True)

        # 4. Check the column headings.
        headers = next(reader, None)
        if not headers:
            return ["CSV file is empty or has no headers."]

        headers = [header.strip().lower() for header in headers]

        if len(headers) != len(set(headers)):
            return ["CSV contains duplicate column names."]

        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            return ["Missing required columns: " + ", ".join(missing)]

        # 5 and 6. Check every data row.
        data_rows = 0
        for row_number, row in enumerate(reader, start=2):
            if not row or all(not value.strip() for value in row):
                continue

            data_rows += 1

            if len(row) != len(headers):
                errors.append(f"Row {row_number}: Incorrect number of columns.")
                continue

            record = {
                column: value.strip()
                for column, value in zip(headers, row)
            }

            for column in REQUIRED_COLUMNS:
                if not record[column]:
                    errors.append(f"Row {row_number}: {column} is empty.")

            email = record["email"]
            if email and not EMAIL_PATTERN.fullmatch(email):
                errors.append(f"Row {row_number}: Invalid email address.")

        if data_rows == 0:
            return ["CSV file has headers but no data rows."]

    except csv.Error as error:
        return [f"CSV parsing error: {error}"]

    return errors


def lambda_handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if not key.startswith("uploads/"):
            logger.warning("Ignoring file outside uploads folder: %s", key)
            continue

        logger.info("Processing file: s3://%s/%s", bucket, key)

        try:
            errors = validate_csv(bucket, key)
            filename = key[len("uploads/"):]

            if errors:
                destination = "rejected/" + filename
                status = "REJECTED"
                logger.warning("File rejected: %s. Reasons: %s", key, errors)
            else:
                destination = "processed/" + filename
                status = "PROCESSED"
                logger.info("File successfully validated: %s", key)

            # Copy the original file into the appropriate prefix.
            s3.copy_object(
                Bucket=bucket,
                Key=destination,
                CopySource={"Bucket": bucket, "Key": key},
            )

            logger.info("File copied to: %s", destination)
            logger.info("Final status: %s", status)

        except Exception:
            logger.exception("Unexpected processing error for file: %s", key)
            raise

    return {
        "statusCode": 200,
        "body": json.dumps("File processing completed"),
    }
