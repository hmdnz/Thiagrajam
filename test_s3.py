import os
import boto3
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")


# Create S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)


try:
    # List files inside the bucket
    response = s3.list_objects_v2(
        Bucket=AWS_S3_BUCKET
    )

    print("✅ Successfully connected to S3!")
    print(f"📦 Bucket: {AWS_S3_BUCKET}")

    objects = response.get("Contents", [])

    if not objects:
        print("📂 The bucket is empty.")
    else:
        print("\nFiles in bucket:")

        for obj in objects:
            print(obj["Key"])

except Exception as e:
    print("❌ Error connecting to S3:")
    print(e)