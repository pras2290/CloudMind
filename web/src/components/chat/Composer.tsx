import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "../ui/button";

const MAX_LEN = 4000;

type Props = { onSend: (text: string) => void; disabled?: boolean; busy?: boolean; placeholder?: string };

export function Composer({ onSend, disabled, busy, placeholder = "Ask about your AWS infrastructure…" }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  useEffect(() => {
    if (!busy && !disabled) ref.current?.focus();
  }, [busy, disabled]);

  const submit = () => {
    const text = value.trim();
    if (!text || busy || disabled) return;
    onSend(text);
    setValue("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4">
      <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-sm transition focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          maxLength={MAX_LEN}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          aria-label="Message"
          className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 disabled:cursor-not-allowed"
        />
        <Button size="icon" className="h-8 w-8 shrink-0 rounded-xl" onClick={submit} disabled={!value.trim() || busy || disabled} aria-label="Send message">
          <ArrowUp />
        </Button>
      </div>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">
        CloudMind answers from your indexed AWS data and documents. Verify critical changes before acting.
      </p>
    </div>
  );
}
