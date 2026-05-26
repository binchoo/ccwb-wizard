"""ccwb_domain — pure Python domain module for the ccwb web wizard.

This package is shared by the FastAPI backend, the Vite/React frontend (via
the backend's ``/api/scenarios`` endpoint), and any AI agent that wants to
read or write a ccwb Config without booting a UI.

Subsequent units (Domain, Backend, Frontend) will populate this module further.
The Cleanup unit only seeds ``bedrock_models.py`` (Bedrock model matrix).
"""
