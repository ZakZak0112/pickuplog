# main/management/commands/check_lostitem_line.py

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from collections import Counter

from main.models import LostItem, StationDict


class Command(BaseCommand):
    help = 'LostItem의 호선 정보 업데이트 결과를 확인합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detail',
            action='store_true',
            help='상세 결과 출력 (역별 매칭 상태)'
        )
        parser.add_argument(
            '--sample',
            type=int,
            default=10,
            help='샘플 데이터 출력 개수 (기본: 10)'
        )

    def handle(self, *args, **options):
        show_detail = options['detail']
        sample_count = options['sample']
        
        self.stdout.write(self.style.MIGRATE_HEADING('='*70))
        self.stdout.write(self.style.MIGRATE_HEADING('📊 LostItem 호선 정보 업데이트 결과 확인'))
        self.stdout.write(self.style.MIGRATE_HEADING('='*70))
        
        # 1. 전체 통계
        self._show_overall_stats()
        
        # 2. 노선별 분포
        self._show_line_distribution()
        
        # 3. 환승역 통계
        self._show_transfer_stats()
        
        # 4. 샘플 데이터
        self._show_sample_data(sample_count)
        
        # 5. 미매칭 역 분석
        self._show_unmatched_stations()
        
        # 6. 상세 정보 (옵션)
        if show_detail:
            self._show_detailed_info()
        
        self.stdout.write(self.style.SUCCESS('\n✅ 확인 완료!'))

    def _show_overall_stats(self):
        """전체 통계"""
        self.stdout.write(self.style.SUCCESS('\n━━━ 1️⃣ 전체 통계 ━━━'))
        
        # 전체 분실물 중 지하철역 관련
        total_items = LostItem.objects.count()
        subway_items = LostItem.objects.filter(
            station__isnull=False,
            station__icontains='역'
        ).count()
        
        # 호선 정보 유무
        with_line = LostItem.objects.filter(
            station__isnull=False,
            station__icontains='역',
            line__isnull=False
        ).count()
        
        without_line = LostItem.objects.filter(
            station__isnull=False,
            station__icontains='역',
            line__isnull=True
        ).count()
        
        # 비율 계산
        if subway_items > 0:
            completion_rate = (with_line / subway_items) * 100
        else:
            completion_rate = 0
        
        self.stdout.write(f'\n  📦 전체 분실물: {total_items:,}건')
        self.stdout.write(f'  🚇 지하철역 분실물: {subway_items:,}건')
        self.stdout.write(f'  ✅ 호선 정보 O: {with_line:,}건')
        self.stdout.write(f'  ❌ 호선 정보 X: {without_line:,}건')
        self.stdout.write(f'  📈 완성도: {completion_rate:.1f}%')
        
        # 진행 바 표시
        bar_length = 50
        filled = int(bar_length * completion_rate / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        self.stdout.write(f'  [{bar}] {completion_rate:.1f}%')

    def _show_line_distribution(self):
        """노선별 분포"""
        self.stdout.write(self.style.SUCCESS('\n━━━ 2️⃣ 노선별 분포 ━━━'))
        
        # 노선별 카운트 (환승역 고려)
        line_counter = Counter()
        
        items_with_line = LostItem.objects.filter(
            line__isnull=False
        ).values_list('line', flat=True)
        
        for line_str in items_with_line:
            if ',' in line_str:
                # 환승역: 각 노선에 카운트
                for line in line_str.split(','):
                    line_counter[line.strip()] += 1
            else:
                line_counter[line_str] += 1
        
        if line_counter:
            # 상위 15개 노선
            sorted_lines = line_counter.most_common(15)
            
            self.stdout.write(f'\n  {"노선":<12} {"분실물 건수":<12} {"비율":>8}')
            self.stdout.write('  ' + '-' * 35)
            
            total = sum(line_counter.values())
            
            for line, count in sorted_lines:
                percentage = (count / total) * 100
                bar = '▓' * int(percentage / 2)
                self.stdout.write(f'  {line:<12} {count:<12,} {percentage:>6.1f}% {bar}')
        else:
            self.stdout.write('  데이터 없음')

    def _show_transfer_stats(self):
        """환승역 통계"""
        self.stdout.write(self.style.SUCCESS('\n━━━ 3️⃣ 환승역 통계 ━━━'))
        
        # 환승역 (쉼표 포함)
        transfer_items = LostItem.objects.filter(
            line__contains=','
        )
        
        transfer_count = transfer_items.count()
        
        # 단일 노선
        single_items = LostItem.objects.filter(
            line__isnull=False
        ).exclude(line__contains=',')
        
        single_count = single_items.count()
        
        total = transfer_count + single_count
        
        if total > 0:
            transfer_rate = (transfer_count / total) * 100
            single_rate = (single_count / total) * 100
            
            self.stdout.write(f'\n  🔄 환승역 분실물: {transfer_count:,}건 ({transfer_rate:.1f}%)')
            self.stdout.write(f'  🚇 단일노선역 분실물: {single_count:,}건 ({single_rate:.1f}%)')
            
            # 환승역 상위 10개
            if transfer_count > 0:
                self.stdout.write('\n  📍 환승역 TOP 10:')
                
                transfer_stations = transfer_items.values('station', 'line').annotate(
                    count=Count('id')
                ).order_by('-count')[:10]
                
                for idx, item in enumerate(transfer_stations, 1):
                    self.stdout.write(
                        f'     {idx:2d}. {item["station"]:<15} '
                        f'[{item["line"]}] {item["count"]:>3}건'
                    )
        else:
            self.stdout.write('  데이터 없음')

    def _show_sample_data(self, sample_count):
        """샘플 데이터 출력"""
        self.stdout.write(self.style.SUCCESS(f'\n━━━ 4️⃣ 샘플 데이터 (최근 {sample_count}건) ━━━'))
        
        samples = LostItem.objects.filter(
            line__isnull=False
        ).order_by('-registered_at')[:sample_count]
        
        if samples:
            self.stdout.write(f'\n  {"ID":<15} {"역명":<15} {"노선":<20} {"품목":<15} {"등록일"}')
            self.stdout.write('  ' + '-' * 85)
            
            for item in samples:
                item_name = item.item_name[:12] + '...' if len(item.item_name) > 12 else item.item_name
                reg_date = item.registered_at.strftime('%Y-%m-%d') if item.registered_at else 'N/A'
                
                self.stdout.write(
                    f'  {str(item.item_id)[:13]:<15} {item.station[:13]:<15} '
                    f'{item.line[:18]:<20} {item_name:<15} {reg_date}'
                )
        else:
            self.stdout.write('  데이터 없음')

    def _show_unmatched_stations(self):
        """미매칭 역 분석"""
        self.stdout.write(self.style.SUCCESS('\n━━━ 5️⃣ 미매칭 역 분석 ━━━'))
        
        unmatched = LostItem.objects.filter(
            station__isnull=False,
            station__icontains='역',
            line__isnull=True
        )
        
        unmatched_count = unmatched.count()
        
        if unmatched_count > 0:
            self.stdout.write(self.style.WARNING(f'\n  ⚠️  총 {unmatched_count}건의 미매칭 역 존재'))
            
            # 역별 집계
            unmatched_stations = unmatched.values('station').annotate(
                count=Count('id')
            ).order_by('-count')[:20]
            
            self.stdout.write(f'\n  {"역명":<20} {"분실물 건수":<12} {"StationDict 존재여부"}')
            self.stdout.write('  ' + '-' * 50)
            
            for item in unmatched_stations:
                station = item['station']
                count = item['count']
                
                # StationDict에 존재하는지 확인
                in_dict = StationDict.objects.filter(
                    Q(station_name_raw=station) | 
                    Q(station_name_std=station.replace('역', '').strip())
                ).exists()
                
                status = '✓ 존재함' if in_dict else '✗ 없음'
                
                self.stdout.write(f'  {station:<20} {count:<12} {status}')
            
            if unmatched_count > 20:
                self.stdout.write(f'\n  ... 외 {unmatched_count - 20}개 역')
            
            # 해결 방법 제시
            self.stdout.write(self.style.WARNING('\n  💡 해결 방법:'))
            self.stdout.write('     1. StationDict에 없는 역은 sync_ridership.py 실행')
            self.stdout.write('     2. 역 이름이 다른 경우 수동 매핑 필요')
            self.stdout.write('     3. sync_lostitem_line.py를 다시 실행')
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ 모든 역이 매칭되었습니다!'))

    def _show_detailed_info(self):
        """상세 정보 (옵션)"""
        self.stdout.write(self.style.SUCCESS('\n━━━ 6️⃣ 상세 정보 ━━━'))
        
        # StationDict 통계
        total_stations = StationDict.objects.values('station_name_std').distinct().count()
        total_lines = StationDict.objects.values('line_code').distinct().count()
        transfer_stations = StationDict.objects.filter(is_transfer=True).values('station_name_std').distinct().count()
        
        self.stdout.write(f'\n  📚 StationDict 정보:')
        self.stdout.write(f'     - 총 역 수: {total_stations}개')
        self.stdout.write(f'     - 총 노선 수: {total_lines}개')
        self.stdout.write(f'     - 환승역 수: {transfer_stations}개')
        
        # 날짜별 통계
        self.stdout.write(f'\n  📅 날짜별 분실물 (최근 7일):')
        
        from datetime import datetime, timedelta
        
        for i in range(7):
            target_date = datetime.now().date() - timedelta(days=i)
            
            day_count = LostItem.objects.filter(
                registered_at__date=target_date,
                line__isnull=False
            ).count()
            
            if day_count > 0:
                self.stdout.write(f'     - {target_date}: {day_count}건')