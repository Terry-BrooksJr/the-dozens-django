"""
Module: nhhc.backends.storage_backends

This module contains custom classes for S3Boto3Storage, which are used for storing static, public media, and private media files in AWS S3.

Classes:
- StaticStorage: Used for storing static files in AWS S3.
- PublicMediaStorage: Used for storing public media files in AWS S3.
- PrivateMediaStorage: Used for storing private media files in AWS S3.

Attributes:
- location: The location in AWS S3 where the files will be stored.
- file_overwrite: Specifies whether existing files should be overwritten.
- bucket_name: The name of the bucket where the files will be stored.
- default_acl: The default access control list for the files.
- custom_domain: Specifies whether a custom domain is used for accessing the files.

Usage:
To use these custom classes, simply import them and specify the appropriate settings in your Django settings file.

Example:
```python
# settings.py
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

class StaticStorage(S3Boto3Storage):
    location = settings.AWS_STATIC_LOCATION

class PublicMediaStorage(S3Boto3Storage):
    location = settings.AWS_PUBLIC_MEDIA_LOCATION
    file_overwrite = False

class PrivateMediaStorage(S3Boto3Storage):
    location = settings.AWS_PRIVATE_MEDIA_LOCATION
    bucket_name = settings.AWS_PRIVATE_BUCKET_NAME
    default_acl = 'private'
    file_overwrite = False
custom_domain = False
"""

import os

from django.conf import settings
from django_bunny.storage import BunnyStorage


class StaticStorage(BunnyStorage):
    location = "staticfiles"
    default_acl = "public-read"


