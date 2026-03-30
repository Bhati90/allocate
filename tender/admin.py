from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.db import models
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import forms
from decimal import Decimal

from .models import (UserProfile,
    ActivityCatalog, Cluster, Farmer, Plot, ClusterActivityRate,MukkadamLedgerEntry,
    ClusterMukkadamAssignment, Job, JobActivity, JobBooking, FarmerPayment,
    ActivityScheduleRule, ClusterActivityScheduleRule,
    Mukkadam, ClusterMukkadamActivityRate, MukkadamActivityRate,
    MukkadamAvailability, Allocation, MukkadamPayment,
    ActivityLogTender, ExtraWorker, Leave,
    AllocationChangeLogTender, PaymentChangeLog,
    WebhookLog, SystemConfiguration, APISync,
    MukkadamWeeklyPayment, MukkadamMiscCost, MukkadamJobSettlement,
)


from django.contrib import admin
from .models import FarmerBillWebhookLog

# -----------------------------
# User Profile Admin
# -----------------------------
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'full_name',
        'mobile_number',
        'role',
        'is_mobile_verified',
        'created_at'
    )
    list_filter = ('role', 'is_mobile_verified', 'created_at')
    search_fields = ('mobile_number', 'full_name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


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
        'activity', 'plot', 'api_activity_id',
        'total_area', 'allocated_area', 'remaining_area',
        'scheduled_date', 'rate_per_acre', 'total_price',
        'allocation_status', 'is_strict', 'is_lost',
        'is_manually_moved', 'is_manually_edited', 'source',
    )
    readonly_fields = ('remaining_area', 'total_price', 'allocation_status')
    show_change_link = True
    autocomplete_fields = ['activity', 'plot']



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

    def has_add_permission(self, request, obj=None):
        return False


class LeaveInline(admin.TabularInline):
    model = Leave
    extra = 1
    fields = ('date', 'leave_type', 'crew_on_leave', 'reason', 'is_active')


class ClusterMukkadamAssignmentInline(admin.TabularInline):
    model = ClusterMukkadamAssignment
    extra = 1
    fields = (
        'cluster', 'transport_price', 'advance_amount', 'advance_is_manual',
        'weekly_payment_day', 'total_weekly_payments', 'is_active', 'joined_at'
    )
    readonly_fields = ('total_weekly_payments', 'joined_at')
    autocomplete_fields = ['cluster']


class MukkadamWeeklyPaymentInline(admin.TabularInline):
    model = MukkadamWeeklyPayment
    extra = 1
    fields = ('payment_date', 'amount', 'crew_size_on_date', 'is_auto_generated', 'notes')
    readonly_fields = ('created_at',)


class MukkadamMiscCostInline(admin.TabularInline):
    model = MukkadamMiscCost
    extra = 1
    fields = ('job', 'amount', 'reason', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['job']


class MukkadamJobSettlementInline(admin.TabularInline):
    model = MukkadamJobSettlement
    extra = 0
    fields = ('job', 'cluster', 'gross_amount', 'advance_deducted', 'weekly_payments_deducted', 'credit_carried_forward', 'net_payable', 'status')
    readonly_fields = ('gross_amount', 'net_payable', 'calculated_at')
    show_change_link = True
    autocomplete_fields = ['job', 'cluster']


# ============================================================================
# ACTIVITY CATALOG
# ============================================================================


@admin.register(ActivityCatalog)
class ActivityCatalogAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "activity_type",
        "default_rate_per_acre",
        "default_productivity_per_worker",
        "estimated_workers_per_acre",
        "default_gap_days",
        "is_strict",
        "source",
        "updated_at",
    ]
    list_editable = [
        "default_rate_per_acre",
        "default_productivity_per_worker",
        "estimated_workers_per_acre",
        "default_gap_days",
        "is_strict",
    ]
    list_filter = ["activity_type", "is_strict", "source"]
    search_fields = ["name", "activity_type"]
    ordering = ["name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "activity_type", "source", "is_strict"),
        }),
        ("Rates & Productivity", {
            "description": (
                "GLOBAL defaults — used when no cluster-level override exists. "
                "Override per cluster via ClusterMukkadamActivityRate."
            ),
            "fields": (
                "default_rate_per_acre",
                "default_productivity_per_worker",
                "estimated_workers_per_acre",
            ),
        }),
        ("Scheduling", {
            "fields": ("default_gap_days",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )



@admin.register(ActivityScheduleRule)
class ActivityScheduleRuleAdmin(admin.ModelAdmin):
    list_display = ('activity', 'gap_days', 'phase_order')
    list_editable = ('gap_days', 'phase_order')
    search_fields = ('activity__name',)
    autocomplete_fields = ['activity']


# ============================================================================
# CLUSTER
# ============================================================================

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'district_display', 'taluka_display',
        'farmer_count', 'mukkadam_count', 'job_count', 'date_range_display'
    )
    search_fields = ('name', 'districts', 'talukas', 'villages')
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
        count = obj.mukkadams.count()
        url = reverse('admin:tender_mukkadam_changelist') + f'?clusters__id__exact={obj.pk}'
        return format_html('<a href="{}">{} mukkadams</a>', url, count)
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
# FARMER & PLOT
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

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'job_id', 'farmer', 'crop_name', 'status_badge',
        'priority_badge', 'cluster_list', 'scheduled_date',
        'total_activities_amount', 'payment_status', 'booking_type',
        'activity_count', 'pending_activities', 'updated_at'
    )
    list_filter = (
        'status', 'priority', 'payment_status', 'booking_type',
        'is_field_verified', 'is_complex', 'clusters',
        'activities__allocation_status',   # filter by activity status
        'activities__activity',            # filter by activity type
    )
    search_fields = (
        'job_id', 'work_id',
        'farmer__farmer_name', 'farmer__phone_number',
        'activities__activity__name',      # search by activity name
        'activities__api_activity_id',     # search by api activity id
    )
    filter_horizontal = ('clusters',)
    readonly_fields = ('created_at', 'updated_at', 'last_synced', 'activity_summary')
    date_hierarchy = 'scheduled_date'
    autocomplete_fields = ['farmer', 'plot']
    inlines = [JobActivityInline, JobBookingInline]
    actions = ['mark_completed', 'mark_cancelled', 'recalculate_amounts']

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
        ('Activity Summary', {
            'fields': ('activity_summary',),
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

    # ── List display helpers ───────────────────────────────────────────────
    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b', 'scheduled': '#3b82f6',
            'in_progress': '#8b5cf6', 'completed': '#10b981', 'cancelled': '#ef4444',
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
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, obj.priority)
    priority_badge.short_description = 'Priority'

    def cluster_list(self, obj):
        return ', '.join([c.name for c in obj.clusters.all()]) or '-'
    cluster_list.short_description = 'Clusters'

    def activity_count(self, obj):
        count = obj.activities.count()
        url = reverse('admin:tender_jobactivity_changelist') + f'?job__job_id={obj.job_id}'
        return format_html('<a href="{}">{} activities</a>', url, count)
    activity_count.short_description = 'Activities'

    def pending_activities(self, obj):
        pending = obj.activities.filter(allocation_status='pending', is_lost=False).count()
        if pending == 0:
            return format_html('<span style="color:#10b981;font-weight:bold;">✓ All done</span>')
        return format_html(
            '<span style="color:#ef4444;font-weight:bold;">{} pending</span>', pending
        )
    pending_activities.short_description = 'Pending'

    # ── Detail page summary ────────────────────────────────────────────────
    def activity_summary(self, obj):
        from django.db.models import Sum, Count
        stats = obj.activities.aggregate(
            total=Count('id'),
            total_area=Sum('total_area'),
            allocated_area=Sum('allocated_area'),
            pending=Count('id', filter=models.Q(allocation_status='pending')),
            allocated=Count('id', filter=models.Q(allocation_status='fully_allocated')),
            in_progress=Count('id', filter=models.Q(allocation_status='in_progress')),
            lost=Count('id', filter=models.Q(is_lost=True)),
        )
        return format_html(
            '''
            <table style="border-collapse:collapse;font-size:13px;">
              <tr>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:bold;">Total Activities</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;">{}</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:bold;">Total Area</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;">{} ac</td>
              </tr>
              <tr>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:bold;">Pending</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;color:#f59e0b;font-weight:bold;">{}</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:bold;">Allocated Area</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;color:#10b981;font-weight:bold;">{} ac</td>
              </tr>
              <tr>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:bold;">Fully Allocated</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;color:#10b981;font-weight:bold;">{}</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:bold;">In Progress</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;color:#8b5cf6;font-weight:bold;">{}</td>
              </tr>
              <tr>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:bold;">Lost / Cancelled</td>
                <td style="padding:4px 12px;border:1px solid #e5e7eb;color:#ef4444;font-weight:bold;">{}</td>
                <td></td><td></td>
              </tr>
            </table>
            ''',
            stats['total'], stats['total_area'] or 0,
            stats['pending'], stats['allocated_area'] or 0,
            stats['allocated'], stats['in_progress'],
            stats['lost'],
        )
    activity_summary.short_description = 'Activity Summary'

    # ── Bulk actions ───────────────────────────────────────────────────────
    def mark_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'✅ {updated} jobs marked as completed.')
    mark_completed.short_description = '✅ Mark selected as Completed'

    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'❌ {updated} jobs marked as cancelled.')
    mark_cancelled.short_description = '❌ Mark selected as Cancelled'

    def recalculate_amounts(self, request, queryset):
        from django.db.models import Sum
        updated = 0
        for job in queryset:
            total = job.activities.aggregate(s=Sum('subtotal'))['s'] or 0
            job.total_activities_amount = total
            job.save(update_fields=['total_activities_amount'])
            updated += 1
        self.message_user(request, f'🔄 Recalculated amounts for {updated} jobs.')
    recalculate_amounts.short_description = '🔄 Recalculate activity amounts'
@admin.register(JobActivity)
class JobActivityAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'job', 'activity', 'plot', 'total_area',
        'allocated_area', 'remaining_area', 'scheduled_date',
        'allocation_status_badge', 'rate_per_acre', 'subtotal',
        'is_strict', 'is_lost', 'is_manually_moved', 'api_activity_id'
    )
    list_filter = (
        'allocation_status', 'is_strict', 'is_fully_allocated',
        'is_lost', 'is_manually_edited', 'is_manually_moved',
        'activity', 'source',
    )
    search_fields = (
        'job__job_id',
        'job__farmer__farmer_name',
        'activity__name',
        'api_activity_id',
        'plot__name',
        'plot__plot_code',
    )
    readonly_fields = (
        'remaining_area', 'total_price', 'subtotal',
        'created_at', 'updated_at',
    )
    list_editable = (
        'scheduled_date',   # quick reschedule from list
    )
    date_hierarchy = 'scheduled_date'
    autocomplete_fields = ['job', 'activity', 'plot']
    inlines = [AllocationInline]
    actions = ['recalculate_status', 'mark_lost', 'mark_not_lost', 'mark_manually_moved', 'clear_manually_moved']

    fieldsets = (
        ('Job & Activity', {
            'fields': ('job', 'activity', 'plot', 'api_activity_id', 'source', 'original_source')
        }),
        ('Area', {
            'fields': ('total_area', 'allocated_area', 'remaining_area', 'crop_bundles')
        }),
        ('Schedule', {
    'fields': (
        'scheduled_date', 'original_scheduled_date', 'sales_date',  # ← add sales_date
        'scheduled_time', 'estimated_workers',
        'is_manually_moved', 'last_moved_by', 'last_moved_at',
    )
}),
        ('Pricing', {
            'fields': ('rate_per_acre', 'total_price', 'transport_cost', 'other_cost', 'subtotal')
        }),
        ('Status', {
            'fields': (
                'allocation_status', 'is_fully_allocated',
                'is_strict', 'is_manually_edited',
            ),
            'description': '⚠️ Manually overriding status will not recalculate remaining_area. Use the Recalculate action instead.'
        }),
        ('Lost / Cancelled', {
            'fields': ('is_lost', 'lost_reason'),
            'classes': ('collapse',)
        }),
        ('Move History', {
            'fields': ('moved_from_activity', 'move_reason'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('location',),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ── Badges ────────────────────────────────────────────────────────────
    def allocation_status_badge(self, obj):
        colors = {
            'pending':              '#f59e0b',
            'partially_allocated':  '#3b82f6',
            'fully_allocated':      '#10b981',
            'in_progress':          '#8b5cf6',
            'completed':            '#6b7280',
        }
        color = colors.get(obj.allocation_status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_allocation_status_display()
        )
    allocation_status_badge.short_description = 'Status'

    # ── Actions ───────────────────────────────────────────────────────────
    def recalculate_status(self, request, queryset):
        from django.db.models import Sum
        updated = 0
        for obj in queryset:
            total = obj.allocations.filter(
                status__in=['scheduled', 'in_progress', 'completed']
            ).aggregate(total=Sum('allocated_area'))['total'] or 0
            obj.allocated_area = total
            obj.save()
            updated += 1
        self.message_user(request, f'✅ Recalculated {updated} activities.')
    recalculate_status.short_description = '🔄 Recalculate status from allocations'

    def mark_lost(self, request, queryset):
        updated = queryset.update(is_lost=True)
        self.message_user(request, f'🚫 Marked {updated} activities as lost.')
    mark_lost.short_description = '🚫 Mark as Lost'

    def mark_not_lost(self, request, queryset):
        updated = queryset.update(is_lost=False)
        self.message_user(request, f'✅ Restored {updated} activities.')
    mark_not_lost.short_description = '✅ Restore (unmark lost)'

    def mark_manually_moved(self, request, queryset):
        updated = queryset.update(is_manually_moved=True)
        self.message_user(request, f'📌 Marked {updated} as manually moved.')
    mark_manually_moved.short_description = '📌 Mark as Manually Moved'

    def clear_manually_moved(self, request, queryset):
        updated = queryset.update(is_manually_moved=False)
        self.message_user(request, f'🔓 Cleared manually moved flag on {updated} activities.')
    clear_manually_moved.short_description = '🔓 Clear Manually Moved flag'



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
# MUKKADAM
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
    readonly_fields = ('created_at', 'updated_at', 'last_synced')
    inlines = [
        ClusterMukkadamAssignmentInline,
        MukkadamActivityRateInline,
        MukkadamAvailabilityInline,
        LeaveInline,
        MukkadamMiscCostInline,
        MukkadamJobSettlementInline,
    ]

    fieldsets = (
        ('Identity', {
            'fields': ('mukkadam_id', 'mukkadam_name', 'mobile_numbers', 'is_permanent')
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

from django.contrib import admin
from .models import ClusterMukkadamAssignment

from django.contrib import admin




@admin.register(ClusterMukkadamAssignment)
class ClusterMukkadamAssignmentAdmin(admin.ModelAdmin):
    search_fields = ('mukkadam__mukkadam_name', 'cluster__name')  # ← required for autocomplete_fields
    list_display = ('mukkadam', 'cluster', 'is_active', 'advance_amount', 'weekly_amount')
    list_editable = (
        'advance_amount',   # ✅ edit directly from list
        'weekly_amount',
        'is_active',
    )
    list_filter = ('mukkadam_type', 'updown_mode', 'is_active', 'weekly_payment_day')
    search_fields = ('mukkadam__mukkadam_name', 'cluster__name')
    readonly_fields = ('joined_at', 'updated_at')

    fieldsets = (
        ('Basic Info', {
            'fields': ('mukkadam', 'cluster', 'weekly_amount', 'mukkadam_type', 'updown_mode', 'is_active')
        }),
        ('Updown Availability', {
            'fields': ('updown_from_date', 'updown_to_date', 'updown_specific_dates')
        }),
        ('Financials', {
            'fields': (
                'transport_price',
                'advance_amount',        # ✅ fully editable
                'advance_is_manual',
                'weekly_payment_day',
                'total_weekly_payments',
            )
        }),
        ('Timestamps', {
            'fields': ('joined_date', 'joined_at', 'updated_at')
        }),
    )


# admin.py

@admin.register(MukkadamLedgerEntry)
class MukkadamLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'mukkadam', 'cluster', 'payment_type',
        'farmer_name', 'activity_name', 'acres',
        'amount', 'job_date', 'payment_date',
        'payment_status', 'remark'
    )
    list_filter = ('payment_type', 'payment_status', 'cluster', 'mukkadam')
    search_fields = ('mukkadam__mukkadam_name', 'farmer_name', 'activity_name', 'remark')
    list_editable = ('payment_status', 'remark')
    date_hierarchy = 'payment_date'
    autocomplete_fields = ['mukkadam', 'cluster', 'job', 'job_activity']

    fieldsets = (
        ('Who', {
            'fields': ('mukkadam', 'cluster')
        }),
        ('Farmer & Job (optional)', {
            'fields': ('farmer_name', 'farmer_contact', 'job', 'job_activity', 'activity_name'),
            'description': 'Leave blank for advance/transport/weekly payments'
        }),
        ('Payment', {
            'fields': ('payment_type', 'acres', 'amount', 'job_date', 'payment_date')
        }),
        ('Status', {
            'fields': ('payment_status', 'remark', 'proof_s3_key')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

@admin.register(MukkadamWeeklyPayment)
class MukkadamWeeklyPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'assignment', 'payment_date', 'amount',
        'crew_size_on_date', 'is_auto_generated', 'notes', 'created_at'
    )
    list_filter = ('is_auto_generated', 'assignment__cluster')

    date_hierarchy = 'payment_date'
    autocomplete_fields = ['assignment']

    fieldsets = (
        ('Payment Details', {
            'fields': ('assignment', 'payment_date', 'amount', 'crew_size_on_date')
        }),
        ('Meta', {
            'fields': ('is_auto_generated', 'notes')
        }),
    )


@admin.register(MukkadamMiscCost)
class MukkadamMiscCostAdmin(admin.ModelAdmin):
    list_display = ('mukkadam', 'job', 'amount', 'reason', 'created_at')
    search_fields = ('mukkadam__mukkadam_name', 'job__job_id', 'reason')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['mukkadam', 'job']

    fieldsets = (
        ('Details', {
            'fields': ('mukkadam', 'job', 'amount', 'reason')
        }),
    )


@admin.register(MukkadamJobSettlement)
class MukkadamJobSettlementAdmin(admin.ModelAdmin):
    list_display = (
        'mukkadam', 'job', 'cluster', 'gross_amount',
        'payable_amount', 'advance_deducted', 'weekly_payments_deducted',
        'credit_carried_forward', 'deposit_carried_forward',
        'net_payable_colored', 'status_badge', 'calculated_at'
    )
    list_filter = ('status', 'cluster')
    search_fields = ('mukkadam__mukkadam_name', 'job__job_id')
    
    # ✅ Only keep true auto-fields as readonly
    readonly_fields = ('created_at', 'updated_at')
    
    filter_horizontal = ('weekly_payments_applied',)
    autocomplete_fields = ['mukkadam', 'job', 'cluster', 'plot']

    fieldsets = (
        ('Core', {
            'fields': ('mukkadam', 'job', 'plot', 'cluster', 'status')
        }),
        ('Gross Calculation', {
            'fields': (
                'gross_amount',        # ✅ now editable
                'deposit_percent',
                'payable_amount',      # ✅ now editable
                'deposit_carried_forward',
                'credit_carried_forward',
            )
        }),
        ('Deductions', {
            'fields': (
                'advance_deducted',           # ✅ now editable
                'weekly_payments_deducted',   # ✅ now editable
            )
        }),
        ('Net', {
            'fields': ('net_payable',)        # ✅ now editable
        }),
        ('Weekly Payments Applied', {
            'fields': ('weekly_payments_applied',),
            'classes': ('collapse',)
        }),
        ('Notes & Timestamps', {
            'fields': ('notes', 'calculated_at', 'paid_at', 'created_at', 'updated_at'),
        }),
    )

    def net_payable_colored(self, obj):
        color = '#dc2626' if obj.net_payable > 0 else '#16a34a'
        label = f'₹{obj.net_payable}' if obj.net_payable > 0 else f'−₹{abs(obj.net_payable)}'
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, label)
    net_payable_colored.short_description = 'Net Payable'

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b', 'calculated': '#3b82f6',
            'payment_raised': '#8b5cf6', 'paid': '#10b981', 'no_payment_needed': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

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


# ============================================================================
# ALLOCATION
# ============================================================================
@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'job_activity', 'mukkadam', 'cluster',
        'allocated_date', 'allocated_area', 'allocated_workers',
        'farmer_rate', 'mukkadam_rate', 'profit_display',
        'work_status_badge', 'status_badge',
        'payment_status', 'report_submitted', 'farmer_agreed',
        'allows_second_job', 'is_carry_forward', 'is_auto_allocated',
    )
    list_filter = (
        'status', 'work_status', 'payment_status', 'cluster',
        'report_submitted', 'farmer_agreed',
        'is_carry_forward', 'is_auto_allocated',
        'allows_second_job', 'use_actual_for_settlement',
    )
    search_fields = (
        'job_activity__job__job_id',
        'job_activity__activity__name',
        'mukkadam__mukkadam_name',
    )
    readonly_fields = (
        'farmer_amount', 'mukkadam_amount', 'profit',
        'efficiency_score', 'created_at', 'updated_at',
    )
    date_hierarchy = 'allocated_date'
    autocomplete_fields = ['job_activity', 'mukkadam', 'cluster']
    inlines = [AllocationChangeLogInline]

    fieldsets = (
        ('Core Assignment', {
            'fields': ('job_activity', 'mukkadam', 'cluster', 'allocated_date')
        }),
        ('Allocation Details', {
            'fields': (
                'allocated_area', 'allocated_workers',
                'allows_second_job', 'is_auto_allocated',
            )
        }),
        ('Pricing', {
            'fields': (
                'farmer_rate', 'mukkadam_rate',
                'farmer_amount', 'mukkadam_amount', 'profit',
            )
        }),
        ('Status', {
            'fields': (
                'status', 'work_status', 'payment_status',
                'actual_workers', 'actual_area_completed', 'efficiency_score',
            )
        }),
        ('Day-End Report', {
            'fields': (
                'actual_start_time', 'actual_end_time', 'actual_crew_size',
                'actual_area_done', 'report_submitted', 'report_submitted_at',
                'use_actual_for_settlement',
            )
        }),
        ('Farmer Verification', {
            'fields': (
                'farmer_agreed', 'farmer_response_at', 'farmer_dispute_reason',
            )
        }),
        ('Dispute Resolution', {
            'fields': (
                'mukkadam_claimed_area', 'admin_override_area',
                'dispute_reason', 'dispute_resolved_at', 'dispute_resolved_by',
            ),
            'classes': ('collapse',)
        }),
        ('Carry Forward', {
            'fields': ('is_carry_forward', 'carry_forward_from'),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time'),
            'classes': ('collapse',)
        }),
        ('Last Modified', {
            'fields': ('last_modified_by', 'last_modified_at'),
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
            'scheduled':   '#3b82f6',
            'in_progress': '#8b5cf6',
            'completed':   '#10b981',
            'cancelled':   '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def work_status_badge(self, obj):
        colors = {
            'work_not_started': '#f59e0b',
            'in_progress':      '#8b5cf6',
            'completed':        '#10b981',
        }
        color = colors.get(obj.work_status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_work_status_display()
        )
    work_status_badge.short_description = 'Work Status'
@admin.register(MukkadamPayment)
class MukkadamPaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'mukkadam', 'settlement', 'mode', 'amount', 'paid_at', 'created_by')
    list_filter = ('mode',)
    search_fields = ('payment_id', 'mukkadam__mukkadam_name')
    
    # ✅ Only auto-fields readonly
    readonly_fields = ('payment_id', 'created_at', 'updated_at')
    
    filter_horizontal = ('allocations',)
    date_hierarchy = 'paid_at'
    autocomplete_fields = ['mukkadam', 'settlement']

    fieldsets = (
        ('Payment', {
            'fields': ('payment_id', 'mukkadam', 'settlement', 'mode', 'amount')
        }),
        ('Details', {
            'fields': ('notes', 'paid_at', 'created_by', 'proof_s3_key')
        }),
        ('Allocations', {
            'fields': ('allocations',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# ============================================================================
# LEAVES & EXTRA WORKERS
# ============================================================================

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


@admin.register(ExtraWorker)
class ExtraWorkerAdmin(admin.ModelAdmin):
    list_display = ('mukkadam', 'date', 'workers', 'note')
    list_filter = ('date',)
    search_fields = ('mukkadam__mukkadam_name',)
    date_hierarchy = 'date'
    list_editable = ('workers',)
    autocomplete_fields = ['mukkadam']


# Replace PaymentChangeLogAdmin
@admin.register(PaymentChangeLog)
class PaymentChangeLogAdmin(admin.ModelAdmin):
    list_display = ('payment_type', 'change_type', 'field_changed', 'old_value', 'new_value', 'changed_by', 'changed_at')
    list_filter = ('payment_type', 'change_type')
    readonly_fields = ('changed_at',)
    date_hierarchy = 'changed_at'


# ============================================================================
# SYSTEM
# ============================================================================

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at', 'updated_by')
    search_fields = ('key', 'description')
    readonly_fields = ('updated_at',)



from django.contrib import admin
from .models import FarmerBillWebhookLog


from .models import FarmerPaymentWebhookLog

# ============================================================================
# MISSING MODEL REGISTRATIONS
# ============================================================================

from .models import JobNote, AllocationAuditLog, MukkadamOTPRequest, FarmerCall, PaymentProof
@admin.register(JobNote)
class JobNoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'job_activity', 'author', 'note_date', 'is_resolved', 'resolved_by', 'created_at')
    list_filter = ('is_resolved', 'note_date', 'tags')
    search_fields = ('job__job_id', 'job_activity__id', 'text', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'note_date'
    filter_horizontal = ('mentions',)
    autocomplete_fields = ['job', 'job_activity', 'author', 'resolved_by']
    fieldsets = (
        ('Note', {
            'fields': ('job', 'job_activity', 'author', 'text', 'tags', 'mentions', 'note_date')
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_by', 'resolved_at', 'resolution_note')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(AllocationAuditLog)
class AllocationAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'action', 'allocation_id', 'job_id',
        'mukkadam_name', 'farmer_name', 'activity_name',
        'allocated_date', 'allocated_area', 'changed_by', 'changed_at'
    )
    list_filter = ('action', 'allocated_date', 'changed_by')
    search_fields = ('job_id', 'mukkadam_name', 'farmer_name', 'activity_name')
    readonly_fields = ('changed_at',)
    date_hierarchy = 'changed_at'
    fieldsets = (
        ('Event', {
            'fields': ('action', 'allocation_id', 'job_activity_id', 'job_id')
        }),
        ('Who', {
            'fields': ('mukkadam_id', 'mukkadam_name', 'farmer_name', 'activity_name')
        }),
        ('Details', {
            'fields': ('allocated_date', 'allocated_area', 'allocated_workers', 'notes')
        }),
        ('Snapshot', {
            'fields': ('snapshot',),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('changed_by', 'changed_at'),
        }),
    )


@admin.register(MukkadamOTPRequest)
class MukkadamOTPRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'mukkadam', 'phone', 'otp_type',
        'crew_size', 'allocation', 'is_used', 'requested_at'
    )
    list_filter = ('otp_type', 'is_used')
    search_fields = ('mukkadam__mukkadam_name', 'phone')
    readonly_fields = ('requested_at',)
    list_editable = ('is_used',)
    date_hierarchy = 'requested_at'
    autocomplete_fields = ['mukkadam', 'allocation']
    fieldsets = (
        ('Request', {
            'fields': ('mukkadam', 'phone', 'otp_type', 'crew_size', 'allocation')
        }),
        ('Status', {
            'fields': ('is_used', 'requested_at')
        }),
    )


@admin.register(FarmerCall)
class FarmerCallAdmin(admin.ModelAdmin):
    list_display = (
        'call_sid', 'mobile_number', 'from_number', 'purpose',
        'status', 'direction', 'duration', 'talk_time',
        'has_recording', 'initiated_at', 'created_by'
    )
    list_filter = ('purpose', 'status', 'direction')
    search_fields = ('call_sid', 'mobile_number', 'job_id', 'notes')
    readonly_fields = ('initiated_at', 'call_sid')
    date_hierarchy = 'initiated_at'
    fieldsets = (
        ('Call Identity', {
            'fields': ('call_sid', 'mobile_number', 'from_number', 'direction', 'purpose')
        }),
        ('Status & Metrics', {
            'fields': ('status', 'state', 'duration', 'talk_time', 'price')
        }),
        ('Recording', {
            'fields': ('recording_url', 'recording_urls', 's3_key'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('initiated_at', 'answered_at', 'completed_at', 'created_time', 'updated_time'),
            'classes': ('collapse',)
        }),
        ('Exotel Data', {
            'fields': ('virtual_number', 'custom_field', 'legs_url'),
            'classes': ('collapse',)
        }),
        ('Context', {
            'fields': ('job_id', 'notes', 'webhook_data', 'created_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    list_display = ('id', 'proof_type', 'reference_id', 'file_name', 's3_key', 'uploaded_at', 'uploaded_by')
    list_filter = ('proof_type', 'uploaded_at')
    search_fields = ('file_name', 's3_key', 'reference_id')
    readonly_fields = ('uploaded_at',)
    fieldsets = (
        ('Proof', {
            'fields': ('proof_type', 'reference_id', 'file_name', 's3_key', 's3_url')
        }),
        ('Audit', {
            'fields': ('uploaded_by', 'uploaded_at')
        }),
    )


# In ActivityLogTenderAdmin — remove has_change_permission, keep has_add = False
@admin.register(ActivityLogTender)
class ActivityLogTenderAdmin(admin.ModelAdmin):
    list_display = ('action', 'job', 'job_activity', 'performed_by', 'created_at')
    list_filter = ('action',)
    search_fields = ('job__job_id',)
    readonly_fields = ('created_at',)   # only timestamp is readonly
    date_hierarchy = 'created_at'
    # ← no has_add/change/delete overrides = all enabled


# In AllocationChangeLogTenderAdmin — make editable
@admin.register(AllocationChangeLogTender)
class AllocationChangeLogTenderAdmin(admin.ModelAdmin):
    list_display = ('allocation', 'change_type', 'field_changed', 'old_value', 'new_value', 'changed_by', 'changed_at')
    list_filter = ('change_type',)
    search_fields = ('allocation__job_activity__job__job_id',)
    readonly_fields = ('changed_at',)
    date_hierarchy = 'changed_at'


# In WebhookLogAdmin — make editable
@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'status', 'farmer_id', 'job_id',
        'cluster_matched', 'activities_processed', 'activities_failed',
        'plots_created', 'error_type', 'created_at'
    )
    list_filter = ('status', 'cluster_matched')
    search_fields = ('farmer_id', 'job_id', 'error_type')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


# In APISyncAdmin — make editable
@admin.register(APISync)
class APISyncAdmin(admin.ModelAdmin):
    list_display = ('sync_type', 'status', 'records_synced', 'last_sync_at', 'error_message')
    list_filter = ('sync_type', 'status')
    readonly_fields = ('last_sync_at',)
    date_hierarchy = 'last_sync_at'


# In FarmerBillWebhookLogAdmin — enable delete at minimum
@admin.register(FarmerBillWebhookLog)
class FarmerBillWebhookLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'farmer_name', 'farmer_phone', 'job_id',
        'crop_name', 'mukkadam_name', 'total_billed', 'balance_due',
        'sent_by_name', 'webhook_status',
    ]
    list_filter = ['webhook_status', 'created_at']
    search_fields = ['farmer_name', 'farmer_id', 'job_id', 'sent_by_name']
    readonly_fields = ['created_at', 'full_payload']
    ordering = ['-created_at']
    # ← all permissions enabled by default


# In FarmerPaymentWebhookLogAdmin — enable delete
@admin.register(FarmerPaymentWebhookLog)
class FarmerPaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'booking_id', 'amount', 'mode', 'transaction_id', 'payment_created', 'status']
    list_filter = ['status', 'payment_created', 'created_at']
    search_fields = ['booking_id', 'transaction_id']
    readonly_fields = ['created_at', 'raw_payload']