from django.shortcuts import render

from core.models import Batch
from core.models import BatchCommand


def statistics(request):
    batches_count = Batch.objects.all().count()
    editors = Batch.objects.values("user").distinct().count()
    commands_count = BatchCommand.objects.all().count()
    average_commands_per_batch = (
        round(commands_count / batches_count) if batches_count > 0 else 0
    )
    # TODO: we can refactor a lot of this into a BatchCommand model manager
    items_created = BatchCommand.objects.filter(
        operation=BatchCommand.Operation.CREATE_ITEM,
        status=BatchCommand.STATUS_DONE,
    ).count()
    edits = (
        BatchCommand.objects.filter(status=BatchCommand.STATUS_DONE)
        .exclude(response_id__isnull=True)
        .exclude(response_id="")
        .count()
    )
    data = {
        "batches_count": batches_count,
        "commands_count": commands_count,
        "average_commands_per_batch": average_commands_per_batch,
        "items_created": items_created,
        "editors": editors,
        "edits": edits,
    }
    return render(request, "statistics.html", data)
