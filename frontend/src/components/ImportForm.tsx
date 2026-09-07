import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ChefIcon } from "./ChefIcon";

type Tab = "url" | "images" | "text";

interface StoredImage {
  name: string;
  dataUrl: string;
}

const TAB_KEY = "import_tab";
const IMAGES_KEY = "import_images";
const MAX_SOURCE_TEXT_CHARS = 100_000;

function loadStoredImages(): StoredImage[] {
  try {
    const raw = sessionStorage.getItem(IMAGES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveStoredImages(images: StoredImage[]) {
  try {
    sessionStorage.setItem(IMAGES_KEY, JSON.stringify(images));
  } catch {
    // sessionStorage full — ignore
  }
}

/** Convert a base64 data URL back to a File object */
async function dataUrlToFile(dataUrl: string, name: string): Promise<File> {
  const res = await fetch(dataUrl);
  const blob = await res.blob();
  return new File([blob], name, { type: blob.type });
}

export function ImportForm({
  onSubmitUrl,
  onSubmitImages,
  onSubmitText,
  initialUrl = "",
  disabled = false,
}: {
  onSubmitUrl: (url: string) => void;
  onSubmitImages: (files: File[]) => void;
  onSubmitText: (text: string) => void;
  initialUrl?: string;
  disabled?: boolean;
}) {
  const [tab, setTab] = useState<Tab>(() => {
    if (initialUrl) return "url";
    try {
      return (sessionStorage.getItem(TAB_KEY) as Tab) || "url";
    } catch {
      return "url";
    }
  });
  const [url, setUrl] = useState(initialUrl);
  const [images, setImages] = useState<StoredImage[]>(loadStoredImages);
  const [text, setText] = useState("");
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const textTrimmed = text.trim();
  const textCount = text.length;
  const textOverLimit = textCount > MAX_SOURCE_TEXT_CHARS;
  const textCanSubmit = !disabled && textTrimmed.length > 0 && !textOverLimit;

  // Persist tab choice
  useEffect(() => {
    sessionStorage.setItem(TAB_KEY, tab);
  }, [tab]);

  // Persist images to sessionStorage whenever they change
  useEffect(() => {
    saveStoredImages(images);
  }, [images]);

  const addFiles = useCallback((input: HTMLInputElement) => {
    const fileList = input.files;
    if (!fileList || fileList.length === 0) return;

    const newFiles = Array.from(fileList);
    input.value = "";

    for (const file of newFiles) {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        setImages((prev) => [...prev, { name: file.name, dataUrl }]);
      };
      reader.readAsDataURL(file);
    }
  }, []);

  function removeImage(index: number) {
    setImages((prev) => prev.filter((_, i) => i !== index));
  }

  function handleUrlSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (disabled || !url.trim()) return;
    onSubmitUrl(url.trim());
  }

  async function handleImageSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (disabled || images.length === 0) return;

    // Reconstruct File objects from stored data URLs
    const files = await Promise.all(
      images.map((img) => dataUrlToFile(img.dataUrl, img.name))
    );
    // Clear stored images after submission
    sessionStorage.removeItem(IMAGES_KEY);
    onSubmitImages(files);
  }

  function handleTextSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!textCanSubmit) return;
    onSubmitText(text);
  }

  return (
    <div className="flex flex-col items-center gap-8 px-6 pt-12">
      <ChefIcon className="h-20 w-20" />

      <p className="text-lg text-muted-foreground">Choose recipe source</p>

      <ToggleGroup
        type="single"
        value={tab}
        onValueChange={(v) => v && setTab(v as Tab)}
        className="grid w-full max-w-sm grid-cols-3 gap-1 rounded-2xl border border-border bg-card/60 p-1 shadow-sm backdrop-blur"
        aria-label="Recipe source"
      >
        <ToggleGroupItem
          value="url"
          disabled={disabled}
          className="min-w-0 justify-center gap-1 rounded-xl px-2 py-2 text-xs font-medium data-[state=on]:border data-[state=on]:border-border data-[state=on]:bg-background data-[state=on]:shadow-sm sm:text-sm"
        >
          <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          <span className="truncate">URL</span>
        </ToggleGroupItem>
        <ToggleGroupItem
          value="images"
          disabled={disabled}
          className="min-w-0 justify-center gap-1 rounded-xl px-2 py-2 text-xs font-medium data-[state=on]:border data-[state=on]:border-border data-[state=on]:bg-background data-[state=on]:shadow-sm sm:text-sm"
        >
          <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
            <circle cx="9" cy="9" r="2" />
            <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
          </svg>
          <span className="truncate">Images</span>
        </ToggleGroupItem>
        <ToggleGroupItem
          value="text"
          disabled={disabled}
          className="min-w-0 justify-center gap-1 rounded-xl px-2 py-2 text-xs font-medium data-[state=on]:border data-[state=on]:border-border data-[state=on]:bg-background data-[state=on]:shadow-sm sm:text-sm"
        >
          <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 6h16" />
            <path d="M4 12h16" />
            <path d="M4 18h10" />
          </svg>
          <span className="truncate">Text</span>
        </ToggleGroupItem>
      </ToggleGroup>

      {tab === "url" && (
        <form onSubmit={handleUrlSubmit} className="flex w-full max-w-sm flex-col gap-6">
          <div className="flex flex-col gap-2">
            <label htmlFor="recipe-url" className="text-sm font-medium text-foreground">
              Recipe page, YouTube, or Instagram URL
            </label>
            <Input
              id="recipe-url"
              type="url"
              placeholder="Recipe page, YouTube, or Instagram link"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              aria-describedby="recipe-url-help"
              className="h-14 bg-card text-base"
              disabled={disabled}
            />
            <p id="recipe-url-help" className="text-sm leading-6 text-muted-foreground">
              Paste a recipe page, YouTube video, or Instagram post/Reel URL.
            </p>
          </div>
          <Button type="submit" size="lg" className="h-14 text-base font-semibold" disabled={disabled || !url.trim()}>
            Continue
          </Button>
        </form>
      )}

      {tab === "images" && (
        <form onSubmit={handleImageSubmit} className="flex w-full max-w-sm flex-col gap-6">
          <div className="grid grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => cameraRef.current?.click()}
              className="flex h-28 flex-col items-center justify-center gap-2 rounded-lg bg-card text-sm text-card-foreground disabled:cursor-not-allowed disabled:opacity-50"
              disabled={disabled}
            >
              <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
                <circle cx="12" cy="13" r="3" />
              </svg>
              Camera
            </button>
            <button
              type="button"
              onClick={() => galleryRef.current?.click()}
              className="flex h-28 flex-col items-center justify-center gap-2 rounded-lg bg-card text-sm text-card-foreground disabled:cursor-not-allowed disabled:opacity-50"
              disabled={disabled}
            >
              <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
                <circle cx="9" cy="9" r="2" />
                <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
              </svg>
              Gallery
            </button>
          </div>

          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => addFiles(e.currentTarget)}
            disabled={disabled}
          />
          <input
            ref={galleryRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => addFiles(e.currentTarget)}
            disabled={disabled}
          />

          {images.length > 0 && (
            <div className="flex flex-wrap gap-3">
              {images.map((img, i) => (
                <div key={`${img.name}-${i}`} className="relative">
                  <img
                    src={img.dataUrl}
                    alt={img.name}
                    className="h-16 w-16 rounded-md object-cover"
                  />
                  <button
                    type="button"
                    onClick={() => removeImage(i)}
                    className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-xs text-destructive-foreground disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={disabled}
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}

          <Button
            type="submit"
            size="lg"
            className="h-14 text-base font-semibold"
            disabled={disabled || images.length === 0}
          >
            Continue
          </Button>
        </form>
      )}

      {tab === "text" && (
        <form onSubmit={handleTextSubmit} className="flex w-full max-w-sm flex-col gap-4">
          <div className="flex flex-col gap-2">
            <textarea
              id="recipe-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste the recipe here..."
              className="min-h-48 w-full resize-y rounded-xl border border-border bg-card px-4 py-3 text-base leading-6 shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
              aria-describedby="recipe-text-help recipe-text-count"
              disabled={disabled}
              spellCheck={true}
            />
            <p id="recipe-text-help" className="text-sm leading-6 text-muted-foreground">
              Paste the recipe text directly. It stays only in this screen until you continue.
            </p>
          </div>

          <div className="flex items-center justify-between gap-3 text-sm">
            <span
              id="recipe-text-count"
              className={textOverLimit ? "text-destructive" : "text-muted-foreground"}
            >
              {textCount.toLocaleString()} / {MAX_SOURCE_TEXT_CHARS.toLocaleString()} characters
            </span>
            <span
              className={
                textOverLimit
                  ? "text-destructive"
                  : textTrimmed.length === 0
                    ? "text-destructive"
                    : "text-muted-foreground"
              }
            >
              {textOverLimit ? "Over limit" : textTrimmed.length === 0 ? "Required" : "Ready"}
            </span>
          </div>

          <Button
            type="submit"
            size="lg"
            className="h-14 text-base font-semibold"
            disabled={!textCanSubmit}
          >
            Continue
          </Button>
        </form>
      )}
    </div>
  );
}
