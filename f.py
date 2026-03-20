import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT setval('job_activities_id_seq', (SELECT MAX(id) FROM job_activities) + 1)")
    print('✅ job_activities sequence fixed')
    
    cursor.execute("SELECT setval('allocations_id_seq', (SELECT MAX(id) FROM allocations) + 1)")
    print('✅ allocations sequence fixed')
    
    # Jobs uses string primary key so no sequence needed
    print('✅ Done')