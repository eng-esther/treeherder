import decimal

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import exceptions, serializers

from treeherder.model.models import Repository
from treeherder.perf.models import (
    BackfillRecord,
    IssueTracker,
    PerformanceAlert,
    PerformanceAlertSummary,
    PerformanceBugTemplate,
    PerformanceDatum,
    PerformanceFramework,
    PerformanceSignature,
    PerformanceTag,
)
from treeherder.webapp.api.utils import to_timestamp


class OptionalBooleanField(serializers.BooleanField):
    def __init__(self, *args, **kwargs):
        kwargs['default'] = False
        super().__init__(*args, **kwargs)


class PerformanceDecimalField(serializers.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs['max_digits'] = 20
        kwargs['decimal_places'] = 2
        kwargs['coerce_to_string'] = False
        kwargs['allow_null'] = True
        super().__init__(*args, **kwargs)


class PerfCompareDecimalField(serializers.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs['max_digits'] = None
        kwargs['decimal_places'] = 2
        kwargs['coerce_to_string'] = False
        super().__init__(*args, **kwargs)


class TimestampField(serializers.Field):
    def to_representation(self, value):
        return to_timestamp(value.time)


class WordsField(serializers.CharField):
    def to_representation(self, obj):
        # if string's value is blank, just return nothing
        if isinstance(obj, str):
            return obj.split(' ')
        return []


class BackfillRecordSerializer(serializers.Serializer):
    context = serializers.JSONField()
    status = serializers.IntegerField()
    total_actions_triggered = serializers.IntegerField()
    total_backfills_failed = serializers.IntegerField()
    total_backfills_successful = serializers.IntegerField()
    total_backfills_in_progress = serializers.IntegerField()

    class Meta:
        model = BackfillRecord
        fields = (
            'alert',
            'context',
            'status',
            'total_actions_triggered',
            'total_backfills_failed',
            'total_backfills_successful',
            'total_backfills_in_progress',
        )


class PerformanceFrameworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceFramework
        fields = ['id', 'name']


class PerformanceSignatureSerializer(serializers.ModelSerializer):
    option_collection_hash = serializers.SlugRelatedField(
        read_only=True, slug_field="option_collection_hash", source="option_collection"
    )
    machine_platform = serializers.SlugRelatedField(
        read_only=True, slug_field="platform", source="platform"
    )
    tags = WordsField(read_only=True, allow_blank=True)
    extra_options = WordsField(read_only=True, allow_blank=True)
    measurement_unit = serializers.CharField(read_only=True)
    suite_public_name = serializers.CharField(read_only=True, required=False)
    test_public_name = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = PerformanceSignature
        fields = [
            'id',
            'framework_id',
            'signature_hash',
            'machine_platform',
            'suite',
            'test',
            'lower_is_better',
            'has_subtests',
            'option_collection_hash',
            'tags',
            'extra_options',
            'measurement_unit',
            'suite_public_name',
            'test_public_name',
        ]


class PerformanceAlertSerializer(serializers.ModelSerializer):
    series_signature = PerformanceSignatureSerializer(read_only=True)
    summary_id = serializers.SlugRelatedField(
        slug_field="id",
        source="summary",
        required=False,
        queryset=PerformanceAlertSummary.objects.all(),
    )
    related_summary_id = serializers.SlugRelatedField(
        slug_field="id",
        source="related_summary",
        allow_null=True,
        required=False,
        queryset=PerformanceAlertSummary.objects.all(),
    )
    classifier = serializers.SlugRelatedField(
        slug_field="username", allow_null=True, required=False, queryset=User.objects.all()
    )
    classifier_email = serializers.SerializerMethodField()
    backfill_record = BackfillRecordSerializer(read_only=True, allow_null=True)

    # Force `is_regression` to be an optional field, even when using PUT, since in
    # Django 2.1 BooleanField no longer has an implicit `blank=True` on the model.
    # TODO: Switch to using PATCH instead in the UI and the API tests.
    is_regression = serializers.BooleanField(required=False)

    # express quantities in terms of decimals to save space
    amount_abs = PerformanceDecimalField(read_only=True)
    amount_pct = PerformanceDecimalField(read_only=True)
    t_value = PerformanceDecimalField(read_only=True)
    prev_value = PerformanceDecimalField(read_only=True)
    new_value = PerformanceDecimalField(read_only=True)
    noise_profile = serializers.CharField(read_only=True)

    @transaction.atomic
    def update(self, instance, validated_data):
        # ensure the related summary, if set, has the same repository and
        # framework as the original summary
        related_summary = validated_data.get('related_summary')
        if related_summary:
            if (
                validated_data.get('status', instance.status) != PerformanceAlert.DOWNSTREAM
                and instance.summary.repository_id != related_summary.repository_id
            ):
                raise exceptions.ValidationError(
                    "New summary's repository ({}) does not match existing "
                    "summary's repository ({})".format(
                        related_summary.repository, instance.summary.framework
                    )
                )
            elif instance.summary.framework_id != related_summary.framework_id:
                raise exceptions.ValidationError(
                    "New summary's framework ({}) does not match existing "
                    "summary's framework ({})".format(
                        related_summary.framework, instance.summary.framework
                    )
                )

            status = validated_data.get('status')
            if status and status in PerformanceAlert.RELATIONAL_STATUS_IDS:
                # we've caught a downstream/reassignment: timestamp it
                related_summary.timestamp_first_triage().save()

        instance.timestamp_first_triage()

        return super().update(instance, validated_data)

    def get_classifier_email(self, performance_alert):
        return getattr(performance_alert.classifier, 'email', None)

    class Meta:
        model = PerformanceAlert
        fields = [
            'id',
            'status',
            'series_signature',
            'is_regression',
            'prev_value',
            'new_value',
            't_value',
            'amount_abs',
            'amount_pct',
            'summary_id',
            'related_summary_id',
            'manually_created',
            'classifier',
            'starred',
            'classifier_email',
            'backfill_record',
            'noise_profile',
        ]


class PerformanceTagSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)

    class Meta:
        model = PerformanceTag
        fields = ['id', 'name']


class PerformanceAlertSummarySerializer(serializers.ModelSerializer):
    alerts = PerformanceAlertSerializer(many=True, read_only=True)
    related_alerts = PerformanceAlertSerializer(many=True, read_only=True)
    performance_tags = serializers.SlugRelatedField(
        many=True, required=False, slug_field='name', queryset=PerformanceTag.objects.all()
    )
    repository = serializers.SlugRelatedField(read_only=True, slug_field='name')
    framework = serializers.SlugRelatedField(read_only=True, slug_field='id')
    revision = serializers.SlugRelatedField(read_only=True, slug_field='revision', source='push')
    push_timestamp = TimestampField(source='push', read_only=True)
    prev_push_revision = serializers.SlugRelatedField(
        read_only=True, slug_field='revision', source='prev_push'
    )
    assignee_username = serializers.SlugRelatedField(
        slug_field="username",
        source="assignee",
        allow_null=True,
        required=False,
        queryset=User.objects.all(),
    )
    assignee_email = serializers.SerializerMethodField()
    # marking these fields as readonly, the user should not be modifying them
    # (after the item is first created, where we don't use this serializer
    # class)
    prev_push_id = serializers.ReadOnlyField()
    push_id = serializers.ReadOnlyField()
    created = serializers.ReadOnlyField()

    def update(self, instance, validated_data):
        instance.timestamp_first_triage()
        return super().update(instance, validated_data)

    def get_assignee_email(self, performance_alert_summary):
        return getattr(performance_alert_summary.assignee, 'email', None)

    class Meta:
        model = PerformanceAlertSummary
        fields = [
            'id',
            'push_id',
            'prev_push_id',
            'created',
            'repository',
            'framework',
            'alerts',
            'related_alerts',
            'status',
            'bug_number',
            'bug_updated',
            'issue_tracker',
            'notes',
            'revision',
            'push_timestamp',
            'prev_push_revision',
            'assignee_username',
            'assignee_email',
            'performance_tags',
        ]


class PerformanceBugTemplateSerializer(serializers.ModelSerializer):
    framework = serializers.SlugRelatedField(read_only=True, slug_field='id')

    class Meta:
        model = PerformanceBugTemplate
        fields = [
            'framework',
            'keywords',
            'status_whiteboard',
            'default_component',
            'default_product',
            'cc_list',
            'text',
        ]


class IssueTrackerSerializer(serializers.ModelSerializer):
    text = serializers.CharField(read_only=True, source='name')
    issueTrackerUrl = serializers.URLField(read_only=True, source='task_base_url')

    class Meta:
        model = IssueTracker
        fields = ['id', 'text', 'issueTrackerUrl']


class PerformanceQueryParamsSerializer(serializers.Serializer):
    startday = serializers.DateTimeField(required=False, allow_null=True, default=None)
    endday = serializers.DateTimeField(required=False, allow_null=True, default=None)
    revision = serializers.CharField(required=False, allow_null=True, default=None)
    repository = serializers.CharField()
    framework = serializers.ListField(required=False, child=serializers.IntegerField(), default=[])
    interval = serializers.IntegerField(required=False, allow_null=True, default=None)
    parent_signature = serializers.CharField(required=False, allow_null=True, default=None)
    signature = serializers.CharField(required=False, allow_null=True, default=None)
    no_subtests = serializers.BooleanField(required=False)
    all_data = OptionalBooleanField()
    no_retriggers = OptionalBooleanField()

    def validate(self, data):
        if (
            data['revision'] is None
            and data['interval'] is None
            and (data['startday'] is None or data['endday'] is None)
        ):
            raise serializers.ValidationError(
                'Required: revision, startday and endday or interval.'
            )

        return data

    def validate_repository(self, repository):
        try:
            Repository.objects.get(name=repository)

        except ObjectDoesNotExist:
            raise serializers.ValidationError('{} does not exist.'.format(repository))

        return repository


class PerformanceDatumSerializer(serializers.ModelSerializer):
    revision = serializers.CharField(source='push__revision')

    class Meta:
        model = PerformanceDatum
        fields = ['job_id', 'id', 'value', 'push_timestamp', 'push_id', 'revision']


class PerformanceSummarySerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="platform__platform")
    values = serializers.ListField(
        child=serializers.DecimalField(
            rounding=decimal.ROUND_HALF_EVEN,
            decimal_places=2,
            max_digits=None,
            coerce_to_string=False,
        ),
        default=[],
    )
    name = serializers.SerializerMethodField()
    suite = serializers.CharField()
    parent_signature = serializers.IntegerField(source="parent_signature_id")
    signature_id = serializers.IntegerField(source="id")
    job_ids = serializers.ListField(child=serializers.IntegerField(), default=[])
    data = PerformanceDatumSerializer(read_only=True, many=True, default=[])
    repository_name = serializers.CharField()

    class Meta:
        model = PerformanceSignature
        fields = [
            'signature_id',
            'framework_id',
            'signature_hash',
            'platform',
            'test',
            'suite',
            'lower_is_better',
            'has_subtests',
            'tags',
            'values',
            'name',
            'parent_signature',
            'job_ids',
            'repository_name',
            'repository_id',
            'data',
            'measurement_unit',
            'application',
        ]

    def get_name(self, value):
        test = value['test']
        suite = value['suite']
        test_suite = suite if test == '' or test == suite else '{} {}'.format(suite, test)
        return '{} {} {}'.format(test_suite, value['option_name'], value['extra_options'])


class PerfCompareResultsQueryParamsSerializer(serializers.Serializer):
    base_revision = serializers.CharField(required=False, allow_null=True, default=None)
    new_revision = serializers.CharField(required=False, allow_null=True, default=None)
    base_repository = serializers.CharField()
    new_repository = serializers.CharField()
    framework = serializers.IntegerField(required=False, allow_null=True, default=None)
    interval = serializers.IntegerField(required=False, allow_null=True, default=None)
    no_subtests = serializers.BooleanField(required=False)

    def validate(self, data):
        if (
            data['base_revision'] is None
            and data['new_revision'] is None
            and data['interval'] is None
        ):
            raise serializers.ValidationError('Required: base_revision, new_revision and interval.')

        try:
            Repository.objects.get(name=data['base_repository'])
            Repository.objects.get(name=data['new_repository'])
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                '{} or {} does not exist.'.format(data['base_repository'], data['new_repository'])
            )

        return data


class PerfCompareResultsSerializer(serializers.ModelSerializer):
    is_empty = serializers.BooleanField()
    is_complete = serializers.BooleanField()
    platform = serializers.CharField()
    header_name = serializers.CharField()
    base_repository_name = serializers.CharField()
    new_repository_name = serializers.CharField()
    base_measurement_unit = serializers.CharField()
    new_measurement_unit = serializers.CharField()
    base_retriggerable_job_ids = serializers.ListField(child=serializers.IntegerField(), default=[])
    new_retriggerable_job_ids = serializers.ListField(child=serializers.IntegerField(), default=[])
    option_name = serializers.CharField()
    base_runs = serializers.ListField(
        child=PerfCompareDecimalField(),
        default=[],
    )
    new_runs = serializers.ListField(
        child=PerfCompareDecimalField(),
        default=[],
    )
    base_avg_value = PerfCompareDecimalField()
    new_avg_value = PerfCompareDecimalField()
    base_stddev = PerfCompareDecimalField()
    new_stddev = PerfCompareDecimalField()
    base_stddev_pct = PerfCompareDecimalField()
    new_stddev_pct = PerfCompareDecimalField()
    confidence = PerfCompareDecimalField()
    confidence_text = serializers.CharField()
    confidence_text_long = serializers.CharField()
    is_improvement = serializers.BooleanField(required=False)
    t_value_confidence = serializers.IntegerField(required=False, allow_null=True, default=None)
    t_value_care_min = serializers.IntegerField(required=False, allow_null=True, default=None)
    delta_value = PerfCompareDecimalField()
    delta_percentage = PerfCompareDecimalField()
    magnitude = PerfCompareDecimalField()
    new_is_better = OptionalBooleanField()

    class Meta:
        model = PerformanceSignature
        fields = [
            'framework_id',
            'platform',
            'suite',
            'is_empty',
            'header_name',
            'base_repository_name',
            'new_repository_name',
            'is_complete',
            'base_measurement_unit',
            'new_measurement_unit',
            'base_retriggerable_job_ids',
            'new_retriggerable_job_ids',
            'base_runs',
            'new_runs',
            'base_avg_value',
            'new_avg_value',
            'test',
            'option_name',
            'extra_options',
            'base_stddev',
            'new_stddev',
            'base_stddev_pct',
            'new_stddev_pct',
            'confidence',
            'confidence_text',
            'confidence_text_long',
            'is_improvement',
            't_value_confidence',
            't_value_care_min',
            'delta_value',
            'delta_percentage',
            'magnitude',
            'new_is_better',
        ]


class TestSuiteHealthParamsSerializer(serializers.Serializer):
    framework = serializers.CharField(default=None)


class CommaSeparatedField(serializers.Field):
    def to_representation(self, value):
        return value.split(',')


class TestSuiteHealthSerializer(serializers.Serializer):
    test = serializers.CharField()
    suite = serializers.CharField()
    platforms = CommaSeparatedField()
    repositories = CommaSeparatedField()
    total_alerts = serializers.IntegerField()
    total_regressions = serializers.IntegerField()
    total_untriaged = serializers.IntegerField()
