# utils.py
from rest_framework import serializers

ALLOWED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg"]

def validate_file_extension(value, allowed_extensions=ALLOWED_IMAGE_EXTENSIONS):
    if value and not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
        raise serializers.ValidationError(f"Only {', '.join(allowed_extensions)} files are allowed.")
    return value
