"""Django 1.0 admin interface declarations."""

from autotest.frontend import settings
from autotest.frontend.afe import model_logic, models
from django import forms
from django.contrib import admin


class SiteAdmin(admin.ModelAdmin):

    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super(SiteAdmin, self).formfield_for_dbfield(db_field, **kwargs)
        if (db_field.rel and
                issubclass(db_field.rel.to, model_logic.ModelWithInvalid)):
            model = db_field.rel.to
            field.choices = model.valid_objects.all().values_list(
                'id', model.name_field)
        return field


class ModelWithInvalidForm(forms.ModelForm):

    def validate_unique(self):
        # Don't validate name uniqueness if the duplicate model is invalid
        model = self.Meta.model
        filter_data = {
            model.name_field: self.cleaned_data[model.name_field],
            'invalid': True
        }
        needs_remove = bool(self.Meta.model.objects.filter(**filter_data))
        if needs_remove:
            name_field = self.fields.pop(model.name_field)
        super(ModelWithInvalidForm, self).validate_unique()
        if needs_remove:
            self.fields[model.name_field] = name_field


class AtomicGroupForm(ModelWithInvalidForm):

    class Meta:
        model = models.AtomicGroup


class AtomicGroupAdmin(SiteAdmin):
    list_display = ('name', 'description', 'max_number_of_machines')

    form = AtomicGroupForm

    def queryset(self, request):
        return models.AtomicGroup.valid_objects

admin.site.register(models.AtomicGroup, AtomicGroupAdmin)


class LabelForm(ModelWithInvalidForm):

    class Meta:
        model = models.Label


class LabelAdmin(SiteAdmin):
    list_display = ('name', 'atomic_group', 'kernel_config')
    # Avoid a bug with the admin interface showing a select box pointed at an
    # AtomicGroup when this field is intentionally NULL such that editing a
    # label via the admin UI unintentionally sets an atomicgroup.
    raw_id_fields = ('atomic_group',)

    form = LabelForm

    def queryset(self, request):
        return models.Label.valid_objects

admin.site.register(models.Label, LabelAdmin)


class UserAdmin(SiteAdmin):
    list_display = ('login', 'access_level')
    search_fields = ('login',)

admin.site.register(models.User, UserAdmin)


class HostForm(ModelWithInvalidForm):

    class Meta:
        model = models.Host


class HostAdmin(SiteAdmin):
    # TODO(showard) - showing platform requires a SQL query for
    # each row (since labels are many-to-many) - should we remove
    # it?
    list_display = ('hostname', 'platform', 'locked', 'status')
    list_filter = ('labels', 'locked', 'protection')
    search_fields = ('hostname', 'status')
    filter_horizontal = ('labels',)

    form = HostForm

    def queryset(self, request):
        return models.Host.valid_objects

admin.site.register(models.Host, HostAdmin)


class TestAdmin(SiteAdmin):
    fields = ('name', 'author', 'test_category', 'test_class',
              'test_time', 'sync_count', 'test_type', 'path',
              'dependencies', 'experimental', 'run_verify',
              'description')
    list_display = ('name', 'test_type', 'admin_description', 'sync_count')
    search_fields = ('name',)
    filter_horizontal = ('dependency_labels',)

admin.site.register(models.Test, TestAdmin)


class ProfilerAdmin(SiteAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

admin.site.register(models.Profiler, ProfilerAdmin)


class AclGroupAdmin(SiteAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    filter_horizontal = ('users', 'hosts')

    def queryset(self, request):
        return models.AclGroup.objects.exclude(name='Everyone')

    def save_model(self, request, obj, form, change):
        super(AclGroupAdmin, self).save_model(request, obj, form, change)
        _orig_save_m2m = form.save_m2m

        def save_m2m():
            _orig_save_m2m()
            obj.perform_after_save(change)

        form.save_m2m = save_m2m

admin.site.register(models.AclGroup, AclGroupAdmin)


class DroneSetForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(DroneSetForm, self).__init__(*args, **kwargs)
        drone_ids_used = set()
        for drone_set in models.DroneSet.objects.exclude(id=self.instance.id):
            drone_ids_used.update(drone_set.drones.values_list('id', flat=True))
        available_drones = models.Drone.objects.exclude(id__in=drone_ids_used)

        self.fields['drones'].widget.choices = [(drone.id, drone.hostname)
                                                for drone in available_drones]


class DroneSetAdmin(SiteAdmin):
    filter_horizontal = ('drones',)
    form = DroneSetForm

admin.site.register(models.DroneSet, DroneSetAdmin)

admin.site.register(models.Drone)


if settings.FULL_ADMIN:
    class JobAdmin(SiteAdmin):
        list_display = ('id', 'owner', 'name', 'control_type')
        filter_horizontal = ('dependency_labels',)

    admin.site.register(models.Job, JobAdmin)

    class IneligibleHostQueueAdmin(SiteAdmin):
        list_display = ('id', 'job', 'host')

    admin.site.register(models.IneligibleHostQueue, IneligibleHostQueueAdmin)

    class HostQueueEntryAdmin(SiteAdmin):
        list_display = ('id', 'job', 'host', 'status',
                        'meta_host')

    admin.site.register(models.HostQueueEntry, HostQueueEntryAdmin)

    admin.site.register(models.AbortedHostQueueEntry)
