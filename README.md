# AWS Automated File Processing System

A small serverless project where CSV files dropped into an S3 bucket get checked automatically by a Lambda function and sorted into a `processed/` or `rejected/` folder. Nobody has to open each file and squint at it.

I built this to get proper hands-on experience with AWS. I'd read about S3, Lambda and IAM plenty of times, but I wanted to see how they actually fit together, and, as it turned out, how they fall apart when you get one setting slightly wrong.

!\[Architecture](screenshots/s3-bucket.png)

\---

## What it does

Imagine a company that receives CSV files of employee details. Instead of someone checking each one by hand:

1. A file is uploaded to the `uploads/` folder in S3.
2. S3 notices and triggers a Lambda function.
3. The Lambda (written in Python) checks the file.
4. If the file is fine, it's copied to `processed/`.
5. If it isn't, it's copied to `rejected/`, and the reasons are logged.
6. CloudWatch keeps a record of everything that happened.

```
upload → uploads/ → S3 event → Lambda validates the file
                                   ├── valid   → processed/
                                   └── invalid → rejected/
                                   (everything logged in CloudWatch)
```

The original file stays in `uploads/`. That's deliberate, because when something gets rejected I want the original there to look at.

\---

## AWS services used

|Service|What I used it for|
|-|-|
|Amazon S3|Storing uploaded, processed and rejected files|
|AWS Lambda|Running the Python validation code whenever a file arrives|
|AWS IAM|Giving the Lambda only the access it needs, and nothing more|
|Amazon CloudWatch|Logging every run, and working out what went wrong|

Everything runs in **Europe (London) `eu-west-2`**. I kept it deliberately simple: no EC2, no databases, no API Gateway.

\---

## What counts as a valid file

A valid file looks like this:

csv
name,email,department
John Smith,john@example.com,IT
Sarah Jones,sarah@example.com,HR
David Brown,david@example.com,Finance



The Lambda rejects a file if:

* it doesn't end in `.csv`
* it's bigger than 1 MB (checked with `head\\\_object()` before downloading, so big files don't waste time or money)
* it isn't UTF-8 encoded
* it's missing any of the `name`, `email` or `department` columns
* any row has an empty required field
* any email isn't in a basic valid format (it's a simple check, not a full email validator)

\---

## Testing

I tested it with one good file and four deliberately bad ones. Watching the bad ones get rejected for the right reasons was oddly satisfying.

|Test file|What's wrong with it|Result|
|-|-|-|
|`valid-employees.csv`|Nothing|Processed|
|`missing-column.csv`|No `department` column|Rejected|
|`invalid-email.csv`|An email with no `@`|Rejected|
|`employees.txt`|Not a CSV|Rejected|
|`large-file.csv`|Over 1 MB|Rejected|



!\[Processed file](screenshots/successful-upload.png)
!\[Rejected files](screenshots/rejected-upload.png)
!\[CloudWatch logs](screenshots/cloudwatch-logs.png)



## Things that went wrong (and what they taught me)

The full story is in [documentation/troubleshooting.md](documentation/troubleshooting.md), but here are the highlights.

**The capital U.** For a long time, files went into `uploads/` and then nothing happened. No error, no logs, nothing. I checked IAM permissions, regions, roles and my code. The actual problem was that my S3 event notification prefix was `Uploads/` instead of `uploads/`. S3 is case-sensitive, so it was waiting for files in a folder that didn't exist. One letter, a couple of hours. Lesson learned.

**"Log group does not exist."** This looked like another problem, but it was really the clue I needed. No log group means the Lambda has never run at all, so the issue was the trigger, not the code or the permissions.

**Two bucket names.** At one point different parts of my setup pointed at two different buckets: mine and the example name from the tutorial. Now I copy and paste resource names instead of typing them.

**The CSV that looked fine.** Some sample data I pasted into a spreadsheet ended up all in the first column. It looked like a CSV, but it only had one column, so the Lambda (correctly) rejected it.

**The ListBucket warning.** The Lambda console warned that the role couldn't call `ListBucket`. I assumed this was my big problem. It wasn't, but it did teach me the difference between bucket-level and object-level permissions.

\---

## What I learned

* How S3 event notifications trigger Lambda, and that the trigger needs both the notification on the bucket *and* a permission on the function.
* How to write a least-privilege IAM policy, so the Lambda can read only from `uploads/` and write only to `processed/` and `rejected/`.
* How to use boto3 to read, inspect and copy files in S3.
* That CloudWatch is the first place to look, and that *no* logs tells you something too.
* That AWS is very literal. Names, regions and capital letters all have to match exactly.

\---

## What I'd improve next

If this were going into production, I'd look at:

* **Duplicate events:** S3 can deliver the same event more than once, so I'd make processing idempotent.
* **SQS and a dead-letter queue:** to queue incoming files and catch failed runs instead of losing them.
* **DynamoDB:** to keep a record of every file and its result.
* **Alerts:** an SNS notification when a file is rejected.
* **Terraform:** to build the whole setup from code rather than clicking through the console.
* **Automated tests:** for the validation logic.

\---

## Repository layout



aws-automated-file-processing/
├── README.md
├── lambda/
│   └── lambda\_function.py      # the validation code
├── iam/
│   └── s3-policy.json          # the Lambda's S3 permissions
├── test-files/                 # the files I tested with
├── screenshots/                # evidence from the AWS console
└── documentation/
└── troubleshooting.md      # everything that went wrong, in detail



All the data in this project is made up. There are no credentials, keys or real employee details anywhere in this repository.

\---

## Final thoughts

This was one of my first proper AWS projects. The building part was fairly quick; the debugging took far longer and taught me far more. If I had to sum it up: AWS will do exactly what you tell it, so you'd better tell it exactly the right thing.

**Built with:** AWS S3 · Lambda · IAM · CloudWatch · Python · Boto3

