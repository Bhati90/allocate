from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import forms
from decimal import Decimal

from .models import (
    ActivityCatalog, Cluster, Farmer, Plot, ClusterActivityRate,
    Job, JobActivity, JobBooking, FarmerPayment,
    ActivityScheduleRule, ClusterActivityScheduleRule,
    Mukkadam, ClusterMukkadamActivityRate, MukkadamActivityRate,
    MukkadamAvailability, Allocation, MukkadamPayment,
    ActivityLogTender, ExtraWorker, Leave,
    AllocationChangeLogTender, PaymentChangeLog,
    WebhookLog, SystemConfiguration, APISync,
)


# ============================================================================
# CUSTOM ADMIN SITE
# ============================================================================

class KisanmitraAdminSite(admin.AdminSite):
    site_header = "🌾 Kisanmitra Farm Planner Admin"
    site_title = "Kisanmitra Admin"
    index_title = "Operations Dashboard"


# ============================================================================
# INLINES
# ============================================================================

class ClusterActivityRateInline(admin.TabularInline):
    model = ClusterActivityRate
    extra = 1
    fields = ('activity', 'rate_per_acre')
    autocomplete_fields = ['activity']


class ClusterMukkadamActivityRateInline(admin.TabularInline):
    model = ClusterMukkadamActivityRate
    extra = 1
    fields = ('activity', 'rate_per_acre', 'productivity_per_worker')
    autocomplete_fields = ['activity']


class ClusterActivityScheduleRuleInline(admin.TabularInline):
    model = ClusterActivityScheduleRule
    extra = 1
    fields = ('activity', 'gap_days')
    autocomplete_fields = ['activity']


class PlotInline(admin.TabularInline):
    model = Plot
    extra = 0
    fields = ('name', 'area_acres', 'crop_name', 'variety', 'pruning_date', 'plot_code')
    show_change_link = True


class JobActivityInline(admin.TabularInline):
    model = JobActivity
    extra = 0
    fields = (
        'activity', 'plot', 'total_area', 'allocated_area', 'remaining_area',
        'scheduled_date', 'rate_per_acre', 'total_price', 'allocation_status'
    )
    readonly_fields = ('remaining_area', 'total_price', 'allocation_status')
    show_change_link = True
    autocomplete_fields = ['activity']


class JobBookingInline(admin.StackedInline):
    model = JobBooking
    extra = 0
    fields = ('booking_id', 'status', 'total_amount', 'advance_paid', 'balance', 'assignee_number')
    readonly_fields = ('booking_id',)


class FarmerPaymentInline(admin.TabularInline):
    model = FarmerPayment
    extra = 0
    fields = ('payment_id', 'mode', 'amount', 'paid_status', 'paid_at', 'notes')
    readonly_fields = ('payment_id',)


class MukkadamActivityRateInline(admin.TabularInline):
    model = MukkadamActivityRate
    extra = 1
    fields = ('activity', 'rate_per_acre', 'productivity_per_worker', 'is_active')
    autocomplete_fields = ['activity']


class MukkadamAvailabilityInline(admin.TabularInline):
    model = MukkadamAvailability
    extra = 0
    fields = ('date', 'available_crew_size', 'is_available', 'is_on_leave', 'allocated_workers', 'remaining_capacity', 'notes')
    readonly_fields = ('remaining_capacity',)


class AllocationInline(admin.TabularInline):
    model = Allocation
    extra = 0
    fields = ('mukkadam', 'allocated_date', 'allocated_area', 'allocated_workers', 'farmer_rate', 'mukkadam_rate', 'status')
    show_change_link = True
    autocomplete_fields = ['mukkadam']


class AllocationChangeLogInline(admin.TabularInline):
    model = AllocationChangeLogTender
    extra = 0
    readonly_fields = ('change_type', 'field_changed', 'old_value', 'new_value', 'changed_by', 'changed_at')
    can_delete = False


class LeaveInline(admin.TabularInline):
    model = Leave
    extra = 1
    fields = ('date', 'leave_type', 'crew_on_leave', 'reason', 'is_active')


# ============================================================================
# MASTER DATA ADMIN
# ============================================================================

@admin.register(ActivityCatalog)
class ActivityCatalogAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'activity_type', 'default_rate_per_acre',
        'estimated_workers_per_acre', 'default_gap_days',
        'is_strict_badge', 'source', 'created_at'
    )
    list_filter = ('is_strict', 'source', 'activity_type')
    search_fields = ('name', 'activity_type')
    list_editable = ('default_rate_per_acre', 'estimated_workers_per_acre', 'default_gap_days')
    ordering = ('name',)
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'activity_type', 'source')
        }),
        ('Rates & Workers', {
            'fields': ('default_rate_per_acre', 'estimated_workers_per_acre')
        }),
        ('Scheduling', {
            'fields': ('default_gap_days', 'is_strict')
        }),
    )

    def is_strict_badge(self, obj):
        if obj.is_strict:
            return format_html('<span style="color:red;font-weight:bold;">⚠ Strict</span>')
        return format_html('<span style="color:green;">Normal</span>')
    is_strict_badge.short_description = 'Type'


@admin.register(ActivityScheduleRule)
class ActivityScheduleRuleAdmin(admin.ModelAdmin):
    list_display = ('activity', 'gap_days', 'phase_order')
    list_editable = ('gap_days', 'phase_order')
    search_fields = ('activity__name',)
    autocomplete_fields = ['activity']


# ============================================================================
# CLUSTER ADMIN
# ============================================================================

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'district_display', 'taluka_display',
        'farmer_count', 'mukkadam_count', 'job_count', 'date_range_display'
    )
    search_fields = ('name', 'districts', 'talukas', 'villages')
    filter_horizontal = ()
    fieldsets = (
        ('Cluster Identity', {
            'fields': ('name', 'note')
        }),
        ('Geography', {
            'fields': (
                'state_code',
                'district_codes', 'districts',
                'taluka_codes', 'talukas',
                'village_codes', 'villages',
            )
        }),
    )
    inlines = [
        ClusterActivityRateInline,
        ClusterMukkadamActivityRateInline,
        ClusterActivityScheduleRuleInline,
    ]

    def district_display(self, obj):
        return ', '.join(obj.districts[:3]) if obj.districts else '-'
    district_display.short_description = 'Districts'

    def taluka_display(self, obj):
        return ', '.join(obj.talukas[:3]) if obj.talukas else '-'
    taluka_display.short_description = 'Talukas'

    def farmer_count(self, obj):
        count = obj.farmers.count()
        url = reverse('admin:tender_farmer_changelist') + f'?clusters__id__exact={obj.pk}'
        return format_html('<a href="{}">{} farmers</a>', url, count)
    farmer_count.short_description = 'Farmers'

    def mukkadam_count(self, obj):
        return obj.mukkadams.count()
    mukkadam_count.short_description = 'Mukkadams'

    def job_count(self, obj):
        return obj.jobs.count()
    job_count.short_description = 'Jobs'

    def date_range_display(self, obj):
        dr = obj.date_range
        if dr['start_date'] and dr['end_date']:
            return f"{dr['start_date']} → {dr['end_date']}"
        return '-'
    date_range_display.short_description = 'Activity Range'


@admin.register(ClusterActivityRate)
class ClusterActivityRateAdmin(admin.ModelAdmin):
    list_display = ('cluster', 'activity', 'rate_per_acre', 'updated_at')
    list_filter = ('cluster',)
    search_fields = ('cluster__name', 'activity__name')
    list_editable = ('rate_per_acre',)
    autocomplete_fields = ['cluster', 'activity']


@admin.register(ClusterActivityScheduleRule)
class ClusterActivityScheduleRuleAdmin(admin.ModelAdmin):
    list_display = ('cluster', 'activity', 'gap_days')
    list_filter = ('cluster',)
    search_fields = ('cluster__name', 'activity__name')
    list_editable = ('gap_days',)
    autocomplete_fields = ['cluster', 'activity']


# ============================================================================
# FARMER & PLOT ADMIN
# ============================================================================

@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = (
        'farmer_id', 'farmer_name', 'phone_number',
        'cluster_list', 'location', 'plot_count', 'job_count', 'last_synced'
    )
    list_filter = ('clusters',)
    search_fields = ('farmer_id', 'farmer_name', 'phone_number', 'location')
    filter_horizontal = ('clusters',)
    readonly_fields = ('last_synced',)
    inlines = [PlotInline]
    fieldsets = (
        ('Identity', {
            'fields': ('farmer_id', 'farmer_name', 'phone_number')
        }),
        ('Assignment', {
            'fields': ('clusters', 'location')
        }),
        ('Location Coordinates', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Sync Info', {
            'fields': ('last_synced',),
            'classes': ('collapse',)
        }),
    )

    def cluster_list(self, obj):
        return ', '.join([c.name for c in obj.clusters.all()]) or '-'
    cluster_list.short_description = 'Clusters'

    def plot_count(self, obj):
        return obj.plots.count()
    plot_count.short_description = 'Plots'

    def job_count(self, obj):
        return obj.jobs.count()
    job_count.short_description = 'Jobs'


@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display = (
        'farmer', 'name', 'area_acres', 'crop_name',
        'variety', 'pruning_date', 'cluster_list', 'plot_code'
    )
    list_filter = ('clusters', 'crop_name')
    search_fields = ('farmer__farmer_name', 'name', 'crop_name', 'variety', 'plot_code')
    filter_horizontal = ('clusters',)
    autocomplete_fields = ['farmer']
    fieldsets = (
        ('Basic Info', {
            'fields': ('farmer', 'name', 'area_acres', 'plot_code')
        }),
        ('Crop Details', {
            'fields': ('crop_name', 'variety', 'pruning_date')
        }),
        ('Cluster Assignment', {
            'fields': ('clusters',)
        }),
        ('Location', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
    )

    def cluster_list(self, obj):
        return ', '.join([c.name for c in obj.clusters.all()]) or '-'
    cluster_list.short_description = 'Clusters'


# ============================================================================
# JOB ADMIN
# ============================================================================

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'job_id', 'farmer', 'crop_name', 'status_badge',
        'priority_badge', 'cluster_list', 'scheduled_date',
        'total_activities_amount', 'payment_status', 'booking_type', 'updated_at'
    )
    list_filter = (
        'status', 'priority', 'payment_status', 'booking_type',
        'is_field_verified', 'is_complex', 'clusters'
    )
    search_fields = ('job_id', 'work_id', 'farmer__farmer_name', 'farmer__phone_number')
    filter_horizontal = ('clusters',)
    readonly_fields = ('created_at', 'updated_at', 'last_synced')
    date_hierarchy = 'scheduled_date'
    autocomplete_fields = ['farmer', 'plot']
    inlines = [JobActivityInline, JobBookingInline]

    fieldsets = (
        ('Job Identity', {
            'fields': ('job_id', 'work_id', 'booking_type', 'farmer', 'plot')
        }),
        ('Crop Details', {
            'fields': ('crop_name', 'variety')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'payment_status')
        }),
        ('Scheduling', {
            'fields': ('scheduled_date', 'completed_date')
        }),
        ('Financials', {
            'fields': ('booking_amount', 'total_activities_amount')
        }),
        ('Cluster Assignment', {
            'fields': ('clusters',)
        }),
        ('Flags', {
            'fields': ('is_field_verified', 'is_complex'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('activity_notes', 'internal_notes', 'point_of_contact'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_synced'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'scheduled': '#3b82f6',
            'in_progress': '#8b5cf6',
            'completed': '#10b981',
            'cancelled': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def priority_badge(self, obj):
        colors = {'LOW': '#6b7280', 'MEDIUM': '#3b82f6', 'HIGH': '#f59e0b', 'URGENT': '#ef4444'}
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color, obj.priority
        )
    priority_badge.short_description = 'Priority'

    def cluster_list(self, obj):
        return ', '.join([c.name for c in obj.clusters.all()]) or '-'
    cluster_list.short_description = 'Clusters'


@admin.register(JobActivity)
class JobActivityAdmin(admin.ModelAdmin):
    list_display = (
        'job', 'activity', 'plot', 'total_area',
        'allocated_area', 'remaining_area', 'scheduled_date',
        'allocation_status_badge', 'rate_per_acre', 'subtotal',
        'is_strict', 'is_lost'
    )
    list_filter = (
        'allocation_status', 'is_strict', 'is_fully_allocated',
        'is_lost', 'is_manually_edited', 'activity'
    )
    search_fields = ('job__job_id', 'job__farmer__farmer_name', 'activity__name')
    readonly_fields = ('remaining_area', 'total_price', 'subtotal', 'is_fully_allocated', 'allocation_status', 'created_at', 'updated_at')
    date_hierarchy = 'scheduled_date'
    autocomplete_fields = ['job', 'activity', 'plot']
    inlines = [AllocationInline]

    fieldsets = (
        ('Job & Activity', {
            'fields': ('job', 'activity', 'plot', 'api_activity_id')
        }),
        ('Area', {
            'fields': ('total_area', 'allocated_area', 'remaining_area', 'crop_bundles')
        }),
        ('Schedule', {
            'fields': ('scheduled_date', 'scheduled_time', 'estimated_workers')
        }),
        ('Pricing', {
            'fields': ('rate_per_acre', 'total_price', 'transport_cost', 'other_cost', 'subtotal')
        }),
        ('Status', {
            'fields': ('allocation_status', 'is_fully_allocated', 'is_strict', 'is_manually_edited')
        }),
        ('Lost', {
            'fields': ('is_lost', 'lost_reason'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('location',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def allocation_status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'partially_allocated': '#3b82f6',
            'fully_allocated': '#10b981',
            'in_progress': '#8b5cf6',
            'completed': '#6b7280',
        }
        color = colors.get(obj.allocation_status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_allocation_status_display()
        )
    allocation_status_badge.short_description = 'Alloc. Status'

    def is_strictly_allocated(self, obj):
        return obj.is_strict
    is_strictly_allocated.boolean = True
    is_strictly_allocated.short_description = 'Strict'


@admin.register(JobBooking)
class JobBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'job', 'status', 'total_amount', 'advance_paid', 'balance', 'assignee_number')
    list_filter = ('status',)
    search_fields = ('booking_id', 'job__job_id', 'job__farmer__farmer_name', 'assignee_number')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [FarmerPaymentInline]
    autocomplete_fields = ['job']


@admin.register(FarmerPayment)
class FarmerPaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'booking', 'mode', 'amount', 'paid_status', 'paid_at', 'created_by')
    list_filter = ('mode', 'paid_status')
    search_fields = ('payment_id', 'booking__job__job_id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'paid_at'


# ============================================================================
# MUKKADAM ADMIN
# ============================================================================

@admin.register(Mukkadam)
class MukkadamAdmin(admin.ModelAdmin):
    list_display = (
        'mukkadam_id', 'mukkadam_name', 'mobile_numbers',
        'cluster_list', 'crew_size', 'max_crew_capacity',
        'efficiency', 'is_permanent', 'district', 'taluka', 'village'
    )
    list_filter = ('is_permanent', 'clusters', 'work_mode', 'district')
    search_fields = ('mukkadam_name', 'mobile_numbers', 'village', 'taluka', 'district')
    filter_horizontal = ('clusters',)
    readonly_fields = ('created_at', 'updated_at', 'last_synced')
    inlines = [MukkadamActivityRateInline, MukkadamAvailabilityInline, LeaveInline]

    fieldsets = (
        ('Identity', {
            'fields': ('mukkadam_id', 'mukkadam_name', 'mobile_numbers', 'is_permanent')
        }),
        ('Cluster Assignment', {
            'fields': ('clusters',)
        }),
        ('Crew', {
            'fields': ('crew_size', 'max_crew_capacity', 'efficiency', 'has_smartphone', 'work_mode')
        }),
        ('Availability', {
            'fields': ('start_date', 'end_date')
        }),
        ('Location', {
            'fields': (
                'state', 'state_code',
                'district', 'district_code',
                'taluka', 'taluka_code',
                'village', 'village_code',
                'current_latitude', 'current_longitude',
            ),
            'classes': ('collapse',)
        }),
        ('Rate Cards (API Data)', {
            'fields': ('rate_card', 'tender_activities'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_synced'),
            'classes': ('collapse',)
        }),
    )

    def cluster_list(self, obj):
        return ', '.join([c.name for c in obj.clusters.all()]) or '-'
    cluster_list.short_description = 'Clusters'


@admin.register(MukkadamActivityRate)
class MukkadamActivityRateAdmin(admin.ModelAdmin):
    list_display = ('mukkadam', 'activity', 'rate_per_acre', 'productivity_per_worker', 'is_active')
    list_filter = ('is_active', 'activity')
    search_fields = ('mukkadam__mukkadam_name', 'activity__name')
    list_editable = ('rate_per_acre', 'productivity_per_worker', 'is_active')
    autocomplete_fields = ['mukkadam', 'activity']


@admin.register(ClusterMukkadamActivityRate)
class ClusterMukkadamActivityRateAdmin(admin.ModelAdmin):
    list_display = ('cluster', 'activity', 'rate_per_acre', 'productivity_per_worker', 'updated_at')
    list_filter = ('cluster',)
    search_fields = ('cluster__name', 'activity__name')
    list_editable = ('rate_per_acre', 'productivity_per_worker')
    autocomplete_fields = ['cluster', 'activity']


@admin.register(MukkadamAvailability)
class MukkadamAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        'mukkadam', 'date', 'available_crew_size',
        'allocated_workers', 'remaining_capacity',
        'is_available', 'is_on_leave', 'is_manually_set'
    )
    list_filter = ('is_available', 'is_on_leave', 'is_manually_set', 'mukkadam__clusters')
    search_fields = ('mukkadam__mukkadam_name',)
    date_hierarchy = 'date'
    list_editable = ('available_crew_size', 'is_available', 'is_on_leave')
    readonly_fields = ('remaining_capacity', 'created_at', 'updated_at')
    autocomplete_fields = ['mukkadam']


@admin.register(ExtraWorker)
class ExtraWorkerAdmin(admin.ModelAdmin):
    list_display = ('mukkadam', 'date', 'workers', 'note')
    list_filter = ('date',)
    search_fields = ('mukkadam__mukkadam_name',)
    date_hierarchy = 'date'
    list_editable = ('workers',)
    autocomplete_fields = ['mukkadam']


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = (
        'leave_type', 'date', 'mukkadam', 'cluster',
        'crew_on_leave', 'reason', 'is_active'
    )
    list_filter = ('leave_type', 'is_active', 'cluster')
    search_fields = ('mukkadam__mukkadam_name', 'reason')
    date_hierarchy = 'date'
    list_editable = ('is_active', 'crew_on_leave')
    autocomplete_fields = ['mukkadam', 'cluster']
    fieldsets = (
        ('Leave Details', {
            'fields': ('leave_type', 'date', 'mukkadam', 'cluster')
        }),
        ('Info', {
            'fields': ('crew_on_leave', 'reason', 'is_active')
        }),
    )


# ============================================================================
# ALLOCATION ADMIN
# ============================================================================

@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'job_activity', 'mukkadam', 'cluster',
        'allocated_date', 'allocated_area', 'allocated_workers',
        'farmer_rate', 'mukkadam_rate', 'profit_display', 'status_badge'
    )
    list_filter = ('status', 'cluster', 'allocated_date')
    search_fields = (
        'job_activity__job__job_id',
        'job_activity__activity__name',
        'mukkadam__mukkadam_name'
    )
    readonly_fields = ('farmer_amount', 'mukkadam_amount', 'profit', 'efficiency_score', 'created_at', 'updated_at')
    date_hierarchy = 'allocated_date'
    autocomplete_fields = ['job_activity', 'mukkadam', 'cluster']
    inlines = [AllocationChangeLogInline]

    fieldsets = (
        ('Core Assignment', {
            'fields': ('job_activity', 'mukkadam', 'cluster', 'allocated_date')
        }),
        ('Allocation Details', {
            'fields': ('allocated_area', 'allocated_workers')
        }),
        ('Pricing', {
            'fields': ('farmer_rate', 'mukkadam_rate', 'farmer_amount', 'mukkadam_amount', 'profit')
        }),
        ('Status & Performance', {
            'fields': ('status', 'actual_workers', 'actual_area_completed', 'efficiency_score')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time'),
            'classes': ('collapse',)
        }),
        ('Notes & Audit', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def profit_display(self, obj):
        color = 'green' if obj.profit >= 0 else 'red'
        return format_html(
            '<span style="color:{};font-weight:bold;">₹{}</span>',
            color, obj.profit
        )
    profit_display.short_description = 'Profit'

    def status_badge(self, obj):
        colors = {
            'scheduled': '#3b82f6',
            'in_progress': '#8b5cf6',
            'completed': '#10b981',
            'cancelled': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(MukkadamPayment)
class MukkadamPaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'mukkadam', 'mode', 'amount', 'paid_at', 'created_by')
    list_filter = ('mode',)
    search_fields = ('payment_id', 'mukkadam__mukkadam_name')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('allocations',)
    date_hierarchy = 'paid_at'
    autocomplete_fields = ['mukkadam']


# ============================================================================
# LOGS & AUDIT ADMIN
# ============================================================================

@admin.register(ActivityLogTender)
class ActivityLogTenderAdmin(admin.ModelAdmin):
    list_display = ('action', 'job', 'job_activity', 'performed_by', 'created_at')
    list_filter = ('action',)
    search_fields = ('job__job_id',)
    readonly_fields = ('action', 'job', 'job_activity', 'performed_by', 'details', 'created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AllocationChangeLogTender)
class AllocationChangeLogTenderAdmin(admin.ModelAdmin):
    list_display = ('allocation', 'change_type', 'field_changed', 'old_value', 'new_value', 'changed_by', 'changed_at')
    list_filter = ('change_type',)
    search_fields = ('allocation__job_activity__job__job_id',)
    readonly_fields = ('allocation', 'change_type', 'field_changed', 'old_value', 'new_value',
                       'change_reason', 'changed_by', 'changed_at', 'allocation_snapshot')
    date_hierarchy = 'changed_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PaymentChangeLog)
class PaymentChangeLogAdmin(admin.ModelAdmin):
    list_display = ('payment_type', 'change_type', 'field_changed', 'old_value', 'new_value', 'changed_by', 'changed_at')
    list_filter = ('payment_type', 'change_type')
    readonly_fields = ('payment_type', 'farmer_payment', 'mukkadam_payment', 'change_type',
                       'field_changed', 'old_value', 'new_value', 'change_reason',
                       'changed_by', 'changed_at', 'payment_snapshot')
    date_hierarchy = 'changed_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'status_badge', 'farmer_id', 'job_id',
        'cluster_matched', 'activities_processed', 'activities_failed',
        'plots_created', 'error_type', 'created_at'
    )
    list_filter = ('status', 'cluster_matched')
    search_fields = ('farmer_id', 'job_id', 'error_type', 'error_message')
    readonly_fields = (
        'webhook_data', 'status', 'error_type', 'error_message',
        'farmer_id', 'job_id', 'cluster_matched', 'cluster_id',
        'activities_processed', 'activities_failed', 'plots_created', 'created_at'
    )
    date_hierarchy = 'created_at'

    def status_badge(self, obj):
        colors = {'success': '#10b981', 'partial': '#f59e0b', 'failed': '#ef4444'}
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ============================================================================
# SYSTEM CONFIG ADMIN
# ============================================================================

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at', 'updated_by')
    search_fields = ('key', 'description')
    readonly_fields = ('updated_at',)


@admin.register(APISync)
class APISyncAdmin(admin.ModelAdmin):
    list_display = ('sync_type', 'status_badge', 'records_synced', 'last_sync_at', 'error_message')
    list_filter = ('sync_type', 'status')
    readonly_fields = ('sync_type', 'last_sync_at', 'status', 'records_synced', 'error_message')
    date_hierarchy = 'last_sync_at'

    def status_badge(self, obj):
        colors = {'success': '#10b981', 'partial': '#f59e0b', 'failed': '#ef4444'}
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False