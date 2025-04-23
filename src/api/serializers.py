from rest_framework import serializers
from rest_framework.reverse import reverse_lazy

from core.models import Batch, BatchCommand


class BatchListSerializer(serializers.HyperlinkedModelSerializer):
    """
    Simple Serializer used for API listing and BatchCommands
    """

    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return {"code": obj.status, "display": obj.get_status_display()}

    class Meta:
        model = Batch
        fields = [
            "url",
            "pk",
            "user",
            "name",
            "status",
            "message",
            "created",
            "modified",
        ]


class BatchDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Full batch serializer
    """

    status = serializers.SerializerMethodField()
    commands_url = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    def get_status(self, obj):
        return {"code": obj.status, "display": obj.get_status_display()}

    def get_commands_url(self, obj):
        return reverse_lazy(
            "command-list", kwargs={"batchpk": obj.pk}, request=self.context["request"]
        )

    def get_summary(self, obj):
        return {
            "initial_commands": obj.initial_commands,
            "running_commands": obj.running_commands,
            "done_commands": obj.done_commands,
            "error_commands": obj.error_commands,
            "total_commands": obj.total_commands,
        }

    class Meta:
        model = Batch
        fields = [
            "pk",
            "name",
            "user",
            "status",
            "summary",
            "commands_url",
            "message",
            "created",
            "modified",
        ]


class BatchCommandListSerializer(serializers.HyperlinkedModelSerializer):
    """
    Simple BatchCommand used for simple listing
    """

    url = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()

    def get_action(self, obj):
        return obj.get_action_display()

    def get_url(self, obj):
        return reverse_lazy(
            "command-detail", kwargs={"pk": obj.pk}, request=self.context["request"]
        )

    class Meta:
        model = BatchCommand
        fields = [
            "url",
            "pk",
            "index",
            "action",
            "json",
            "response_id",
            "status",
            "created",
            "modified",
        ]


class BatchCommandDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    FULL batch command serializer
    """

    batch = BatchListSerializer()
    status = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()

    def get_action(self, obj):
        return obj.get_action_display()

    def get_status(self, obj):
        return {"code": obj.status, "display": obj.get_status_display()}

    class Meta:
        model = BatchCommand
        fields = [
            "batch",
            "pk",
            "index",
            "action",
            "raw",
            "json",
            "response_id",
            "status",
            "created",
            "modified",
        ]
