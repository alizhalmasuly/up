from django.conf import settings
from django.db import models

from mountains.models import Mountain, difficulty_label, optimize_photo_url


class Story(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories")
    mountain = models.ForeignKey(Mountain, on_delete=models.SET_NULL, null=True, blank=True, related_name="stories")
    title = models.CharField(max_length=160)
    hike_date = models.DateField()
    difficulty = models.CharField(max_length=12, choices=Mountain.DIFFICULTY_CHOICES, default=Mountain.MODERATE)
    description = models.TextField()
    useful_tips = models.TextField(blank=True)
    equipment_used = models.CharField(max_length=300, blank=True)
    cover = models.ImageField(upload_to="stories/", blank=True)
    cover_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="liked_stories")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

    def get_difficulty_display(self):
        return difficulty_label(self.difficulty)

    @property
    def image(self):
        image_url = self.cover.url if self.cover else (self.cover_url or (self.mountain.image_url if self.mountain else ""))
        return optimize_photo_url(image_url)


class Comment(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_comments")
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Comment by {self.author}"
