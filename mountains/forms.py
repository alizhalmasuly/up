from django import forms

from .models import Mountain


class PreparationForm(forms.Form):
    # The selected place comes from the public place-search API, so it cannot
    # be restricted to the site's curated Mountain rows.
    mountain = forms.CharField(max_length=200)
    difficulty = forms.ChoiceField(choices=Mountain.DIFFICULTY_CHOICES)
    duration_hours = forms.IntegerField(min_value=1, max_value=48, initial=5)
    season = forms.ChoiceField(choices=[("spring", "Весна"), ("summer", "Лето"), ("autumn", "Осень"), ("winter", "Зима")])
    people_count = forms.IntegerField(min_value=1, max_value=50, initial=2)
