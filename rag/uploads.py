"""Helpers for user-uploaded documents."""
import os
import re

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt"}


def safe_upload_name(name):
    """Strip directories and any characters outside [A-Za-z0-9_.-]."""
    base = os.path.basename(name.replace("\\", "/"))
    return re.sub(r"[^A-Za-z0-9_.-]", "_", base).lstrip(".")
