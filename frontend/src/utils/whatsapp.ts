// utils/whatsapp.ts

export const notifyWhatsAppGroup = (
  note: any,
  jobLabel: string,
  authorName: string
) => {
  const taggedNames = note.mentions
    ?.map((m: any) => m.full_name || m.username)
    .join(', ') || 'team';

  const message =
    `📌 Job Note — ${jobLabel}\n` +
    `👤 By: ${authorName}\n` +
    `👥 Tagged: ${taggedNames}\n\n` +
    `📝 ${note.text}\n\n` +
    `👉 Open app to resolve`;

  // 1. Copy to clipboard
  navigator.clipboard.writeText(message);

  // 2. Open WhatsApp group
  window.open('https://chat.whatsapp.com/HwN8dW1qcWy1R8lhfcujyw', '_blank');
};