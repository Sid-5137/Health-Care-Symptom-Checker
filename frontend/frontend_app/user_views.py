from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .user_forms import SignUpForm, LoginForm, ProfileForm
from .forms import SymptomForm
from .models import SymptomHistory, UserProfile
import os
import requests

# FastAPI backend endpoint (moved to backend/). Allow override via env var.
BACKEND_BASE = os.getenv("BACKEND_URL", "https://health-care-symptom-checker-1.onrender.com").rstrip("/")
BACKEND_URL = f"{BACKEND_BASE}/check"

def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            UserProfile.objects.get_or_create(user=user)
            # Use namespaced URL to avoid NoReverseMatch when app is namespaced
            return redirect("frontend_app:profile")
    else:
        form = SignUpForm()
    return render(request, "signup.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Use namespaced URL for consistency
            return redirect("frontend_app:home")
    else:
        form = LoginForm()
    return render(request, "registration/login.html", {"form": form})

def logout_view(request):
    logout(request)
    # Redirect to our custom login route (namespaced) to avoid /accounts/login/
    return redirect("frontend_app:login")

@login_required
def profile_view(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    user = request.user
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user_profile)
        if form.is_valid():
            form.save()
    else:
        form = ProfileForm(instance=user_profile)
    return render(request, "profile.html", {"form": form, "user": user})

@login_required
def history_view(request):
    history = SymptomHistory.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "history.html", {"history": history})

@login_required
def history_clear(request):
    if request.method == "POST":
        SymptomHistory.objects.filter(user=request.user).delete()
        messages.success(request, "Your history has been cleared.")
        return redirect("frontend_app:history")
    return redirect("frontend_app:history")

@login_required
def home(request):
    result = None
    error = None
    rec_list = None
    used_family_history = False
    if request.method == "POST":
        form = SymptomForm(request.POST)
        if form.is_valid():
            symptoms = form.cleaned_data["symptoms"]
            target_language = form.cleaned_data["target_language"]
            consider_family = form.cleaned_data.get("consider_family_history", True)
            # Pull optional family history from the user's profile
            family_history = (
                UserProfile.objects.filter(user=request.user)
                .values_list("family_history", flat=True)
                .first()
            )
            used_family_history = bool(family_history and str(family_history).strip()) and consider_family
            try:
                payload = {
                    "symptoms": symptoms,
                }
                if consider_family and family_history:
                    payload["family_history"] = family_history
                response = requests.post(
                    BACKEND_URL + f"?target_language={target_language}",
                    json=payload,
                    timeout=60,
                )
                if response.status_code == 200:
                    result = response.json()
                    # Convert recommendations paragraph to list points (split by semicolons)
                    rec_text = result.get("recommendations", "") or ""
                    parts = [p.strip() for p in rec_text.split(";")]
                    rec_list = [p for p in parts if p]
                    SymptomHistory.objects.create(
                        user=request.user,
                        symptoms=symptoms,
                        probable_conditions="\n".join(result.get("probable_conditions", [])),
                        recommendations=result.get("recommendations", ""),
                        disclaimer=result.get("disclaimer", ""),
                    )
                else:
                    error = f"Backend error: {response.status_code} - {response.text}"
            except Exception as e:
                error = f"Request failed: {e}"
    else:
        form = SymptomForm()
    return render(
        request,
        "home.html",
        {
            "form": form,
            "result": result,
            "error": error,
            "rec_list": rec_list,
            "used_family_history": used_family_history,
        },
    )
