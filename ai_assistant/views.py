import json
from hashlib import sha256

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from mountains.models import Mountain

from .services import recommend_gear


def chat_page(request):
    return render(request, "ai_assistant/chat.html", {
        "mountains": Mountain.objects.all(),
        "difficulty_choices": Mountain.DIFFICULTY_CHOICES,
    })


@require_POST
def chat(request):
    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return JsonResponse({"error": "Invalid request size"}, status=400)
    if content_length > 16 * 1024:
        return JsonResponse({"error": "Request is too large"}, status=413)

    identity = f"user:{request.user.pk}" if request.user.is_authenticated else f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
    rate_key = "assistant-chat-rate:" + sha256(identity.encode()).hexdigest()
    if cache.add(rate_key, 1, timeout=60):
        request_count = 1
    else:
        try:
            request_count = cache.incr(rate_key)
        except ValueError:
            if cache.add(rate_key, 1, timeout=60):
                request_count = 1
            else:
                request_count = cache.get(rate_key, 1)
    if request_count > 20:
        return JsonResponse({"error": "Too many requests. Try again in a minute."}, status=429)

    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request"}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid request"}, status=400)
    message = str(body.get("message", "")).strip()[:2000]
    if not message:
        return JsonResponse({"error": "Message is required"}, status=400)
    try:
        latitude = float(body.get("latitude"))
        longitude = float(body.get("longitude"))
    except (TypeError, ValueError):
        latitude = longitude = None
    if latitude is not None and not -90 <= latitude <= 90:
        latitude = None
    if longitude is not None and not -180 <= longitude <= 180:
        longitude = None
    reply = recommend_gear(
        message, mountain=str(body.get("mountain", ""))[:120], season=str(body.get("season", "summer"))[:30],
        duration=str(body.get("duration", "5"))[:30], difficulty=str(body.get("difficulty", "moderate"))[:30],
        language=(request.LANGUAGE_CODE or "ru").split("-")[0], latitude=latitude, longitude=longitude,
    )
    return JsonResponse({"reply": reply})
