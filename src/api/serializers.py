from django.utils import timezone
from django.db.utils import OperationalError
from django.db.utils import ProgrammingError
from rest_framework import serializers
from rest_framework.reverse import reverse_lazy

from core.parsers import V1CommandParser
from core.exceptions import ServerError, UnauthorizedToken
from core.models import Batch, BatchCommand, Wikibase, get_default_wikibase, Token, Client


class WikibaseField(serializers.ChoiceField):
    choices = []

    def __init__(self, *args, **kw):
        try:
            kw.setdefault("choices", Wikibase.objects.all())
        except (OperationalError, ProgrammingError):
            # db not initialized
            pass
        return super().__init__(*args, **kw)

    def to_representation(self, value):
        return value.url


class RawV1CommandField(serializers.CharField):
    many = True

    def to_internal_value(self, data):
        parser = V1CommandParser()
        return [c for c in parser.parse(data or "")]

    def to_representation(self, value):
        return "\n".join(value.values_list("raw", flat=True))


class BatchListSerializer(serializers.HyperlinkedModelSerializer):
    """
    Simple Serializer used for API listing and BatchCommands
    """

    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return {"code": obj.status, "display": obj.get_status_display()}

    class Meta:
        model = Batch
        fields = ("url", "pk", "user", "name", "status", "message", "created", "modified")


class BatchCreationSerializer(serializers.HyperlinkedModelSerializer):
    name = serializers.CharField(required=False, write_only=True)
    v1 = RawV1CommandField(write_only=True)
    wikibase = WikibaseField(required=False)

    def validate_name(self, value):
        request = self.context.get("request")
        return value or f"Batch user:{request.user.username} {timezone.now().isoformat()}"

    def validate_wikibase(self, value):
        request = self.context.get("request")
        wikibase = value or get_default_wikibase()

        try:
            token = Token.objects.get(user=request.user)
            client = Client(token=token, wikibase=wikibase)
            assert client.get_is_autoconfirmed()
            assert client.get_is_blocked()
        except (AssertionError, UnauthorizedToken, Token.DoesNotExist, ServerError):
            raise serializers.ValidationError(f"Failed to authenticate user at {wikibase.url}")
        return wikibase

    def create(self, validated_data):
        request = self.context.get("request")
        batch_commands = validated_data.pop("v1", [])

        batch = Batch.objects.create(
            user=request.user.username, status=Batch.STATUS_INITIAL, **validated_data
        )
        for batch_command in batch_commands:
            batch_command.batch = batch
            batch_command.save()
        return batch

    class Meta:
        model = Batch
        fields = (
            "url",
            "name",
            "v1",
            "wikibase",
            "combine_commands",
            "block_on_errors",
        )


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
            "initial_commands": obj.total_initial,
            "running_commands": obj.total_running,
            "done_commands": obj.total_done,
            "error_commands": obj.total_error,
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
