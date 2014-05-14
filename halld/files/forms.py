from django import forms

from .models import ResourceFile

class UploadFileForm(forms.ModelForm):
    file = forms.FileField()
    content_type = forms.CharField(required=False)

    def clean_content_type(self):
        content_type = self.cleaned_data['content_type']
        if not content_type:
            content_type = self.files['file'].content_type
        return content_type

    class Meta:
        model = ResourceFile
        fields = ('file', 'content_type')