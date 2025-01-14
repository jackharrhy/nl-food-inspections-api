from fastapi import FastAPI

app = FastAPI()

BASE_URL = "https://www.gov.nl.ca/dgsnl/inspections/public-alpha/"


@app.get("/")
async def root():
    return {"message": "Hello World!"}
