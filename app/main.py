from fastapi import FastAPI

from app.controller.userController import router as user_router

app = FastAPI(
    title="Statistics of China Agent API",
    version="0.1.0",
)

app.include_router(user_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }
