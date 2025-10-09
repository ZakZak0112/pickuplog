from django.db import models

class LostItem(models.Model):
    item_id = models.CharField(max_length=50, unique=True)
    transport = models.CharField(max_length=20, null=True, blank=True)
    line = models.CharField(max_length=50, null=True, blank=True)
    station = models.CharField(max_length=100, null=True, blank=True)
    category = models.CharField(max_length=50, null=True, blank=True)
    item_name = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    is_received = models.BooleanField(default=False)
    registered_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    storage_location = models.CharField(max_length=200, null=True, blank=True)
    registrar_id = models.CharField(max_length=100, null=True, blank=True)
    pickup_company_location = models.CharField(max_length=200, null=True, blank=True)
    views = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.item_name} ({self.category})"
