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
from django.contrib import admin
from django.utils import timezone
from .models import PaymentRequest, TransportPaymentRequest
from django.contrib import admin
from django.utils.html import format_html
from .models import FarmerCall

# allocation_app/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import FarmerCall

@admin.register(FarmerCall)
class FarmerCallAdmin(admin.ModelAdmin):
    # Columns to show in the list view
    list_display = (
        'initiated_at', 
        'mobile_number', 
        'purpose', 
        'status', 
        'duration_display', 
        'play_audio'  # ✅ Custom audio player column
    )
    
    # Filters on the right sidebar
    list_filter = ('status', 'purpose', 'initiated_at')
    
    # Search box
    search_fields = ('mobile_number', 'call_sid', 'job_id')
    
    # Make some fields read-only to prevent accidental edits
    readonly_fields = ('call_sid', 'audio_player_detail', 'initiated_at', 'webhook_data')

    def duration_display(self, obj):
        if obj.duration:
            return f"{obj.duration}s"
        return "-"
    duration_display.short_description = "Duration"

    def play_audio(self, obj):
        """Renders a compact audio player in the list view"""
        url = obj.audio_url
        if url:
            return format_html(
                '<audio controls preload="none" style="width: 200px; height: 30px;">'
                '<source src="{}" type="audio/mpeg">'
                'Your browser does not support audio.'
                '</audio>',
                url
            )
        return format_html('<span style="color: #999;">No Recording</span>')
    play_audio.short_description = "Audio Preview"

    def audio_player_detail(self, obj):
        """Renders a larger audio player for the detail view"""
        url = obj.audio_url
        if url:
            return format_html(
                '<div>'
                '<audio controls style="width: 100%; max-width: 400px;">'
                '<source src="{}" type="audio/mpeg">'
                '</audio>'
                '<p style="margin-top: 5px;"><a href="{}" target="_blank">Download Recording</a></p>'
                '</div>',
                url, url
            )
        return "No recording available"
    audio_player_detail.short_description = "Recording Player"

    # Group fields in the detail view
    fieldsets = (
        ('Primary Info', {
            'fields': ('call_sid', 'mobile_number', 'from_number', 'purpose', 'status')
        }),
        ('Recording', {
            'fields': ('audio_player_detail', 's3_key', 'recording_url')
        }),
        ('Metrics & Timing', {
            'fields': ('duration', 'talk_time', 'price', 'initiated_at', 'completed_at')
        }),
        ('Technical Data', {
            'classes': ('collapse',), # Hide by default
            'fields': ('virtual_number', 'job_id', 'webhook_data', 'legs_url')
        }),
    )
# -------------------------
# PaymentRequest Admin
# -------------------------
@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'mukkadam_id',
        'allocation',
        'requested_amount',
        'status',
        'requested_at',
        'paid_at',
    )

    list_filter = ('status', 'requested_at')
    search_fields = ('id', 'mukkadam_id', 'allocation__id')
    ordering = ('-requested_at',)

    readonly_fields = (
        'allocation',
        'mukkadam_id',
        'requested_amount',
        'requested_at',
        'requested_by',
        'paid_at',
        'paid_by',
        'rejected_at',
        'rejected_by',
    )

    actions = ['mark_as_paid', 'mark_as_rejected']

    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='paid',
            paid_at=timezone.now(),
            paid_by=request.user
        )
        self.message_user(request, f"{updated} payment request(s) marked as PAID.")

    mark_as_paid.short_description = "Mark selected payment requests as PAID"

    def mark_as_rejected(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='rejected',
            rejected_at=timezone.now(),
            rejected_by=request.user
        )
        self.message_user(request, f"{updated} payment request(s) marked as REJECTED.")

    mark_as_rejected.short_description = "Reject selected payment requests"


# -------------------------
# TransportPaymentRequest Admin
# -------------------------
@admin.register(TransportPaymentRequest)
class TransportPaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'transport_provider_id',
        'allocation',
        'requested_amount',
        'status',
        'requested_at',
        'paid_at',
    )

    list_filter = ('status', 'requested_at')
    search_fields = ('id', 'transport_provider_id', 'allocation__id')
    ordering = ('-requested_at',)

    readonly_fields = (
        'allocation',
        'transport_provider_id',
        'requested_amount',
        'requested_at',
        'requested_by',
        'paid_at',
        'paid_by',
        'rejected_at',
        'rejected_by',
    )

    actions = ['mark_as_paid', 'mark_as_rejected']

    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='paid',
            paid_at=timezone.now(),
            paid_by=request.user
        )
        self.message_user(request, f"{updated} transport payment(s) marked as PAID.")

    mark_as_paid.short_description = "Mark selected transport payments as PAID"

    def mark_as_rejected(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='rejected',
            rejected_at=timezone.now(),
            rejected_by=request.user
        )
        self.message_user(request, f"{updated} transport payment(s) marked as REJECTED.")

    mark_as_rejected.short_description = "Reject selected transport payments"

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

from django.contrib import admin
from django.utils.html import format_html
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for ActivityLog
    Immutable, optimized, audit-friendly
    """

    # 📌 Columns shown in admin list view
    list_display = (
        'colored_activity',
        'job_id',
        'mukkadam_id',
        'amount',
        'performed_by',
        'performed_at',
    )

    list_display_links = ('colored_activity', 'job_id')

    # 🔍 Filters on right sidebar
    list_filter = (
        'activity_type',
        'performed_at',
        'performed_by',
    )

    # 🔎 Search box (optimized)
    search_fields = (
        'job_id',
        'description',
        'mukkadam_id__exact',
        'transport_provider_id__exact',
    )

    # ⏱ Default ordering
    ordering = ('-performed_at',)

    # 📆 Date hierarchy (huge UX win)
    date_hierarchy = 'performed_at'

    # 🚀 Performance optimization
    list_select_related = (
        'allocation',
        'payment_request',
        'transport_payment_request',
        'performed_by',
    )

    raw_id_fields = (
        'allocation',
        'payment_request',
        'transport_payment_request',
        'performed_by',
    )

    # 🔒 Make logs immutable
    readonly_fields = (
        'activity_type',
        'description',
        'allocation',
        'payment_request',
        'transport_payment_request',
        'job_id',
        'mukkadam_id',
        'mukkadam_name',
        'transport_provider_id',
        'transport_name',
        'amount',
        'performed_by',
        'performed_at',
        'changes',
        'metadata',
    )

    # 🧾 Better form layout
    fieldsets = (
        ('Activity Info', {
            'fields': (
                'activity_type',
                'description',
                'performed_at',
                'performed_by',
            )
        }),
        ('Related Objects', {
            'fields': (
                'allocation',
                'payment_request',
                'transport_payment_request',
            )
        }),
        ('Reference IDs', {
            'fields': (
                'job_id',
                'mukkadam_id',
                'mukkadam_name',
                'transport_provider_id',
                'transport_name',
            )
        }),
        ('Financial', {
            'fields': ('amount',)
        }),
        ('Change Tracking', {
            'fields': ('changes',),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',),
        }),
    )

    # 🎨 Color-coded activity type
    def colored_activity(self, obj):
        colors = {
            'allocation_created': '#2563eb',   # blue
            'allocation_updated': '#9333ea',   # purple
            'allocation_deleted': '#f59e0b',   # amber
            'payment_requested': '#0ea5e9',    # sky
            'payment_paid': '#16a34a',         # green
            'payment_rejected': '#dc2626',     # red
            'transport_payment_requested': '#0ea5e9',
            'transport_payment_paid': '#16a34a',
            'transport_payment_rejected': '#dc2626',
        }
        color = colors.get(obj.activity_type, "#C9CCD2")
        return format_html(
            '<strong style="color:{}">{}</strong>',
            color,
            obj.get_activity_type_display()
        )

    colored_activity.short_description = 'Activity'

    # ❌ Disable add/delete (system-generated logs only)
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from django.contrib import admin
from django.utils.html import format_html
from .models import ActivityEditHistory, ActivityLostRecord


# ============================
# Activity Edit History Admin
# ============================

@admin.register(ActivityEditHistory)
class ActivityEditHistoryAdmin(admin.ModelAdmin):
    """
    Admin for tracking all edits made to JobActivity
    """

    list_display = (
        'job_activity',
        'edited_by',
        'edited_at',
        'short_reason',
    )

    list_display_links = ('job_activity',)

    list_filter = (
        'edited_at',
        'edited_by',
    )

    search_fields = (
        'job_activity__id',
        'reason',
        'edited_by__username',
    )

    ordering = ('-edited_at',)
    date_hierarchy = 'edited_at'

    raw_id_fields = (
        'job_activity',
        'edited_by',
    )

    readonly_fields = (
        'job_activity',
        'edited_by',
        'edited_at',
        'reason',
        'changes',
    )

    fieldsets = (
        ('Edit Info', {
            'fields': (
                'job_activity',
                'edited_by',
                'edited_at',
            )
        }),
        ('Reason', {
            'fields': ('reason',),
        }),
        ('Changes', {
            'fields': ('changes',),
            'classes': ('collapse',),
        }),
    )

    def short_reason(self, obj):
        return obj.reason[:60] + '...' if len(obj.reason) > 60 else obj.reason

    short_reason.short_description = 'Edit Reason'

    # 🔒 Immutable logs
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============================
# Activity Lost Record Admin
# ============================

@admin.register(ActivityLostRecord)
class ActivityLostRecordAdmin(admin.ModelAdmin):
    """
    Admin for activities marked as lost
    """

    list_display = (
        'job_activity',
        'status_badge',
        'marked_by',
        'marked_at',
        'unmarked_by',
    )

    list_display_links = ('job_activity',)

    list_filter = (
        'is_active',
        'marked_at',
        'marked_by',
    )

    search_fields = (
        'job_activity__id',
        'reason',
        'marked_by__username',
        'unmarked_by__username',
    )

    ordering = ('-marked_at',)
    date_hierarchy = 'marked_at'

    raw_id_fields = (
        'job_activity',
        'marked_by',
        'unmarked_by',
    )

    readonly_fields = (
        'job_activity',
        'marked_by',
        'marked_at',
        'reason',
        'is_active',
        'unmarked_by',
        'unmarked_at',
        'unmark_reason',
    )

    fieldsets = (
        ('Lost Activity Info', {
            'fields': (
                'job_activity',
                'is_active',
            )
        }),
        ('Marked As Lost', {
            'fields': (
                'marked_by',
                'marked_at',
                'reason',
            )
        }),
        ('Unmark Info', {
            'fields': (
                'unmarked_by',
                'unmarked_at',
                'unmark_reason',
            ),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color:#dc2626; font-weight:600;">ACTIVE</span>'
            )
        return format_html(
            '<span style="color:#16a34a; font-weight:600;">UNMARKED</span>'
        )

    status_badge.short_description = 'Status'

    # 🔒 Immutable records
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
