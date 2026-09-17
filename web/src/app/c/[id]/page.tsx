import { ChatApp } from "@/components/chat/chat-app";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ChatApp key={id} initialConversationId={id} />;
}
