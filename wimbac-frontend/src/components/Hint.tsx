// src/components/Hint.tsx

interface HintProps {
  message: string;
  visible: boolean;
}

export default function Hint({ message, visible }: HintProps) {
  if (!visible) return null;

  return (
    <div className="hint" dangerouslySetInnerHTML={{ __html: message }} />
  );
}