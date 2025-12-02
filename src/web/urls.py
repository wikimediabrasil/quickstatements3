from django.urls import path

from .views.auth import login
from .views.auth import logout
from .views.auth import login_dev
from .views.auth import oauth_redirect
from .views.auth import oauth_callback
from .views.batch import batch
from .views.batch import batch_commands
from .views.batch import batch_stop
from .views.batch import batch_restart
from .views.batch import batch_rerun
from .views.batch import batch_report
from .views.batch import batch_summary
from .views.batches import home
from .views.batches import last_batches
from .views.batches import last_batches_by_user
from .views.batches import last_batches_table
from .views.new_batch import new_batch
from .views.new_batch import redirect_to_preview_last_batch
from .views.new_batch import preview_batch_pk
from .views.new_batch import preview_batch_commands_pk
from .views.new_batch import batch_allow_start_pk
from .views.profile import profile
from .views.profile import language_change
from .views.statistics import statistics
from .views.statistics import all_time_counters
from .views.statistics import plots
from .views.statistics import statistics_user
from .views.statistics import all_time_counters_user
from .views.statistics import plots_user


urlpatterns = [
    path("", home, name="home"),
    path("auth/login/", login, name="login"),
    path("auth/logout/", logout, name="logout"),
    path("auth/login/dev/", login_dev, name="login_dev"),
    path("auth/profile/", profile, name="profile"),
    path("auth/redirect/", oauth_redirect, name="oauth_redirect"),
    path("auth/callback/", oauth_callback, name="oauth_callback"),
    path("batches/", last_batches, name="last_batches"),
    path("batches/<str:user>/", last_batches_by_user, name="last_batches_by_user"),
    path("batches_table/", last_batches_table, name="last_batches_table"),
    path("batch/<int:pk>/", batch, name="batch"),
    path("batch/preview/", batch, name="batch_preview"),
    path("batch/<int:pk>/stop/", batch_stop, name="batch_stop"),
    path("batch/<int:pk>/restart/", batch_restart, name="batch_restart"),
    path("batch/<int:pk>/rerun/", batch_rerun, name="batch_rerun"),
    path("batch/<int:pk>/report/", batch_report, name="batch_report"),
    path("batch/<int:pk>/summary/", batch_summary, name="batch_summary"),
    path("batch/<int:pk>/commands/", batch_commands, name="batch_commands"),
    path("batch/new/", new_batch, name="new_batch"),
    path("batch/new/preview/", redirect_to_preview_last_batch, name="redirect_to_preview_last_batch"),
    path("batch/new/preview/<int:pk>/", preview_batch_pk, name="preview_batch_pk"),
    path(
        "batch/new/preview/<int:pk>/commands/",
        preview_batch_commands_pk,
        name="preview_batch_commands_pk",
    ),
    path("batch/new/preview/<int:pk>/allow_start/", batch_allow_start_pk, name="batch_allow_start_pk"),
    path("statistics/", statistics, name="statistics"),
    path("statistics/counters/", all_time_counters, name="statistics_all_time_counters"),
    path("statistics/plots/", plots, name="statistics_plots"),
    path("statistics/<str:username>/", statistics_user, name="statistics_user"),
    path("statistics/counters/<str:username>/", all_time_counters_user, name="statistics_all_time_counters_user"),
    path("statistics/plots/<str:username>/", plots_user, name="statistics_plots_user"),
    path("language/change/<str:code>/", language_change, name="language_change"),
]
