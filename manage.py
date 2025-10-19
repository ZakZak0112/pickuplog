# manage.py 파일 (최종적으로 수정할 내용)

#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
   
    current_path = os.path.dirname(os.path.abspath(__file__))
    if current_path not in sys.path:
        sys.path.insert(0, current_path)
  
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pickuplog.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
       
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()