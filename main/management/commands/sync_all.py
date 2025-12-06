from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = '모든 sync 커맨드 실행'

    def handle(self, *args, **options):
        call_command('sync_lostitem')
        call_command('sync_weather')
        call_command('sync_ridership')
        call_command('sync_reports')
        call_command('sync_lostitem_line')
        #call_command('compare_station_names') #로딩 오래 걸려서 제외
        call_command('debug_station_matching')