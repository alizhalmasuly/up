from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .models import Comment, Story


class StoryForm(forms.ModelForm):
    class Meta:
        model = Story
        fields = ("title", "mountain", "hike_date", "difficulty", "description", "useful_tips", "equipment_used", "cover")
        widgets = {"hike_date": forms.DateInput(attrs={"type": "date"}), "description": forms.Textarea(attrs={"rows": 6})}

    def clean_cover(self):
        cover = self.cleaned_data.get("cover")
        if not isinstance(cover, UploadedFile):
            return cover

        cover.seek(0)
        with Image.open(cover) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")

            output = BytesIO()
            image.save(output, format="WEBP", quality=78, method=6)

        return ContentFile(output.getvalue(), name=f"{Path(cover.name).stem}.webp")


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}
