from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet
from rest_framework.exceptions import NotAuthenticated
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import ModelViewSet

from apps.tasks.authentication import Principal
from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer


class TaskViewSet(ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self) -> QuerySet[Task]:
        return Task.objects.filter(owner_id=self.owner_id())

    def perform_create(self, serializer: BaseSerializer[Task]) -> None:
        serializer.save(owner_id=self.owner_id())

    def owner_id(self) -> UUID:
        user = self.request.user
        if not isinstance(user, Principal):
            raise NotAuthenticated()
        return user.id
