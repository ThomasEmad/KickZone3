from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, PitchViewSet, PitchAvailabilityViewSet, BookingViewSet, PaymentViewSet,
    ReviewViewSet, TournamentViewSet, TournamentTeamViewSet, MessageViewSet,
    MessageGroupViewSet, PromotionViewSet, SystemSettingViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'pitches', PitchViewSet)
router.register(r'pitch-availabilities', PitchAvailabilityViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'tournaments', TournamentViewSet)
router.register(r'tournament-teams', TournamentTeamViewSet)
router.register(r'messages', MessageViewSet)
router.register(r'message-groups', MessageGroupViewSet)
router.register(r'promotions', PromotionViewSet)
router.register(r'settings', SystemSettingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
