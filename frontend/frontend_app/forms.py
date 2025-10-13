from django import forms

LANGUAGE_CHOICES = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("bn", "Bengali"),
    ("ml", "Malayalam"),
    ("gu", "Gujarati"),
    ("kn", "Kannada"),
    ("mr", "Marathi"),
    ("pa", "Punjabi"),
]

class SymptomForm(forms.Form):
    symptoms = forms.CharField(
        label="Describe your symptoms",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        required=True,
    )
    target_language = forms.ChoiceField(
        label="Preferred Language",
        choices=LANGUAGE_CHOICES,
        initial="en",
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )
    consider_family_history = forms.BooleanField(
        label="Consider my family health history",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
