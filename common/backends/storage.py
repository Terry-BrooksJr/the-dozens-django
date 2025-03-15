from django_bunny.storage import BunnyStorage


class StaticStorage(BunnyStorage):
    """
    A subclass of BunnyStorage for handling static file storage.

    This class defines the location as "staticfiles" and default ACL as "public-read".
    """

    location = "staticfiles"
    default_acl = "public-read"
