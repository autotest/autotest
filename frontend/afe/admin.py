"""Django 1.0 admin interface declarations."""

from django.contrib import admin

from autotest_lib.frontend import settings
from autotest_lib.frontend.afe import model_logic, models


class AtomicGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'max_number_of_machines')

    def queryset(self, request):
        return models.AtomicGroup.valid_objects

admin.site.register(models.AtomicGroup, AtomicGroupAdmin)


class LabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'kernel_config')

    def queryset(self, request):
        return models.Label.valid_objects

admin.site.register(models.Label, LabelAdmin)


class UserAdmin(admin.ModelAdmin):
    list_display = ('login', 'access_level')
    search_fields = ('login',)

admin.site.register(models.User, UserAdmin)


class HostAdmin(admin.ModelAdmin):
    # TODO(showard) - showing platform requires a SQL query for
    # each row (since labels are many-to-many) - should we remove
    # it?
    list_display = ('hostname', 'platform', 'locked', 'status')
    list_filter = ('labels', 'locked', 'protection')
    search_fields = ('hostname', 'status')
    filter_horizontal = ('labels',)

    def queryset(self, request):
        return models.Host.valid_objects

admin.site.register(models.Host, HostAdmin)


class TestAdmin(admin.ModelAdmin):
    fields = ('name', 'author', 'test_category', 'test_class',
              'test_time', 'sync_count', 'test_type', 'path',
              'dependencies', 'experimental', 'run_verify',
              'description')
    list_display = ('name', 'test_type', 'description', 'sync_count')
    search_fields = ('name',)
    filter_horizontal = ('dependency_labels',)

admin.site.register(models.Test, TestAdmin)


class ProfilerAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

admin.site.register(models.Profiler, ProfilerAdmin)


class AclGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    filter_horizontal = ('users', 'hosts')

admin.site.register(models.AclGroup, AclGroupAdmin)


if settings.FULL_ADMIN:
    class JobAdmin(admin.ModelAdmin):
        list_display = ('id', 'owner', 'name', 'control_type')
        filter_horizontal = ('dependency_labels',)

    admin.site.register(models.Job, JobAdmin)

    class IneligibleHostQueueAdmin(admin.ModelAdmin):
        list_display = ('id', 'job', 'host')

    admin.site.register(models.IneligibleHostQueue, IneligibleHostQueueAdmin)

    class HostQueueEntryAdmin(admin.ModelAdmin):
        list_display = ('id', 'job', 'host', 'status',
                        'meta_host')

    admin.site.register(models.HostQueueEntry, HostQueueEntryAdmin)

    admin.site.register(models.AbortedHostQueueEntry)
