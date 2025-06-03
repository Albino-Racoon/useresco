import uvicorn

if __name__ == "__main__":
    # Simulira Render start command:
    # uvicorn main.api:app --host 0.0.0.0 --port 10000
    uvicorn.run("main.api:app", host="0.0.0.0", port=10000, reload=True, log_level="info")