from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


class Vouch(models.Model):
    voucher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vouches_given')
    vouchee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vouches_received')

    skill_area = models.CharField(max_length=100, blank=True)  # e.g. "React", "UI Design"
    technical_quality = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    reliability = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)

    reference_id = models.CharField(max_length=100, blank=True)  # id của Milestone/Trade liên quan, nếu có

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.voucher.username} vouched for {self.vouchee.username} ({self.technical_quality}/{self.reliability})"

    def clean(self):
        if self.voucher_id == self.vouchee_id:
            raise ValidationError("You cannot vouch for yourself.")