# Troubleshooting Notes

This is a record of everything that went wrong while I built this project, how I found it and how I fixed it. Some of these took minutes. One of them took an embarrassingly long time and came down to a single capital letter.

I've kept these notes honest, because I think the debugging taught me more about AWS than the parts that worked first time.

\---

## 1\. Files uploaded, then... nothing. Absolutely nothing.

**What happened**

I uploaded my CSV into the `uploads/` folder and sat back waiting for the magic. The file appeared in `uploads/` and stayed there. Nothing in `processed/`, nothing in `rejected/`, no error, no success message. Just silence. In some ways an error would have been nicer, because at least it would have been talking to me.

**What I suspected (in roughly this order)**

* The Lambda's IAM role didn't have the right permissions.
* I'd got the file name wrong somewhere.
* The S3 bucket and the Lambda were in different regions, so they couldn't talk to each other.
* The Lambda wasn't using the role I thought it was using.
* My Python code was broken.

I checked every one of these. Some of them twice. At one point I was convinced AWS had it in for me personally.

**How I investigated it**

* Went to CloudWatch to read the logs and got "Log group does not exist". At first this felt like another problem, but it was actually the biggest clue. If there's no log group at all, the Lambda has never run. So the code and the permissions weren't the issue, because the Lambda wasn't even being woken up.
* Checked the Lambda's resource-based policy. It allowed my bucket to invoke the function, so that side was fine.
* Checked the regions. The bucket and the Lambda were both in London (`eu-west-2`), so that was fine too.
* Finally opened **S3 → Properties → Event notifications** and actually read what I'd typed.

**The cause**

The event notification prefix was `Uploads/` with a capital U. My folder is `uploads/` in lowercase. S3 treats these as two completely different things, so as far as S3 was concerned, nobody had ever uploaded anything to `Uploads/`, and there was no reason to call the Lambda.

**How I fixed it**

Edited the event notification, changed the prefix to `uploads/` (lowercase, with the slash), saved it, and uploaded the file again. It went straight into `processed/`.

**What I learned**

* S3 keys and prefixes are case-sensitive. `Uploads/` and `uploads/` are not the same.
* "No logs at all" and "logs with an error" are very different problems. No logs means the trigger never fired, so look at the trigger first, not the code.
* Read what you actually typed, not what you think you typed.

!\[Fixed event notification](../screenshots/event-notification-fixed.png)

\---

## 2\. Two buckets, one project, zero clarity

**What happened**

At one point I had two bucket names floating around: `my-aws-file-processing-lab26` and `my-aws-file-processing-lab-2026` (the example name from the tutorial). Different parts of my setup were pointing at different ones. The Lambda trigger's resource policy named one bucket and my IAM policy named the other.

I'd also initially pasted the IAM policy with the placeholder `YOUR-BUCKET-NAME` still in it, which is about as useful as addressing a letter to "Some Person, Somewhere".

**How I fixed it**

Picked one bucket and made sure the same name appeared in all four places that need it:

1. The bucket I actually upload files to
2. The S3 event notification
3. The IAM policy on the Lambda's execution role
4. The Lambda's resource-based policy (which AWS creates when you add the trigger)

**What I learned**

Copy and paste names. Don't retype them. And if a tutorial gives you an example name, it's an example, not a suggestion.

\---

## 3\. "The function execution role does not have permissions to call ListBucket on S3"

**What happened**

The Lambda console showed this warning, and I assumed it was the reason my files weren't processing.

**The cause**

It wasn't the cause. It's a console warning that appears because my policy only grants `GetObject` and `PutObject` on specific folders, not `ListBucket` on the bucket itself. My code never lists the bucket, so the function works without it.

**How I fixed it**

I added `s3:ListBucket` on the bucket ARN (`arn:aws:s3:::my-aws-file-processing-lab26`, with no `/\\\*` on the end) to make the warning go away. Note to self: `ListBucket` applies to the bucket, while `GetObject` and `PutObject` apply to the objects inside it, which is why the ARNs look different.

**What I learned**

Not every warning is the problem. This one was a red herring, but it did make me actually understand the difference between bucket-level and object-level permissions.

\---

## 4\. My valid CSV kept getting rejected

**What happened**

I generated some sample employee data and pasted it into a CSV file. It looked fine to me. The Lambda disagreed and kept rejecting it for missing columns.

**The cause**

When I pasted the data into the spreadsheet, every line landed in the first column. So instead of three columns (`name`, `email`, `department`), each row was one long cell containing the whole line. When it was saved, the CSV effectively had one column with commas inside it, and the Lambda (correctly) said `department` was missing. And `email`. And everything else.

**How I fixed it**

Recreated the file properly so each field sat in its own column. The easiest way is to write the CSV in a plain text editor (Notepad or VS Code), or in a spreadsheet use **Data → Text to Columns** with a comma separator before saving.

**What I learned**

A CSV can look perfect in a spreadsheet and still be wrong underneath. If in doubt, open it in a text editor and check what's actually there.

\---

## 5\. Testing the rejections (the deliberate failures)

These were meant to fail, and I was weirdly pleased every time one did.

|Test file|What was wrong|Result|Reason in CloudWatch|
|-|-|-|-|
|`valid-employees.csv`|Nothing|Processed|Final status: PROCESSED|
|`missing-column.csv`|No `department` column|Rejected|Missing required columns: department|
|`invalid-email.csv`|Email with no `@`|Rejected|Row 2: Invalid email address.|
|`employees.txt`|Not a CSV|Rejected|Invalid file type. Only CSV files are accepted.|
|`large-file.csv`|Over 1 MB|Rejected|File is too large. Maximum size is 1 MB.|

A couple of notes:

* The file type check only looks at the extension. A `.txt` file renamed to `.csv` would get past that check (though it would probably fail the column check). In a real system I'd inspect the contents too.
* The size check uses `head\\\_object()`, so the Lambda rejects big files without downloading them first. That keeps it fast and cheap.

!\[Rejected files](../screenshots/rejected-upload.png)
!\[Processed file](../screenshots/successful-upload.png)

\---

## Quick reference: symptom → where to look

|What I saw|Where to look first|
|-|-|
|File sits in `uploads/`, nothing else happens, no logs|S3 event notification (prefix, case, bucket)|
|"Log group does not exist" in CloudWatch|The Lambda hasn't run, so check the trigger. Also check the console region.|
|`AccessDenied` in the logs|IAM policy on the execution role, and bucket name in every ARN|
|File rejected for missing columns when it looks fine|Open the CSV in a text editor and check the commas|
|ListBucket warning in the console|Usually harmless. Add `s3:ListBucket` on the bucket ARN if you want it gone.|

## If I did it again

I'd check the event notification first, before touching IAM, regions or code. Most of my "permission problem" was actually a typo, and the fastest clue was the one I nearly ignored: no logs at all means the Lambda never ran.

