
# Create your models here.
from django.db import models
from django.core.exceptions import ValidationError
import re


# Create your models here.


def validate_category_name(value):
    if not value.strip():
        raise ValidationError("Category name cannot be empty or just spaces")
    if not re.match("^[a-zA-Z\s]+$", value):
        raise ValidationError("Category name can only contain letters and spaces")


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, validators=[validate_category_name])
    is_listed = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def soft_delete(self):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()