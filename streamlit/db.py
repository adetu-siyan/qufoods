import requests
import pandas as pd

# This is temporary — points at the raw S3 batch directly
# On Day 7 this gets replaced with a real Neon PostgreSQL connection

BATCH_URL = "https://qufoods-raw.s3.amazonaws.com/year=2026/month=06/day=17/batch_BATCH-96bd24c2-7124-4fb5-93e8-f016bd600d67_20260617T154538Z.json"

def get_data():
    response = requests.get(BATCH_URL)
    batch = response.json()
    records = batch["records"]
    df = pd.DataFrame(records)
    return df