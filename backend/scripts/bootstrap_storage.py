"""Creates the S3/MinIO bucket if it doesn't exist yet. Run once after
`docker compose up` on a fresh environment."""
from app.services.storage.s3 import get_storage_client

if __name__ == "__main__":
    client = get_storage_client()
    client.ensure_bucket()
    print("Storage bucket ready.")
