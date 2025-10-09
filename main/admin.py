from django.contrib import admin
from .models import LostItem

@admin.register(LostItem)
class LostItemAdmin(admin.ModelAdmin):
    list_display = ("item_id","category","item_name","transport","line","station","status","is_received","registered_at","views")
    list_filter = ("transport","status","is_received","category","line","station")
    search_fields = ("item_id","item_name","description","storage_location","station")
    date_hierarchy = "registered_at"
