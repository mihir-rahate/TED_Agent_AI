from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class SearchQuery(BaseModel):
    query: str

@app.get("/")
async def root():
    return {"message": "API is working!"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/search")
async def search_talks(search_query: SearchQuery):
    # Simple mock response to test if endpoint works
    return {
        "results": [
            {"title": "Test Talk 1", "speaker": "Test Speaker 1"},
            {"title": "Test Talk 2", "speaker": "Test Speaker 2"}
        ],
        "query": search_query.query
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)