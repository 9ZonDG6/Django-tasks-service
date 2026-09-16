from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tasks.views import TaskViewSet

router = DefaultRouter()
router.register("tasks", TaskViewSet, basename="task")
urlpatterns = [path("api/", include(router.urls))]
