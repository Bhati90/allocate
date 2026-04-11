#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
    
    # Initialize New Relic before anything else
    import newrelic.agent
    newrelic.agent.initialize(
        'C:/Users/bhati/New folder (5)/New/allocate/newrelic.ini'
    )
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()