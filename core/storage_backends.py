from django_bunny.storage import BunnyStorage
from storages.backends.s3boto3 import S3Boto3Storage



class StaticStorage(S3Boto3Storage):
    """
    A subclass of S3Boto3Storage for handling static file storage.

    This class defines the location as "static" and default ACL as "public-read".
    """
    location = "static"
    default_acl = "public-read"


class MediaStorage(S3Boto3Storage):
    """
    A subclass of S3Boto3Storage for handling media file storage.

    This class defines the location as "media", disables file overwriting,
    and sets the default ACL as "public-read".
    """
    location = "media"
    file_overwrite = False
    default_acl = "public-read"
