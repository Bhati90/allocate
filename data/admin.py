from django.contrib import admin
from .models import (
    UserProfile,
    JobActivity,
    Allocation,
    AllocationStats,
    
    Contact,
    Message,
    CallLog
)

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


# -----------------------------
# Job Activity Admin
# -----------------------------
@admin.register(JobActivity)
class JobActivityAdmin(admin.ModelAdmin):
    list_display = (
        'job_id',
        'activity_id',
        'activity_name',
        'scheduled_datetime',
        'total_area',
        'allocated_area',
        'remaining_area',
        'is_fully_allocated'
    )
    list_filter = ('scheduled_datetime', 'activity_name')
    search_fields = ('job_id', 'activity_id', 'activity_name')
    readonly_fields = ('rate_per_acre', 'created_at', 'updated_at')
    ordering = ('scheduled_datetime',)


# -----------------------------
# Allocation Admin
# -----------------------------
@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'farmer_work_id',
        'job_activity',
        'mukkadam_id',
        'allocated_area',
        'work_date',
        'status',
        'total_cost',
        'allocated_by',
        'allocated_at'
    )
    list_filter = (
        'status',
        'work_date',
        'transport_type'
    )
    search_fields = (
        'job_activity__job_id',
        'job_activity__activity_name',
        'mukkadam_id'
    )
    readonly_fields = ('allocated_at',)
    autocomplete_fields = ('job_activity', 'allocated_by')


# -----------------------------
# Allocation Stats Admin
# -----------------------------
@admin.register(AllocationStats)
class AllocationStatsAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'total_allocations',
        'total_area_allocated',
        'total_mukkadam_price',
        'total_transport_price'
    )
    ordering = ('-date',)
    readonly_fields = (
        'total_allocations',
        'total_area_allocated',
        'total_mukkadam_price',
        'total_transport_price',
        'allocations_by_user'
    )

# -----------------------------


# -----------------------------
# User Data Sync Admin (Contacts, Calls, SMS)
# -----------------------------
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user_id', 'synced_at')
    search_fields = ('display_name', 'user_id', 'phones')
    readonly_fields = ('synced_at',)
    list_filter = ('synced_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        'type',
        'address',
        'user_id',
        'message_datetime',
        'read_status'
    )
    list_filter = ('type', 'read_status', 'synced_at')
    search_fields = ('address', 'body', 'user_id')
    readonly_fields = ('synced_at', 'timestamp')


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = (
        'type',
        'name',
        'number',
        'duration',
        'user_id',
        'call_datetime'
    )
    list_filter = ('type', 'synced_at')
    search_fields = ('name', 'number', 'user_id')
    readonly_fields = ('synced_at', 'timestamp')


from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for ActivityLog
    """

    # 📌 Columns shown in admin list view
    list_display = (
        'activity_type',
        'job_id',
        'mukkadam_id',
        'amount',
        'performed_by',
        'performed_at',
    )

    # 🔍 Filters on right sidebar
    list_filter = (
        'activity_type',
        'performed_at',
        'performed_by',
    )

    # 🔎 Search box
    search_fields = (
        'job_id',
        'description',
        'mukkadam_id',
        'transport_provider_id',
    )

    # ⏱ Default ordering
    ordering = ('-performed_at',)

    # 🚀 Performance optimization
    list_select_related = (
        'allocation',
        'payment_request',
        'transport_payment_request',
        'performed_by',
    )

    # 🔒 Make logs immutable (recommended)
    readonly_fields = (
        'activity_type',
        'description',
        'allocation',
        'payment_request',
        'transport_payment_request',
        'job_id',
        'mukkadam_id',
        'transport_provider_id',
        'amount',
        'performed_by',
        'performed_at',
        'metadata',
    )

    # 🧾 Better form layout
    fieldsets = (
        ('Activity Info', {
            'fields': ('activity_type', 'description', 'performed_at', 'performed_by')
        }),
        ('Related Objects', {
            'fields': ('allocation', 'payment_request', 'transport_payment_request')
        }),
        ('Reference IDs', {
            'fields': ('job_id', 'mukkadam_id', 'transport_provider_id')
        }),
        ('Financial', {
            'fields': ('amount',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',),
        }),
    )

    # ❌ Disable add/delete (logs should only be system-generated)
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
