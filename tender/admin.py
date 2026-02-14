from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ActivityCatalog, Farmer, Job, JobActivity, JobBooking, FarmerPayment,
    Mukkadam, MukkadamActivityRate, MukkadamAvailability,
    Allocation, MukkadamPayment,
    AllocationChangeLogTender, PaymentChangeLog, SystemConfiguration, APISync
)


# ============================================================================
# MASTER DATA ADMIN
# ============================================================================

@admin.register(ActivityCatalog)
class ActivityCatalogAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'activity_type', 'is_strict', 'default_rate_per_acre',
        'estimated_workers_per_acre', 'source', 'created_at'
    ]
    list_filter = ['is_strict', 'source', 'activity_type']
    search_fields = ['name', 'activity_type']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'activity_type', 'source')
        }),
        ('Default Settings', {
            'fields': ('default_rate_per_acre', 'estimated_workers_per_acre', 'is_strict')
        }),
    )


# ============================================================================
# JOB/BOOKING ADMIN
# ============================================================================

@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ('farmer_id', 'farmer_name', 'cluster')
    # if Farmer only has cluster now:
    list_filter = ('cluster',)


class JobActivityInline(admin.TabularInline):
    model = JobActivity
    extra = 0
    fields = [
        'activity', 'total_area', 'allocated_area', 'remaining_area',
        'scheduled_date', 'rate_per_acre', 'allocation_status'
    ]
    readonly_fields = ['remaining_area', 'allocation_status']
    can_delete = False


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'farmer', 'status', 'priority', 'scheduled_date',
        'booking_type', 'total_activities_amount', 'created_at'
    ]
    list_filter = ['status', 'priority', 'booking_type', 'is_field_verified']
    search_fields = ['job_id', 'work_id', 'farmer__farmer_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'last_synced']
    
    inlines = [JobActivityInline]
    
    fieldsets = (
        ('Job Information', {
            'fields': ('job_id', 'work_id', 'farmer', 'plot_id')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'booking_type')
        }),
        ('Scheduling', {
            'fields': ('scheduled_date', 'is_field_verified', 'is_complex')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'point_of_contact')
        }),
        ('Notes', {
            'fields': ('activity_notes', 'internal_notes')
        }),
        ('Financial', {
            'fields': ('total_activities_amount',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_synced'),
            'classes': ('collapse',)
        }),
    )


@admin.register(JobActivity)
class JobActivityAdmin(admin.ModelAdmin):
    list_display = [
        'job', 'activity', 'total_area', 'allocated_area', 'remaining_area',
        'scheduled_date', 'allocation_status', 'is_fully_allocated'
    ]
    list_filter = ['allocation_status', 'is_fully_allocated', 'activity__is_strict']
    search_fields = ['job__job_id', 'activity__name']
    ordering = ['scheduled_date', '-created_at']
    readonly_fields = ['remaining_area', 'allocation_status', 'is_fully_allocated']
    
    fieldsets = (
        ('Job & Activity', {
            'fields': ('job', 'activity', 'location')
        }),
        ('Area Details', {
            'fields': ('total_area', 'allocated_area', 'remaining_area', 'crop_bundles')
        }),
        ('Scheduling', {
            'fields': ('scheduled_date', 'scheduled_time', 'estimated_workers')
        }),
        ('Pricing', {
            'fields': ('rate_per_acre', 'total_price', 'transport_cost', 'other_cost', 'subtotal')
        }),
        ('Status', {
            'fields': ('allocation_status', 'is_fully_allocated', 'is_manually_edited')
        }),
        ('Lost/Cancelled', {
            'fields': ('is_lost', 'lost_reason'),
            'classes': ('collapse',)
        }),
    )


class FarmerPaymentInline(admin.TabularInline):
    model = FarmerPayment
    extra = 0
    fields = ['payment_id', 'mode', 'amount', 'paid_at', 'paid_status', 'notes']
    readonly_fields = ['payment_id']


@admin.register(JobBooking)
class JobBookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_id', 'job', 'status', 'total_amount', 
        'advance_paid', 'balance', 'payment_progress'
    ]
    list_filter = ['status']
    search_fields = ['booking_id', 'job__job_id', 'assignee_number']
    
    inlines = [FarmerPaymentInline]
    
    def payment_progress(self, obj):
        if obj.total_amount > 0:
            percentage = (obj.advance_paid / obj.total_amount) * 100
            color = 'green' if percentage >= 100 else 'orange' if percentage >= 50 else 'red'
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, percentage
            )
        return "0%"
    payment_progress.short_description = 'Payment %'


@admin.register(FarmerPayment)
class FarmerPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_id', 'booking', 'mode', 'amount', 
        'paid_at', 'paid_status', 'created_by'
    ]
    list_filter = ['mode', 'paid_status', 'paid_at']
    search_fields = ['payment_id', 'booking__job__job_id']
    ordering = ['-paid_at']
    readonly_fields = ['created_at', 'updated_at']


# ============================================================================
# MUKKADAM ADMIN
# ============================================================================

# class MukkadamActivityRateInline(admin.TabularInline):
#     model = MukkadamActivityRate
#     extra = 0
#     fields = ['activity', 'rate_per_acre', 'source', 'is_active']


@admin.register(Mukkadam)
class MukkadamAdmin(admin.ModelAdmin):
    list_display = [
        'mukkadam_id', 'mukkadam_name', 'crew_size', 'district',
        'is_permanent', 'start_date', 'end_date', 'last_synced'
    ]
    list_filter = ['is_permanent', 'district', 'work_mode']
    search_fields = ['mukkadam_id', 'mukkadam_name', 'mobile_numbers']
    ordering = ['mukkadam_name']
    readonly_fields = ['last_synced']
    
    # inlines = [MukkadamActivityRateInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('mukkadam_id', 'mukkadam_name', 'mobile_numbers', 'is_permanent')
        }),
        ('Location', {
            'fields': ('district', 'taluka', 'village', 'current_latitude', 'current_longitude')
        }),
        ('Availability', {
            'fields': ('start_date', 'end_date', 'crew_size', 'work_mode')
        }),
        ('Other Details', {
            'fields': ('has_smartphone',)
        }),
        ('Rate Information', {
            'fields': ('rate_card', 'tender_activities'),
            'classes': ('collapse',)
        }),
        ('Sync Info', {
            'fields': ('last_synced',),
            'classes': ('collapse',)
        }),
    )


# @admin.register(MukkadamActivityRate)
# class MukkadamActivityRateAdmin(admin.ModelAdmin):
#     list_display = [
#         'mukkadam', 'activity', 'rate_per_acre', 'source', 
#         'is_active', 'updated_at'
#     ]
#     list_filter = ['source', 'is_active', 'activity']
#     search_fields = ['mukkadam__mukkadam_name', 'activity__name']
#     ordering = ['mukkadam', 'activity']


@admin.register(MukkadamAvailability)
class MukkadamAvailabilityAdmin(admin.ModelAdmin):
    list_display = [
        'mukkadam', 'date', 'is_available', 'is_on_leave',
        'available_crew_size', 'allocated_workers', 'remaining_capacity',
        'is_manually_set'
    ]
    list_filter = ['is_available', 'is_on_leave', 'is_manually_set', 'date']
    search_fields = ['mukkadam__mukkadam_name']
    ordering = ['-date', 'mukkadam']
    readonly_fields = ['remaining_capacity']
    
    fieldsets = (
        ('Mukkadam & Date', {
            'fields': ('mukkadam', 'date')
        }),
        ('Availability', {
            'fields': ('is_available', 'is_on_leave', 'available_crew_size')
        }),
        ('Capacity', {
            'fields': ('allocated_workers', 'remaining_capacity')
        }),
        ('Notes', {
            'fields': ('notes', 'is_manually_set')
        }),
    )


# ============================================================================
# ALLOCATION ADMIN
# ============================================================================

@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'job_activity', 'mukkadam', 'allocated_date',
        'allocated_area', 'allocated_workers', 'status',
        'profit_display', 'efficiency_score', 'created_by'
    ]
    list_filter = ['status', 'allocated_date', 'mukkadam', 'job_activity__activity']
    search_fields = [
        'job_activity__job__job_id', 
        'mukkadam__mukkadam_name',
        'job_activity__activity__name'
    ]
    ordering = ['-allocated_date', '-created_at']
    readonly_fields = [
        'farmer_amount', 'mukkadam_amount', 'profit', 
        'efficiency_score', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Allocation Details', {
            'fields': ('job_activity', 'mukkadam', 'allocated_date', 'status')
        }),
        ('Area & Workers', {
            'fields': ('allocated_area', 'allocated_workers')
        }),
        ('Pricing', {
            'fields': ('farmer_rate', 'mukkadam_rate', 'farmer_amount', 'mukkadam_amount', 'profit')
        }),
        ('Performance', {
            'fields': (
                'actual_workers', 'actual_area_completed',
                'start_time', 'end_time', 'efficiency_score'
            ),
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
            '<span style="color: {};">₹{:.2f}</span>',
            color, obj.profit
        )
    profit_display.short_description = 'Profit/Loss'


@admin.register(MukkadamPayment)
class MukkadamPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_id', 'mukkadam', 'mode', 'amount',
        'paid_at', 'allocation_count', 'created_by'
    ]
    list_filter = ['mode', 'paid_at']
    search_fields = ['payment_id', 'mukkadam__mukkadam_name']
    ordering = ['-paid_at']
    readonly_fields = ['created_at', 'updated_at']
    
    filter_horizontal = ['allocations']
    
    def allocation_count(self, obj):
        return obj.allocations.count()
    allocation_count.short_description = 'Allocations'


# ============================================================================
# AUDIT LOG ADMIN
# ============================================================================

@admin.register(AllocationChangeLogTender)
class AllocationChangeLogAdmin(admin.ModelAdmin):
    list_display = [
        'allocation', 'change_type', 'field_changed',
        'changed_by', 'changed_at'
    ]
    list_filter = ['change_type', 'changed_at']
    search_fields = ['allocation__id', 'field_changed']
    ordering = ['-changed_at']
    readonly_fields = ['changed_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PaymentChangeLog)
class PaymentChangeLogAdmin(admin.ModelAdmin):
    list_display = [
        'payment_type', 'change_type', 'field_changed',
        'changed_by', 'changed_at'
    ]
    list_filter = ['payment_type', 'change_type', 'changed_at']
    ordering = ['-changed_at']
    readonly_fields = ['changed_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# ============================================================================
# UTILITY ADMIN
# ============================================================================

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ['key', 'description', 'updated_at', 'updated_by']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at']


@admin.register(APISync)
class APISyncAdmin(admin.ModelAdmin):
    list_display = [
        'sync_type', 'status', 'records_synced',
        'last_sync_at', 'has_errors'
    ]
    list_filter = ['sync_type', 'status', 'last_sync_at']
    ordering = ['-last_sync_at']
    readonly_fields = ['last_sync_at']
    
    def has_errors(self, obj):
        if obj.error_message:
            return format_html('<span style="color: red;">✗ Yes</span>')
        return format_html('<span style="color: green;">✓ No</span>')
    has_errors.short_description = 'Errors'
    
    def has_add_permission(self, request):
        return False