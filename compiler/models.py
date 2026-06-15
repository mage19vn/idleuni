from django.db import models
import random
import string

def generate_random_uni_name():
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"Uni_{code}"

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
        ('unicorns-dark', 'Uni Dark'),
        ('unicorns-light', 'Uni Light'),
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
    
    session_id = models.CharField(max_length=100, unique=True, verbose_name="Session ID")
    display_name = models.CharField(max_length=50, default=generate_random_uni_name, verbose_name="Tên tác giả")
    bio = models.TextField(max_length=500, blank=True, null=True, verbose_name="Mô tả cơ bản")
    default_language = models.CharField(max_length=20, choices=LANG_CHOICES, default='python', verbose_name="Ngôn ngữ mặc định")
    favorite_theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='dark', verbose_name="Theme UI yêu thích")
    editor_theme = models.CharField(max_length=20, choices=EDITOR_THEME_CHOICES, default='unicorns-dark', verbose_name="Theme Editor")
    editor_font_family = models.CharField(max_length=100, choices=EDITOR_FONT_CHOICES, default="'Consolas', 'Fira Code', monospace", verbose_name="Font Editor")
    editor_font_size = models.IntegerField(default=14, verbose_name="Cỡ chữ Editor")

    def __str__(self):
        return f"Profile - {self.session_id}"

class CodeSnippet(models.Model):
    hash_id = models.CharField(max_length=8, unique=True, db_index=True)
    content_hash = models.CharField(max_length=64, db_index=True, blank=True, null=True)
    session_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="Session ID")
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
    session_id = models.CharField(max_length=100, verbose_name="Session ID")
    name = models.CharField(max_length=50)
    language = models.CharField(max_length=20, choices=[('python', 'Python'), ('cpp', 'C++'), ('all', 'All')])
    code = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session_id', 'name', 'language')

    def __str__(self):
        return f"{self.session_id} - {self.name} ({self.language})"

class KeymapTemplate(models.Model):
    hash_id = models.CharField(max_length=8, unique=True, db_index=True)
    name = models.CharField(max_length=100, default='Custom Keymap')
    keymap_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Keymap {self.hash_id}"
