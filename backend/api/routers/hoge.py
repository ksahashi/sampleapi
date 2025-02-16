import os

from fastapi import APIRouter

ENVIRON = os.environ["ENVIRON"]
router = APIRouter()

@router.get("/v1/hoge")
async def get_hoge() -> Dict:
    return {
        "name": "hoge",
        "price": 1
    }
