import { supabase } from "@/integrations/supabase/client";

export type NotificationType = "booking" | "assignment" | "completion" | "payment" | "review";

export async function createNotification({
  userId,
  type,
  title,
  message,
  bookingId,
}: {
  userId: string;
  type: NotificationType;
  title: string;
  message: string;
  bookingId?: string;
}) {
  const { error } = await supabase.from("notifications").insert({
    user_id: userId,
    type,
    title,
    message,
    booking_id: bookingId || null,
  });

  if (error) {
    console.error("Failed to create notification:", error);
  }
}

// Get operations head user ID
async function getOperationsHeadId(): Promise<string | null> {
  const { data } = await supabase
    .from("profiles")
    .select("id")
    .eq("role", "operations_head")
    .limit(1)
    .single();
  
  return data?.id || null;
}

// Notify when new booking is created
export async function notifyNewBooking(
  bookingId: string,
  farmerName: string,
  activityName: string,
  requestedDate: string
) {
  const opsHeadId = await getOperationsHeadId();
  if (!opsHeadId) return;

  await createNotification({
    userId: opsHeadId,
    type: "booking",
    title: "New Booking Received",
    message: `${farmerName} requested ${activityName} for ${requestedDate}`,
    bookingId,
  });
}

// Notify when team member is assigned
export async function notifyTeamMemberAssigned(
  bookingId: string,
  teamMemberId: string,
  farmerName: string,
  activityName: string
) {
  await createNotification({
    userId: teamMemberId,
    type: "assignment",
    title: "New Job Assigned",
    message: `You've been assigned to handle ${farmerName}'s ${activityName}. Please find and allocate a mukadam.`,
    bookingId,
  });
}

// Notify when mukadam is allocated (pending approval)
export async function notifyMukadamAllocated(
  bookingId: string,
  mukadamName: string,
  farmerName: string,
  activityName: string
) {
  const opsHeadId = await getOperationsHeadId();
  if (!opsHeadId) return;

  await createNotification({
    userId: opsHeadId,
    type: "assignment",
    title: "Awaiting Approval",
    message: `${mukadamName} has been allocated to ${farmerName}'s ${activityName}. Please review and approve.`,
    bookingId,
  });
}

// Notify when allocation is approved
export async function notifyAllocationApproved(
  bookingId: string,
  teamMemberId: string,
  farmerName: string,
  mukadamName: string
) {
  await createNotification({
    userId: teamMemberId,
    type: "completion",
    title: "Allocation Approved",
    message: `Your allocation of ${mukadamName} to ${farmerName} has been approved. Farmer will be notified.`,
    bookingId,
  });
}

// Notify when job is completed
export async function notifyJobCompleted(
  bookingId: string,
  teamMemberId: string,
  farmerName: string,
  activityName: string
) {
  await createNotification({
    userId: teamMemberId,
    type: "completion",
    title: "Job Completed",
    message: `${farmerName}'s ${activityName} has been marked as completed.`,
    bookingId,
  });

  const opsHeadId = await getOperationsHeadId();
  if (opsHeadId) {
    await createNotification({
      userId: opsHeadId,
      type: "completion",
      title: "Job Completed",
      message: `${farmerName}'s ${activityName} completed by team.`,
      bookingId,
    });
  }
}

// Notify when payment is collected
export async function notifyPaymentCollected(
  bookingId: string,
  amount: number,
  farmerName: string
) {
  const opsHeadId = await getOperationsHeadId();
  if (!opsHeadId) return;

  await createNotification({
    userId: opsHeadId,
    type: "payment",
    title: "Payment Collected",
    message: `₹${amount.toLocaleString("en-IN")} collected from ${farmerName}`,
    bookingId,
  });
}