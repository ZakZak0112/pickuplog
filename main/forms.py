from django import forms
from .models import LostItem

# ==========================================================
# 1. 상태 선택지 상수 정의 (AttributeError 해결)
#    - CSV 데이터 '보관', '수령'을 기반으로 정의했습니다.
# ==========================================================
STATUS_CHOICES = (
    ("보관", "보관"),
    ("수령", "수령"),
    # 필요한 경우 여기에 다른 상태 (예: "폐기", "인계" 등)를 추가하세요.
)


class LostItemForm(forms.ModelForm):
    class Meta:
        model = LostItem
        fields = [
            "item_id","transport","line","station",
            "category","item_name","status","is_received",
            "registered_at","received_at",
            "description","storage_location","registrar_id",
            "pickup_company_location","views",
        ]
        widgets = {
            "registered_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "received_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class LostItemSearchForm(forms.Form):
    q = forms.CharField(label="키워드", required=False)
    
    # 교통수단 선택지
    TRANSPORT_CHOICES = [
        ("", "전체"), 
        ("subway", "지하철"), 
        ("bus", "버스"), 
        ("taxi", "택시"), 
        ("etc", "기타")
    ]
    transport = forms.ChoiceField(label="교통수단", required=False, choices=TRANSPORT_CHOICES)
    
    status = forms.ChoiceField(label="상태", required=False,
        choices=[("", "전체")] + list(STATUS_CHOICES)) 
        
    category = forms.MultipleChoiceField(
        choices=[],  # __init__에서 동적으로 채워질 예정
        required=False,
        # 기존: forms.SelectMultiple(attrs={'size': 5})
        widget=forms.CheckboxSelectMultiple # 체크박스 목록 위젯 사용
    )
    
    
    only_unreceived = forms.BooleanField(label="미수령만", required=False)
    date_from = forms.DateField(label="등록 시작", required=False, widget=forms.DateInput(attrs={"type":"date"}))
    date_to   = forms.DateField(label="등록 끝",  required=False, widget=forms.DateInput(attrs={"type":"date"}))
    sort = forms.ChoiceField(label="정렬", required=False, initial="registered_at_desc",
        choices=[("registered_at_desc","등록 최신순"),("registered_at_asc","등록 오래된순"),("views_desc","조회수 높은순")])
    page_size = forms.IntegerField(label="표시 개수", required=False, min_value=10, max_value=200, initial=30)
    
    # 🌟🌟🌟 추가된 부분: 카테고리 선택지를 동적으로 로드 🌟🌟🌟
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 데이터베이스에서 모든 카테고리를 가져와 choices를 만듭니다.
        # values_list('category', 'category')를 사용하여 (값, 표시 이름) 형태를 만듭니다.
        category_choices = list(LostItem.objects.values_list('category', 'category').distinct().order_by('category'))
        
        # 필드에 choices를 할당합니다.
        # 다중 선택 필드에는 "전체" 옵션이 필요하지 않습니다. (아무것도 선택하지 않으면 '전체' 효과)
        self.fields['category'].choices = category_choices
    # -------------------------------------------------------------


# ==========================================================
# 2. CSV 파일 업로드 폼 (기존 코드를 그대로 유지)
# ==========================================================
class LostItemCsvUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV 파일 선택",
        help_text="잃어버린 물건 데이터가 포함된 CSV 파일을 선택하세요."
    )