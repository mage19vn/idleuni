from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['readonly'] = True
        self.fields['username'].help_text = "Không thể thay đổi tên đăng nhập."

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'default_language', 'favorite_theme', 'editor_theme', 'editor_font_family', 'editor_font_size']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
        }
