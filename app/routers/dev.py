import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.s3 import get_s3_client, presign_get, presign_put

router = APIRouter(prefix="/api/dev", tags=["dev"])

TEST_KEY = "dev/s3-check.txt"
TEST_BODY = b"seans s3 check"


@router.get("/s3-check")
async def s3_check():
    """Roundtrip PUT -> GET -> DELETE against the S3 bucket. Dev only."""
    client = get_s3_client()

    # PUT via presigned URL
    put_url = presign_put(TEST_KEY)
    async with httpx.AsyncClient() as http:
        resp = await http.put(put_url, content=TEST_BODY)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=500, detail=f"PUT failed: {resp.status_code}"
            )

    # GET via presigned URL
    get_url = presign_get(TEST_KEY)
    async with httpx.AsyncClient() as http:
        resp = await http.get(get_url)
        if resp.status_code != 200 or resp.content != TEST_BODY:
            raise HTTPException(status_code=500, detail="GET roundtrip failed")

    # Cleanup
    client.delete_object(Bucket=settings.S3_BUCKET, Key=TEST_KEY)

    return {"ok": True}
