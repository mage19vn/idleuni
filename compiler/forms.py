from django import forms
from .models import Profile

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'default_language', 'favorite_theme', 'editor_theme', 'editor_font_family', 'editor_font_size']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
        }
