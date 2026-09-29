from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from community.models import Story

from .forms import PreparationForm
from .models import Equipment, GearCheck, Mountain, SavedHike
from .services import MountainProviderError, MountainSearchRateLimited, get_nearby_trails, search_mountains


def mountain_list(request):
    query = request.GET.get("q", "").strip()
    mountains = Mountain.objects.all()
    if query:
        mountains = mountains.filter(Q(name__icontains=query) | Q(location__icontains=query))
    return render(request, "mountains/list.html", {"mountains": mountains, "query": query})


@require_GET
def mountain_search_api(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 3:
        return JsonResponse({"results": []})
    try:
        results = search_mountains(query, (request.LANGUAGE_CODE or "en").split("-")[0])
    except MountainSearchRateLimited:
        return JsonResponse({"error": "rate_limited"}, status=429)
    except MountainProviderError:
        return JsonResponse({"error": "search_unavailable"}, status=502)
    return JsonResponse({"results": results, "source": "OpenStreetMap"})


@require_GET
def mountain_trails_api(request):
    try:
        latitude = float(request.GET.get("lat", ""))
        longitude = float(request.GET.get("lon", ""))
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return JsonResponse({"error": "invalid_coordinates"}, status=400)
        trails = get_nearby_trails(latitude, longitude)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_coordinates"}, status=400)
    except MountainSearchRateLimited:
        return JsonResponse({"error": "rate_limited"}, status=429)
    except MountainProviderError:
        return JsonResponse({"error": "trails_unavailable"}, status=502)
    return JsonResponse(trails)


def mountain_detail(request, slug):
    mountain = get_object_or_404(Mountain, slug=slug)
    stories = Story.objects.filter(mountain=mountain).select_related("author")[:3]
    is_saved = request.user.is_authenticated and SavedHike.objects.filter(user=request.user, mountain=mountain).exists()
    return render(request, "mountains/detail.html", {"mountain": mountain, "stories": stories, "is_saved": is_saved})


@login_required
def toggle_saved(request, slug):
    mountain = get_object_or_404(Mountain, slug=slug)
    saved, created = SavedHike.objects.get_or_create(user=request.user, mountain=mountain)
    if not created:
        saved.delete()
    return redirect("mountains:detail", slug=slug)


@login_required
def prepare(request):
    initial = {}
    initial_place = None
    if request.method == "GET":
        mountain_slug = request.GET.get("mountain", "").strip()
        if mountain_slug:
            mountain = Mountain.objects.filter(slug=mountain_slug).first()
            if mountain:
                initial["mountain"] = mountain.name
                initial_place = {
                    "name": mountain.name,
                    "location": mountain.location,
                    "latitude": mountain.latitude,
                    "longitude": mountain.longitude,
                    "elevation": mountain.altitude,
                    "description": mountain.short_description,
                    "kind": "mountain",
                }
    form = PreparationForm(request.POST or None, initial=initial)
    equipment = Equipment.objects.all()
    if request.method == "POST":
        if form.is_valid():
            for item in equipment:
                have_it = request.POST.get(f"gear_{item.id}") == "have"
                GearCheck.objects.update_or_create(user=request.user, equipment=item, defaults={"have_it": have_it})
            messages.success(request, "Список снаряжения сохранён")
            return redirect("mountains:prepare")
    checks = {check.equipment_id: check.have_it for check in GearCheck.objects.filter(user=request.user)}
    groups = {}
    for item in equipment:
        groups.setdefault(item.category, []).append(item)
    return render(request, "mountains/prepare.html", {"form": form, "groups": groups, "checks": checks, "initial_place": initial_place})
