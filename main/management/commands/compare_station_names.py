# main/management/commands/standardize_lostitem_stations.py

from django.core.management.base import BaseCommand
from main.models import LostItem, StationDict
import re

class Command(BaseCommand):
    help = 'LostItem의 역 이름을 표준화하여 기존 station 컬럼에 덮어씌웁니다.'

    def handle(self, *args, **options):
        self.stdout.write('LostItem 역 이름 표준화 시작...')
        
        # StationDict 전체 가져오기
        station_dict = StationDict.objects.all()
        mapping = {}
        for s in station_dict:
            key = re.sub(r'\(.*?\)','', s.station_name_raw).replace('역','').strip().upper()
            mapping[key] = s.station_name_std.strip().upper()
        
        # LostItem 전체 처리
        lost_items = LostItem.objects.filter(transport='subway')
        count_updated = 0
        
        for item in lost_items:
            # 기존 station 표준화
            std_name = re.sub(r'\(.*?\)','', item.station or '').replace('역','').strip().upper()
            
            # StationDict 매칭
            if std_name in mapping:
                item.station = mapping[std_name]  # 기존 컬럼 덮어쓰기
            else:
                item.station = std_name  # 매칭 안 되면 단순 정제명으로 덮어쓰기
            
            item.save()
            count_updated += 1

        self.stdout.write(f'총 {count_updated}개의 LostItem 역 이름이 표준화되어 덮어씌워졌습니다.')
