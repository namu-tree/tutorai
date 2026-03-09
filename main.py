from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="A2A Math Item Generator", version="0.1.0")
app.include_router(router)

@app.get("/")
def root():
    return {"message": "Server is running"}