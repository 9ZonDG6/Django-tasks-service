from rest_framework import serializers

from apps.tasks.models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "owner_id", "title", "description", "completed", "created_at", "updated_at"]
        read_only_fields = ["id", "owner_id", "created_at", "updated_at"]
