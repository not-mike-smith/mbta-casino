from django.urls import path

from . import views

urlpatterns = [
    path("bets", views.place_bet),
    path("bets/active", views.active_bet),
    path("bets/history", views.bet_history),
]
