from flask import Flask
from data_pipeline import run_pipeline

app = Flask(__name__)

@app.route("/run-pipeline", methods=["GET"])
def start_pipeline():

    run_pipeline()

    return {
        "status": "success",
        "message": "Data pipeline executed successfully"
    }


if __name__ == "__main__":
    app.run(debug=True)

    