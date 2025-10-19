# pickuplog/main/management/commands/sync_reports.py

from django.core.management.base import BaseCommand
# 이 임포트가 main/reports.py의 함수를 가져옵니다.
from main.reports import calculate_rain_impact_index 

class Command(BaseCommand):
    help = 'RidershipDaily 데이터를 기반으로 RainImpactReport를 계산하고 적재합니다.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('비 영향 지수(RII) 분석 시작...'))
        
        # 분석 로직 실행
        num_reports = calculate_rain_impact_index()
        
        if num_reports > 0:
            self.stdout.write(self.style.SUCCESS(f'✅ 분석 완료! {num_reports}개의 RainImpactReport가 생성/업데이트되었습니다.'))
        else:
            self.stdout.write(self.style.WARNING('경고: RidershipDaily 데이터가 부족하거나 계산 중 오류가 발생하여 보고서가 생성되지 않았습니다.'))