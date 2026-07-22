"""Quick test to verify core imports work."""
import sklearn
import reportlab
import streamlit
import pandas
import matplotlib
import seaborn
import requests
import boto3

from utils.app_logging import configure_logging
from utils.s3_storage import s3_enabled, s3_status

configure_logging()
assert s3_enabled() is False
assert s3_status()["enabled"] is False
assert boto3.__version__

print("All imports OK")
