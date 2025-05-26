from django.http import Http404

from rest_framework import generics
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated

from api import serializers
from api.paginators import CustomPagination
from api.paginators import CustomBatchCommandPagination

from core.models import Batch
from core.models import BatchCommand


class BatchListView(generics.ListCreateAPIView):
    """
    Available batches listing
    """

    pagination_class = CustomPagination
    serializer_class = serializers.BatchListSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return (
            serializers.BatchCreationSerializer
            if self.request.method == "POST"
            else serializers.BatchListSerializer
        )

    def get_queryset(self):
        queryset = Batch.objects.order_by("-created")
        user = self.request.query_params.get("username")
        if user is not None:
            queryset = queryset.filter(user=user)
        status = self.request.query_params.get("status")
        if status is not None:
            queryset = queryset.filter(status=status)
        return queryset


class BatchDetailView(generics.GenericAPIView, mixins.RetrieveModelMixin):
    """
    Batch detail
    """

    permission_classes = [IsAuthenticated]

    queryset = Batch.objects.all()
    serializer_class = serializers.BatchDetailSerializer

    def get_object(self):
        from django.db.models import Q, Count

        try:
            error_commands = Count(
                "batchcommand", filter=Q(batchcommand__status=BatchCommand.STATUS_ERROR)
            )
            initial_commands = Count(
                "batchcommand",
                filter=Q(batchcommand__status=BatchCommand.STATUS_INITIAL),
            )
            running_commands = Count(
                "batchcommand",
                filter=Q(batchcommand__status=BatchCommand.STATUS_RUNNING),
            )
            done_commands = Count(
                "batchcommand", filter=Q(batchcommand__status=BatchCommand.STATUS_DONE)
            )
            batch = (
                Batch.objects.annotate(error_commands=error_commands)
                .annotate(initial_commands=initial_commands)
                .annotate(running_commands=running_commands)
                .annotate(done_commands=done_commands)
                .annotate(total_commands=Count("batchcommand"))
                .get(pk=self.kwargs["pk"])
            )
            return batch
        except Batch.DoesNotExist:
            raise Http404

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class BatchCommandListView(generics.GenericAPIView, mixins.ListModelMixin):
    """
    Batch commands listing. Uses pagination.
    """

    permission_classes = [IsAuthenticated]

    pagination_class = CustomBatchCommandPagination
    serializer_class = serializers.BatchCommandListSerializer

    def get_queryset(self):
        return (
            BatchCommand.objects.select_related("batch")
            .filter(batch__pk=self.kwargs["batchpk"])
            .order_by("index")
        )

    def get(self, request, *args, **kwargs):
        try:
            batch = Batch.objects.get(pk=kwargs["batchpk"])
            request.batch = batch
        except Batch.DoesNotExist:
            raise Http404
        return self.list(request, *args, **kwargs)


class BatchCommandDetailView(generics.GenericAPIView, mixins.RetrieveModelMixin):
    """
    Batch command detail
    """

    permission_classes = [IsAuthenticated]

    queryset = BatchCommand.objects.select_related("batch").all()
    serializer_class = serializers.BatchCommandDetailSerializer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
