from io import BytesIO
from pathlib import Path

from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Comment, Story


class StoryForm(forms.ModelForm):
    description = forms.CharField(max_length=6000, widget=forms.Textarea(attrs={"rows": 6}))
    useful_tips = forms.CharField(required=False, max_length=3000, widget=forms.Textarea(attrs={"rows": 5}))

    class Meta:
        model = Story
        fields = ("title", "mountain", "hike_date", "difficulty", "description", "useful_tips", "equipment_used", "cover")
        widgets = {"hike_date": forms.DateInput(attrs={"type": "date"}), "description": forms.Textarea(attrs={"rows": 6})}

    def clean_cover(self):
        cover = self.cleaned_data.get("cover")
        if not isinstance(cover, UploadedFile):
            return cover
        if cover.size > 12 * 1024 * 1024:
            raise forms.ValidationError("Cover image must be no larger than 12 MB.")

        cover.seek(0)
        try:
            with Image.open(cover) as source:
                if source.width * source.height > 36_000_000:
                    raise forms.ValidationError("Cover image dimensions are too large.")
                image = ImageOps.exif_transpose(source)
                image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGB")

                output = BytesIO()
                image.save(output, format="WEBP", quality=78, method=6)
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
            raise forms.ValidationError("Upload a valid image file.") from exc

        return ContentFile(output.getvalue(), name=f"{Path(cover.name).stem}.webp")


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}
