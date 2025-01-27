from django.db import models

class User(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    preferences = models.JSONField(null=True, blank=True, default=list)
