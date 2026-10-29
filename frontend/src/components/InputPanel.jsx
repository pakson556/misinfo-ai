import { FileText, ImageUp, Link2, Loader2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

const MODES = [
  { id: "text", label: "Text", icon: FileText },
  { id: "url", label: "Link", icon: Link2 },
  { id: "image", label: "Screenshot", icon: ImageUp },
];

const EXAMPLES = [
  {
    label: "A viral health post",
    text: "BREAKING!!! Doctors don't want you to know this: drinking hot lemon water every morning kills cancer cells. A nurse told me hospitals have known for years. Share this before they delete it!",
  },
  {
    label: "A space myth",
    text: "The Great Wall of China is the only man-made structure visible from space with the naked eye, and astronauts on the Moon have confirmed seeing it.",
  },
  {
    label: "A plain news paragraph",
    text: "Mount Everest, on the border of Nepal and China, is the highest mountain above sea level. Its summit was first reached in 1953 by Edmund Hillary and Tenzing Norgay.",
  },
];

export default function InputPanel({ onSubmit, busy, onCancel }) {
  const [mode, setMode] = useState("text");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState(null);
  const [useWeb, setUseWeb] = useState(true);
  const [drag, setDrag] = useState(false);
  const fileInput = useRef(null);

  const preview = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  useEffect(() => {
    // Paste an image anywhere on the page to check it
    const onPaste = (e) => {
      const img = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
      if (img) {
        setFile(img.getAsFile());
        setMode("image");
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  const ready = mode === "text" ? text.trim().length > 0 : mode === "url" ? /^https?:\/\/\S+\.\S+/.test(url.trim()) : !!file;

  const submit = (e) => {
    e?.preventDefault();
    if (!ready || busy) return;
    if (mode === "text") onSubmit({ text: text.trim(), useWeb });
    if (mode === "url") onSubmit({ url: url.trim(), useWeb });
    if (mode === "image") onSubmit({ file, useWeb });
  };

  return (
    <form onSubmit={submit} className="rounded-xl border border-rule bg-sheet shadow-[0_1px_0_#DDE1E8,0_12px_32px_-18px_rgba(24,32,46,0.25)]">
      <div role="tablist" aria-label="What do you want to check?" className="flex gap-1 border-b border-rule px-3 pt-3">
        {MODES.map((m) => {
          const Icon = m.icon;
          const on = mode === m.id;
          return (
            <button
              key={m.id}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setMode(m.id)}
              className={`-mb-px flex items-center gap-2 border-b-2 px-3 pb-2.5 pt-1 text-sm font-medium transition-colors ${
                on ? "border-ink text-ink" : "border-transparent text-ink-faint hover:text-ink-soft"
              }`}
            >
              <Icon size={16} /> {m.label}
            </button>
          );
        })}
      </div>

      <div className="p-4">
        {mode === "text" && (
          <>
            <label htmlFor="check-text" className="sr-only">Text to check</label>
            <textarea
              id="check-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && submit()}
              rows={7}
              placeholder="Paste a post, message or article…"
              className="block w-full resize-y bg-transparent font-serif text-[1.075rem] leading-[1.75] text-ink placeholder:text-ink-faint focus:outline-none"
            />
            {!text && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-ink-faint">Try:</span>
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex.label}
                    type="button"
                    onClick={() => setText(ex.text)}
                    className="rounded-full border border-rule px-3 py-1 text-ink-soft hover:border-ink-faint hover:text-ink"
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        {mode === "url" && (
          <div className="py-6">
            <label htmlFor="check-url" className="text-sm text-ink-soft">Link to an article or post</label>
            <input
              id="check-url"
              type="url"
              inputMode="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://"
              className="mt-2 block w-full border-b border-rule bg-transparent pb-2 font-serif text-lg text-ink placeholder:text-ink-faint focus:border-ink focus:outline-none"
            />
            <p className="mt-2 text-xs text-ink-faint">We read the article's text and check the claims in it.</p>
          </div>
        )}

        {mode === "image" && (
          <div
            onDragOver={(e) => (e.preventDefault(), setDrag(true))}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files?.[0];
              if (f?.type.startsWith("image/")) setFile(f);
            }}
            className={`relative grid min-h-[11rem] place-items-center rounded-lg border border-dashed transition-colors ${
              drag ? "border-cobalt bg-cobalt-wash" : "border-rule"
            }`}
          >
            {file ? (
              <div className="flex items-center gap-4 p-4">
                <img src={preview} alt="Screenshot to check" className="max-h-36 rounded-md border border-rule" />
                <div className="text-sm">
                  <p className="font-medium text-ink">{file.name || "Pasted image"}</p>
                  <p className="text-ink-faint">{(file.size / 1024).toFixed(0)} KB</p>
                  <button type="button" onClick={() => setFile(null)} className="mt-2 inline-flex items-center gap-1 text-ink-soft hover:text-refuted">
                    <X size={14} /> Remove
                  </button>
                </div>
              </div>
            ) : (
              <button type="button" onClick={() => fileInput.current?.click()} className="p-6 text-center">
                <ImageUp className="mx-auto text-ink-faint" />
                <span className="mt-2 block text-sm font-medium text-ink">Drop a screenshot, paste it, or choose a file</span>
                <span className="block text-xs text-ink-faint">PNG or JPG, up to 8 MB</span>
              </button>
            )}
            <input ref={fileInput} type="file" accept="image/*" hidden onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-soft">
          <input type="checkbox" checked={useWeb} onChange={(e) => setUseWeb(e.target.checked)} className="h-4 w-4 accent-cobalt" />
          Search the web for evidence
        </label>
        {busy ? (
          <button type="button" onClick={onCancel} className="inline-flex items-center gap-2 rounded-lg border border-rule px-4 py-2 text-sm font-medium text-ink hover:bg-paper">
            <Loader2 size={16} className="animate-spin" /> Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!ready}
            className="rounded-lg bg-ink px-5 py-2 text-sm font-semibold text-paper transition-colors hover:bg-cobalt disabled:cursor-not-allowed disabled:bg-rule disabled:text-ink-faint"
          >
            Check it
          </button>
        )}
      </div>
    </form>
  );
}
