# pickuplog/main/management/commands/sync_reports.py

from django.core.management.base import BaseCommand
from main.reports import calculate_rain_impact_index # << 수정된 reports.py 함수 임포트

class Command(BaseCommand):
    """
    RidershipDaily, WeatherDaily, LostItem 데이터를 기반으로 
    Rain Impact Index (RII) 및 기타 종합 분석 지표를 계산하여 
    RainImpactReport 테이블을 업데이트합니다.
    """
    
    help = 'Calculates RII and generates the RainImpactReport.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=== PickUpLog: 종합 분실 분석 시작 (sync_reports) ==='))

        try:
            # reports.py에 정의된 핵심 분석 함수 호출
            updated_count = calculate_rain_impact_index()
            
            if updated_count > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ 성공적으로 RainImpactReport 테이블을 업데이트했습니다. ({updated_count}개 보고서 생성)'
                ))
            else:
                 self.stdout.write(self.style.WARNING(
                    '⚠️ 경고: 분석 로직이 실행되었으나, 업데이트된 보고서가 없습니다. (데이터 부족 또는 로직 문제)'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'❌ 보고서 생성 중 오류 발생: {e}'
            ))
            raise e # 오류 발생 시 디버깅을 위해 재발생