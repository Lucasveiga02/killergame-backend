from flask import Flask

app = Flask(__name__)

@app.get("/")
def health():
    return "Backend is running"

if __name__ == "__main__":
    app.run()
