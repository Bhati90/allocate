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


@admin.register(FarmerCall)
class FarmerCallAdmin(admin.ModelAdmin):
    # --------------------
    # LIST VIEW
    # --------------------
    list_display = (
        'mobile_number',
        'purpose',
        'status_badge',
        'direction',
        'duration',
        'talk_time',
        'has_recording_display',
        'initiated_at',
    )

    list_filter = (
        'status',
        'purpose',
        'direction',
        'initiated_at',
    )

    search_fields = (
        'mobile_number',
        'call_sid',
        'job_id',
        'user_id',
        'from_number',
    )

    ordering = ('-initiated_at',)

    # --------------------
    # READONLY FIELDS
    # --------------------
    readonly_fields = (
        'call_sid',
        'initiated_at',
        'answered_at',
        'completed_at',
        'created_time',
        'updated_time',
        'recording_preview',
        'webhook_data',
        'created_by',
    )

    # --------------------
    # FIELD GROUPING
    # --------------------
    fieldsets = (
        ('Call Identifiers', {
            'fields': (
                'call_sid',
                'user_id',
                'job_id',
                'created_by',
            )
        }),

        ('Call Parties', {
            'fields': (
                'mobile_number',
                'from_number',
                'virtual_number',
                'direction',
            )
        }),

        ('Call Status', {
            'fields': (
                'purpose',
                'status',
                'state',
            )
        }),

        ('Call Metrics', {
            'fields': (
                'duration',
                'talk_time',
                'price',
            )
        }),

        ('Recording', {
            'fields': (
                'recording_preview',
                'recording_url',
                'recording_urls',
            )
        }),

        ('Timestamps', {
            'fields': (
                'initiated_at',
                'answered_at',
                'completed_at',
                'created_time',
                'updated_time',
            )
        }),

        ('Exotel Metadata', {
            'fields': (
                'custom_field',
                'legs_url',
                'webhook_data',
            )
        }),

        ('Notes', {
            'fields': ('notes',)
        }),
    )

    # --------------------
    # BADGES & HELPERS
    # --------------------
    def status_badge(self, obj):
        color_map = {
            'completed': 'green',
            'answered': 'blue',
            'in-progress': 'orange',
            'ringing': 'orange',
            'failed': 'red',
            'busy': 'red',
            'no-answer': 'gray',
            'cancelled': 'gray',
            'pending': 'gray',
            'queued': 'gray',
            'terminal': 'black',
        }
        color = color_map.get(obj.status, 'gray')

        return format_html(
            '<span style="padding:4px 8px; border-radius:6px; background:{}; color:white;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = "Status"

    def has_recording_display(self, obj):
        return "🎧 Yes" if obj.has_recording else "—"
    has_recording_display.short_description = "Recording"

    def recording_preview(self, obj):
        url = obj.primary_recording_url
        if url:
            return format_html(
                '<audio controls style="width:300px;">'
                '<source src="{}" type="audio/mpeg">'
                '</audio>',
                url
            )
        return "No recording available"
    recording_preview.short_description = "Play Recording"

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
