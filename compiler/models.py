from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    THEME_CHOICES = [
        ('dark', 'Giao diện Tối'),
        ('light', 'Giao diện Sáng'),
    ]
    LANG_CHOICES = [
        ('python', 'Python 3'),
        ('cpp', 'C++ (GDB)'),
    ]
    EDITOR_THEME_CHOICES = [
        ('unicorns-dark', 'Unicorns Dark'),
        ('unicorns-light', 'Unicorns Light'),
        ('vs-dark', 'VS Dark'),
        ('vs', 'VS Light'),
        ('hc-black', 'High Contrast Dark'),
    ]
    EDITOR_FONT_CHOICES = [
        ("'Consolas', 'Fira Code', monospace", 'Consolas / Fira Code'),
        ("'JetBrains Mono', monospace", 'JetBrains Mono'),
        ("'Courier New', Courier, monospace", 'Courier New'),
        ("'Source Code Pro', monospace", 'Source Code Pro'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True, null=True, verbose_name="Mô tả cơ bản")
    default_language = models.CharField(max_length=20, choices=LANG_CHOICES, default='python', verbose_name="Ngôn ngữ mặc định")
    favorite_theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='dark', verbose_name="Theme UI yêu thích")
    editor_theme = models.CharField(max_length=20, choices=EDITOR_THEME_CHOICES, default='unicorns-dark', verbose_name="Theme Editor")
    editor_font_family = models.CharField(max_length=100, choices=EDITOR_FONT_CHOICES, default="'Consolas', 'Fira Code', monospace", verbose_name="Font Editor")
    editor_font_size = models.IntegerField(default=14, verbose_name="Cỡ chữ Editor")

    def __str__(self):
        return f"{self.user.username} Profile"

# Signal để tự động tạo Profile khi User được tạo
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class CodeSnippet(models.Model):
    hash_id = models.CharField(max_length=8, unique=True, db_index=True)
    content_hash = models.CharField(max_length=64, db_index=True, blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='snippets')
    title = models.CharField(max_length=100, default='Không tên')
    is_public = models.BooleanField(default=True)
    language = models.CharField(max_length=20)
    file_path = models.CharField(max_length=255)
    input_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.hash_id}) - {self.language}"

class CodeTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates')
    name = models.CharField(max_length=50)
    language = models.CharField(max_length=20, choices=[('python', 'Python'), ('cpp', 'C++'), ('all', 'All')])
    code = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name', 'language')

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.language})"
