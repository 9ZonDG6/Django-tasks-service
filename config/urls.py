from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tasks.views import TaskViewSet

router = DefaultRouter()
router.register("tasks", TaskViewSet, basename="task")
urlpatterns = [path("api/v1/", include(router.urls))]
