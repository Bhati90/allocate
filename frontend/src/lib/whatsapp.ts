import { supabase } from "@/integrations/supabase/client";

export async function sendWhatsAppNotification({
  bookingId,
  recipientType,
  recipientPhone,
  message,
}: {
  bookingId: string;
  recipientType: "farmer" | "mukadam" | "team";
  recipientPhone: string;
  message: string;
}) {
  // Insert into database
  const { error } = await supabase.from("whatsapp_notifications").insert({
    booking_id: bookingId,
    recipient_type: recipientType,
    recipient_phone: recipientPhone,
    message,
    status: "pending",
  });

  if (error) {
    console.error("Failed to create WhatsApp notification:", error);
    return;
  }

  // TODO: Integrate with actual WhatsApp API (Twilio, Gupshup, etc.)
  // For now, just log
  console.log("WhatsApp notification queued:", {
    to: recipientPhone,
    message,
  });

  // In production, you would call something like:
  // await twilioClient.messages.create({
  //   from: 'whatsapp:+14155238886',
  //   to: `whatsapp:${recipientPhone}`,
  //   body: message
  // });
}

// Helper to send farmer allocation notification
export async function notifyFarmerAllocation({
  bookingId,
  farmerPhone,
  farmerName,
  activityName,
  mukadamName,
  mukadamPhone,
  workDate,
  labourCount,
}: {
  bookingId: string;
  farmerPhone: string;
  farmerName: string;
  activityName: string;
  mukadamName: string;
  mukadamPhone: string;
  workDate: string;
  labourCount: number;
}) {
  const message = `
🌱 FarmOps - Work Confirmed

Dear ${farmerName},

Your ${activityName} has been scheduled:

📅 Date: ${workDate}
👷 Mukadam: ${mukadamName}
👥 Team Size: ${labourCount} labourers
📞 Mukadam Contact: ${mukadamPhone}

The team will arrive early morning. Please ensure:
✓ Farm access is clear
✓ Water available for workers
✓ Any specific instructions shared with mukadam

For queries, contact: +91-XXXXXXXXXX

- FarmOps Team
  `.trim();

  await sendWhatsAppNotification({
    bookingId,
    recipientType: "farmer",
    recipientPhone: farmerPhone,
    message,
  });
}

// Helper to send mukadam job notification
export async function notifyMukadamJob({
  bookingId,
  mukadamPhone,
  mukadamName,
  farmerName,
  farmerPhone,
  farmerLocation,
  activityName,
  acres,
  workDate,
  specialInstructions,
}: {
  bookingId: string;
  mukadamPhone: string;
  mukadamName: string;
  farmerName: string;
  farmerPhone: string;
  farmerLocation: string;
  activityName: string;
  acres: number;
  workDate: string;
  specialInstructions?: string;
}) {
  const message = `
🌱 FarmOps - New Job Assignment

Dear ${mukadamName},

New work assigned:

👨‍🌾 Farmer: ${farmerName}
📞 Contact: ${farmerPhone}
📍 Location: ${farmerLocation}
🔧 Work: ${activityName}
📏 Area: ${acres} acres
📅 Date: ${workDate}

${specialInstructions ? `⚠️ Special Instructions:\n${specialInstructions}\n` : ''}
Please confirm availability and reach out to farmer to discuss details.

- FarmOps Team
  `.trim();

  await sendWhatsAppNotification({
    bookingId,
    recipientType: "mukadam",
    recipientPhone: mukadamPhone,
    message,
  });
}