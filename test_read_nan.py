import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.commercial_department.models import Variation
import sqlite3

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()
c.execute("SELECT id, total_amount FROM variations LIMIT 1")
print(c.fetchone())
