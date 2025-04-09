import os
import boto3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch the credentials and region from the environment variables
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION')
bucket_name = os.getenv('AWS_S3_BUCKET_NAME')

# Initialize a session using AWS credentials
s3_client = boto3.client(
    's3',
    region_name=aws_region,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key
)

def upload_file_to_s3(file_content, filname, folder=None):
    """
    Uploads file content (e.g., csv) directly to S3.

    :param file_content: Binary content of the file.
    :param s3_key: Name of the file in S3.
    :param folder: Optional folder name in the S3 bucket (default is None).
    :return: True if upload is successful, False otherwise.
    """
    try:
        # If a folder is specified, prepend it to the key
        s3_key = f"{folder}/{filname}"

        # Upload the binary content to S3
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=file_content)
        print(f"File uploaded successfully to {bucket_name}/{s3_key}")
        return f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{s3_key}"
    except Exception as e:
        print(f"Error uploading binary content: {e}")
        return False
