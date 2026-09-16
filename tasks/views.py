from rest_framework.viewsets import ModelViewSet

from tasks.models import Task
from tasks.serializers import TaskSerializer


class TaskViewSet(ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(owner_id=self.request.user.id)

    def perform_create(self, serializer):
        serializer.save(owner_id=self.request.user.id)
