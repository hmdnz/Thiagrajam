import os
import boto3
from dotenv import load_dotenv

load_dotenv()

# Load variables from .env
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")


s3 = boto3.client(
    "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
)

try:
    s3.upload_file(
        "hello.txt",               # Local file
        os.getenv("AWS_S3_BUCKET"), # Bucket name
        "uploads/hello.txt"         # Location inside S3
    )

    print("✅ File uploaded successfully!")

except Exception as e:
    print("❌ Upload failed:")
    print(e)