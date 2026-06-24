from .base import *
from .base import env

DEBUG = True

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])
