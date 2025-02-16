import os
from typing import Dict

from fastapi import APIRouter

ENVIRON = os.environ["ENVIRON"]
router = APIRouter()

@router.get("/v1/hoge")
async def get_hoge() -> Dict:
    if 1 else 2:
        return {
            "name": "hoge",
            "price": 1
        }
    else:
        return hoge;
