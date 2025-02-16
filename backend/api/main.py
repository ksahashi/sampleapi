from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from routers import test
from starlette.status import HTTP_403_FORBIDDEN
from util import util

correct_key: str = util.get_apikey()
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def get_api_key(
    api_key_header: str = Security(api_key_header),
):
    if api_key_header == correct_key:
        return api_key_header
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )


app = FastAPI()
app.include_router(test.router, dependencies=[Depends(get_api_key)], tags=["Test"])


@app.get("/")
async def root():
    return {"status": "ok"}
