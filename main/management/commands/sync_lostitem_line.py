# main/management/commands/sync_lostitem_line.py (지하철역 전용 버전)

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from django.db import transaction
import re

from main.models import LostItem, StationDict


class Command(BaseCommand):
    help = 'LostItem의 station(발견역) 필드를 사용하여 StationDict에서 노선 정보를 찾아 보강합니다. (지하철역만)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--transfer-strategy',
            type=str,
            default='first',
            choices=['first', 'all', 'skip'],
            help='환승역 처리 방법: first(첫번째 노선), all(모든 노선 쉼표구분), skip(환승역 제외)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 업데이트 없이 결과만 미리보기'
        )
        parser.add_argument(
            '--include-all',
            action='store_true',
            help='기차역 포함 모든 역 처리 (기본: 지하철역만)'
        )

    def handle(self, *args, **options):
        transfer_strategy = options['transfer_strategy']
        dry_run = options['dry_run']
        include_all = options['include_all']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN 모드: 실제 업데이트는 수행되지 않습니다.'))
        
        self.stdout.write(self.style.MIGRATE_HEADING('LostItem 노선 정보 보강 시작...'))
        self.stdout.write(f'환승역 처리 전략: {transfer_strategy}')
        
        if include_all:
            self.stdout.write(self.style.WARNING('⚠️  모든 역 처리 모드 (기차역 포함)'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ 지하철역만 처리 모드 (transport="subway")'))
        
        # 1. StationDict의 역 정보를 딕셔너리로 구축
        station_map_raw = {}  # 원본 역명으로 매칭
        station_map_std = {}  # 표준 역명으로 매칭
        
        for sd in StationDict.objects.all():
            # 원본 역명 매핑
            if sd.station_name_raw not in station_map_raw:
                station_map_raw[sd.station_name_raw] = []
            station_map_raw[sd.station_name_raw].append(sd)
            
            # 표준 역명 매핑
            if sd.station_name_std not in station_map_std:
                station_map_std[sd.station_name_std] = []
            station_map_std[sd.station_name_std].append(sd)

        # 2. LostItem에서 업데이트 대상 찾기
        # 🚇 지하철역만 처리 (transport="subway")
        if include_all:
            lost_items_to_update = LostItem.objects.filter(
                station__isnull=False, 
                station__icontains='역',
                line__isnull=True 
            )
        else:
            # 기본: transport="subway"인 것만 처리
            lost_items_to_update = LostItem.objects.filter(
                transport='subway',  # 🚇 지하철만!
                station__isnull=False, 
                station__icontains='역',
                line__isnull=True 
            )
        
        total_count = lost_items_to_update.count()
        self.stdout.write(f'📊 업데이트 대상: {total_count}건')

        # 통계 변수
        update_count = 0
        transfer_count = 0
        not_found_count = 0
        skipped_transfer_count = 0
        not_found_stations = set()
        
        if not dry_run:
            with transaction.atomic():
                update_count, transfer_count, not_found_count, skipped_transfer_count, not_found_stations = \
                    self._process_items(
                        lost_items_to_update, 
                        station_map_raw, 
                        station_map_std, 
                        transfer_strategy
                    )
        else:
            update_count, transfer_count, not_found_count, skipped_transfer_count, not_found_stations = \
                self._process_items(
                    lost_items_to_update, 
                    station_map_raw, 
                    station_map_std, 
                    transfer_strategy,
                    dry_run=True
                )
        
        # 3. 결과 출력
        self.stdout.write(self.style.SUCCESS(f'\n✅ LostItem 노선 보강 완료!'))
        self.stdout.write(f'  - 총 처리 대상: {total_count}건')
        self.stdout.write(f'  - 업데이트 완료: {update_count}건')
        self.stdout.write(f'  - 환승역 처리: {transfer_count}건')
        
        if transfer_strategy == 'skip':
            self.stdout.write(f'  - 환승역 스킵: {skipped_transfer_count}건')
        
        if not_found_count > 0:
            self.stdout.write(self.style.WARNING(f'  - 매칭 실패: {not_found_count}건'))
            self.stdout.write(f'\n⚠️  StationDict에 없는 역 (TOP 20):')
            for station in sorted(not_found_stations)[:20]:
                self.stdout.write(f'     - {station}')
            
            if len(not_found_stations) > 20:
                self.stdout.write(f'     ... 외 {len(not_found_stations) - 20}개')

    def _process_items(self, items, station_map_raw, station_map_std, transfer_strategy, dry_run=False):
        """실제 아이템 처리 로직"""
        update_count = 0
        transfer_count = 0
        not_found_count = 0
        skipped_transfer_count = 0
        not_found_stations = set()
        
        for item in items:
            raw_station_name = item.station
            station_infos = None
            
            # 1차 시도: 원본 역명으로 정확 매칭
            station_infos = station_map_raw.get(raw_station_name)
            
            # 2차 시도: "역" 제거 후 매칭 (중요!)
            if not station_infos:
                name_without_station = raw_station_name.replace('역', '').strip()
                station_infos = station_map_raw.get(name_without_station)
            
            # 3차 시도: 괄호 제거한 역명으로 매칭
            if not station_infos:
                clean_name = self._clean_station_name(raw_station_name)
                station_infos = station_map_raw.get(clean_name)
            
            # 4차 시도: 괄호 제거 + "역" 제거
            if not station_infos:
                clean_name = self._clean_station_name(raw_station_name).replace('역', '').strip()
                station_infos = station_map_raw.get(clean_name)
            
            # 5차 시도: 표준 역명으로 매칭
            if not station_infos:
                clean_name = self._clean_station_name(raw_station_name).replace('역', '').strip()
                station_infos = station_map_std.get(clean_name)
            
            # 매칭 실패
            if not station_infos:
                not_found_count += 1
                not_found_stations.add(raw_station_name)
                continue
            
            # 노선 정보 결정
            line_value = None
            
            if len(station_infos) == 1:
                # 단일 노선
                line_value = station_infos[0].line_code
                
            else:
                # 환승역
                transfer_count += 1
                
                if transfer_strategy == 'first':
                    # 첫 번째 노선 사용
                    line_value = station_infos[0].line_code
                    
                elif transfer_strategy == 'all':
                    # 모든 노선을 쉼표로 구분하여 저장
                    lines = [si.line_code for si in station_infos]
                    line_value = ','.join(sorted(set(lines)))
                    
                elif transfer_strategy == 'skip':
                    # 환승역 스킵
                    skipped_transfer_count += 1
                    continue
            
            # 업데이트 실행
            if line_value and not dry_run:
                item.line = line_value
                item.save(update_fields=['line'])
                update_count += 1
            elif line_value and dry_run:
                update_count += 1
                if update_count <= 10:  # 처음 10개만 출력
                    self.stdout.write(f'  [{update_count}] {raw_station_name} → {line_value}')
        
        return update_count, transfer_count, not_found_count, skipped_transfer_count, not_found_stations

    def _clean_station_name(self, station_name):
        """역 이름 정제 (괄호 및 공백 제거)"""
        # 괄호와 내용 제거
        cleaned = re.sub(r'\(.*?\)', '', station_name)
        # 공백 제거
        cleaned = cleaned.strip()
        return cleaned