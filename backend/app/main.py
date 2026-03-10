from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

import app.utils.env as env

@app.get("/env-check")
def env_check():
    return {
        "database": env.DATABASE_URL is not None,
        "openai": env.OPENAI_API_KEY is not None
    }


from app.db.postgres import test_connection

@app.get("/db-test")
def db_test():
    return {"db_result": test_connection()}
