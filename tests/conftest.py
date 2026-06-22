import os

# Force mock mode before app settings load during pytest collection.
os.environ["MOCK_MODE"] = "true"
