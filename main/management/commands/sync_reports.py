# pickuplog/main/management/commands/sync_reports.py (최종 수정)

from django.core.management.base import BaseCommand
# 💡 수정: calculate_rain_impact_index 함수 임포트를 제거합니다.
# from main.reports import calculate_rain_impact_index 

class Command(BaseCommand):
    """
    RidershipDaily, WeatherDaily, LostItem 데이터를 기반으로 
    Rain Impact Index (RII) 및 기타 종합 분석 지표를 계산하여 
    RainImpactReport 테이블을 업데이트합니다.
    """
    
    help = 'Calculates RII and generates the RainImpactReport.'

    def handle(self, *args, **options):
        # 💡 수정: 함수 호출 시점에 모듈을 로드합니다.
        # 이렇게 하면 Django가 settings 및 URL을 로드하는 과정에서 reports.py를 강제로 로드하지 않습니다.
        try:
            from main.reports import calculate_rain_impact_index
        except ImportError:
            self.stdout.write(self.style.ERROR('❌ ERROR: main.reports 모듈 로드에 실패했습니다. (순환 참조 문제 재확인 필요)'))
            return
            
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
            # 💡 수정: 최종 오류 시에만 raise하여 스택 트레이스를 유지하고, CommandError로 변환하여 깔끔하게 종료합니다.
            self.stdout.write(self.style.ERROR(
                f'❌ 보고서 생성 중 치명적인 오류 발생: {e}'
            ))
            raise CommandError(f"보고서 생성 실패: {e}")
        