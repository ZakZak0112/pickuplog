# main/management/commands/compare_station_names.py

from django.core.management.base import BaseCommand
from main.models import StationDict, LostItem


class Command(BaseCommand):
    help = 'LostItem과 StationDict의 역 이름을 비교합니다.'

    def handle(self, *args, **options):
        self.stdout.write('='*70)
        self.stdout.write('역 이름 비교 분석')
        self.stdout.write('='*70)
        
        # 1. StationDict에 있는 "용산" 관련 역
        self.stdout.write('\n[1] StationDict - 용산')
        yongsan_dict = StationDict.objects.filter(station_name_raw__contains='용산')
        if yongsan_dict.exists():
            for s in yongsan_dict:
                self.stdout.write(f'  RAW: "{s.station_name_raw}" | STD: "{s.station_name_std}" | LINE: {s.line_code}')
        else:
            self.stdout.write('  없음')
        
        # 2. StationDict에 있는 "서울" 관련 역
        self.stdout.write('\n[2] StationDict - 서울')
        seoul_dict = StationDict.objects.filter(station_name_raw__contains='서울')
        if seoul_dict.exists():
            for s in seoul_dict:
                self.stdout.write(f'  RAW: "{s.station_name_raw}" | STD: "{s.station_name_std}" | LINE: {s.line_code}')
        else:
            self.stdout.write('  없음')
        
        # 3. StationDict에 있는 "영등포" 관련 역
        self.stdout.write('\n[3] StationDict - 영등포')
        ydp_dict = StationDict.objects.filter(station_name_raw__contains='영등포')
        if ydp_dict.exists():
            for s in ydp_dict:
                self.stdout.write(f'  RAW: "{s.station_name_raw}" | STD: "{s.station_name_std}" | LINE: {s.line_code}')
        else:
            self.stdout.write('  없음')
        
        # 4. LostItem에 있는 용산역
        self.stdout.write('\n[4] LostItem - 용산역')
        lost_yongsan = LostItem.objects.filter(
            station__contains='용산',
            transport='subway'
        ).values('station').distinct()
        
        if lost_yongsan.exists():
            for item in lost_yongsan:
                self.stdout.write(f'  station: "{item["station"]}"')
        else:
            self.stdout.write('  없음')
        
        # 5. LostItem에 있는 서울역
        self.stdout.write('\n[5] LostItem - 서울역')
        lost_seoul = LostItem.objects.filter(
            station__contains='서울',
            transport='subway'
        ).values('station').distinct()
        
        if lost_seoul.exists():
            for item in lost_seoul:
                self.stdout.write(f'  station: "{item["station"]}"')
        else:
            self.stdout.write('  없음')
        
        # 6. LostItem에 있는 영등포역
        self.stdout.write('\n[6] LostItem - 영등포역')
        lost_ydp = LostItem.objects.filter(
            station__contains='영등포',
            transport='subway'
        ).values('station').distinct()
        
        if lost_ydp.exists():
            for item in lost_ydp:
                self.stdout.write(f'  station: "{item["station"]}"')
        else:
            self.stdout.write('  없음')
        
        # 7. 샘플 10개
        self.stdout.write('\n[7] StationDict 샘플 10개')
        samples = StationDict.objects.all()[:10]
        for s in samples:
            self.stdout.write(f'  "{s.station_name_raw}" / "{s.station_name_std}"')
        
        # 8. LostItem 지하철역 샘플 10개
        self.stdout.write('\n[8] LostItem 지하철역 샘플 10개')
        lost_samples = LostItem.objects.filter(
            transport='subway'
        ).values('station').distinct()[:10]
        
        for item in lost_samples:
            self.stdout.write(f'  "{item["station"]}"')
        
        self.stdout.write('\n' + '='*70)