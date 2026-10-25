from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.controller.authController import router as auth_router
from app.controller.userController import router as user_router
from app.schema.responseDTO import ApiResponse
from app.security.deps import get_current_user

app = FastAPI(
    title="Statistics of China Agent API",
    version="0.1.0",
    dependencies=[Depends(get_current_user)],
)

app.include_router(user_router)
app.include_router(auth_router)


@app.get("/health")
def health():
    return ApiResponse.ok({"status": "ok"})


# 业务代码抛出的 HTTPException 统一为 ApiResponse 结构；
# 框架层异常（未匹配路径的 404、405、请求参数校验 422 等）保持 FastAPI 默认格式
# @app.exception_handler(HTTPException)
# async def http_exception_handler(
#     request: Request,
#     exc: HTTPException,
# ) -> JSONResponse:
#     return JSONResponse(
#         status_code=exc.status_code,
#         content=ApiResponse.error(exc.status_code, str(exc.detail)).model_dump(),
#         headers=exc.headers,
#     )
