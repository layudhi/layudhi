from django import forms
from .models import Document, SocializationEvent


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'theme', 'description', 'file', 'valid_from', 'valid_until']
        widgets = {'valid_from': forms.DateInput(attrs={'type': 'date'}), 'valid_until': forms.DateInput(attrs={'type': 'date'})}


class EventForm(forms.ModelForm):
    class Meta:
        model = SocializationEvent
        fields = ['title', 'division', 'place', 'schedule', 'presenter', 'materials', 'notes']
        widgets = {'schedule': forms.DateTimeInput(attrs={'type': 'datetime-local'})}


class UploadUsersForm(forms.Form):
    csv_file = forms.FileField(label='File CSV user')
