"""Public, login-free pages for Problem Set 3 (personas, scenarios, findings, MVP).

All content is synthetic or anonymised. No private interview notes are stored here.
"""
from django.http import Http404
from django.shortcuts import render

from .data import FINDINGS, MVP, PERSONAS, ROLES, STORIES


def index(request):
    return render(request, "ps4/index.html", {"personas": PERSONAS.values()})


def _get_persona(slug):
    persona = PERSONAS.get(slug)
    if persona is None:
        raise Http404("Unknown persona")
    return persona


def persona(request, slug):
    return render(request, "ps4/persona.html", {"p": _get_persona(slug)})


def scenario(request, slug):
    return render(request, "ps4/scenario.html", {"p": _get_persona(slug)})


def findings(request):
    return render(request, "ps4/findings.html", {"findings": FINDINGS})


def requirements(request):
    return render(
        request, "ps4/requirements.html", {"roles": ROLES, "stories": STORIES}
    )


def mvp(request):
    return render(request, "ps4/mvp.html", {"mvp": MVP})
