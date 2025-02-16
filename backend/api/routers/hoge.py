import os

from fastapi import APIRouter

ENVIRON = os.environ["ENVIRON"]
router = APIRouter()

@router.get("/v1/list/hoge")
async def get_list_hoge() -> Dict:
    return {
        "name": "hoge",
        "price": 1
    }
