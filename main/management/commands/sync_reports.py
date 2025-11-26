# pickuplog/main/management/commands/sync_reports.py (최종 수정: Importlib 사용)

from django.core.management.base import BaseCommand, CommandError
from importlib import import_module # 💡 importlib 추가

class Command(BaseCommand):
    """
    RidershipDaily, WeatherDaily, LostItem 데이터를 기반으로 
    Rain Impact Index (RII) 및 기타 종합 분석 지표를 계산하여 
    RainImpactReport 테이블을 업데이트합니다.
    """
    
    help = 'Calculates RII and generates the RainImpactReport.'

    def handle(self, *args, **options):
        
        # 💡 수정: importlib를 사용하여 모듈 로드 오류를 회피합니다.
        try:
            reports_module = import_module('main.reports')
            calculate_rain_impact_index = reports_module.calculate_rain_impact_index
        except AttributeError:
             # reports.py가 로드되었으나 함수를 찾지 못할 경우
             raise CommandError('❌ ERROR: main.reports 모듈에 "calculate_rain_impact_index" 함수가 정의되지 않았습니다.')
        except ImportError as e:
            # 순환 참조 등으로 인해 모듈 로드가 실패했을 경우
            raise CommandError(f'❌ ERROR: main.reports 모듈 로드 실패 (ImportError): {e}')
            
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
                f'❌ 보고서 생성 중 치명적인 오류 발생: {e}'
            ))
            raise CommandError(f"보고서 생성 실패: {e}")