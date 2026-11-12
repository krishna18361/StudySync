import { useRef, useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";

const ALLOWED_EXT = [".pdf", ".docx", ".pptx", ".txt", ".md", ".text"];
const MAX_MB = 25;

const FILE_ICONS = {
  pdf: "📕",
  docx: "📘",
  doc: "📘",
  pptx: "📙",
  ppt: "📙",
  md: "📝",
  txt: "📄",
  text: "📄",
};

function extOf(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

function iconFor(name) {
  return FILE_ICONS[extOf(name).replace(".", "")] || "📄";
}

function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(0)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function validate(file) {
  const ext = extOf(file.name);
  if (!ALLOWED_EXT.includes(ext)) {
    return `Unsupported format '${ext || "unknown"}'. Use PDF, DOCX, PPTX, TXT or MD.`;
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    return `File is ${formatBytes(file.size)} — the limit is ${MAX_MB} MB.`;
  }
  return null;
}

let idSeq = 0;

export default function UploadDropzone({ onUploaded }) {
  const toast = useToast();
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [queue, setQueue] = useState([]);

  function patchItem(id, patch) {
    setQueue((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  async function uploadFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const accepted = [];
    for (const file of files) {
      const error = validate(file);
      if (error) {
        const id = ++idSeq;
        setQueue((prev) => [
          ...prev,
          { id, name: file.name, size: file.size, status: "error", progress: 0, error },
        ]);
        toast.error("File rejected", `${file.name}: ${error}`);
        // clean up rejected rows after a short delay
        setTimeout(() => setQueue((prev) => prev.filter((item) => item.id !== id)), 6000);
      } else {
        accepted.push(file);
      }
    }

    for (const file of accepted) {
      const id = ++idSeq;
      setQueue((prev) => [
        ...prev,
        { id, name: file.name, size: file.size, status: "uploading", progress: 0 },
      ]);
      try {
        const doc = await api.upload(file, (pct) => patchItem(id, { progress: pct }));
        patchItem(id, { status: "processing", progress: 100 });
        if (doc.status === "failed") {
          patchItem(id, { status: "error", error: doc.error || "Processing failed." });
          toast.error("Processing failed", `${file.name}: ${doc.error || "Could not index the file."}`);
        } else {
          patchItem(id, { status: "done", progress: 100 });
          toast.success("Upload complete", `${file.name} is ready to study.`);
          if (onUploaded) onUploaded(doc);
          setTimeout(() => setQueue((prev) => prev.filter((item) => item.id !== id)), 4000);
        }
      } catch (err) {
        const message = err?.message || String(err);
        patchItem(id, { status: "error", error: message });
        toast.error(
          "Upload failed",
          message.toLowerCase().includes("failed to fetch")
            ? "Could not reach the backend. Make sure the FastAPI server is running."
            : message
        );
      }
    }
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    uploadFiles(event.dataTransfer.files);
  }

  function onBrowse(event) {
    uploadFiles(event.target.files);
    event.target.value = "";
  }

  return (
    <div className="dropzone-wrap">
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragging(false);
        }}
        onDrop={onDrop}
      >
        <span className="dropzone-icon" aria-hidden="true">
          ⬆
        </span>
        <span className="dropzone-title">
          {dragging ? "Drop to upload" : "Upload Material"}
        </span>
        <span className="dropzone-hint">Drag &amp; drop or click to browse</span>
        <span className="dropzone-formats">PDF · PPTX · DOCX · TXT · MD — up to {MAX_MB} MB</span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ALLOWED_EXT.join(",")}
          onChange={onBrowse}
          hidden
        />
      </div>

      {queue.length > 0 ? (
        <div className="upload-queue">
          {queue.map((item) => (
            <div key={item.id} className={`upload-item ${item.status}`}>
              <span className="upload-item-icon" aria-hidden="true">
                {iconFor(item.name)}
              </span>
              <div className="upload-item-main">
                <div className="upload-item-topline">
                  <span className="upload-item-name" title={item.name}>
                    {item.name}
                  </span>
                  <span className="upload-item-size">{formatBytes(item.size)}</span>
                </div>
                {item.status === "error" ? (
                  <span className="upload-item-msg error">{item.error}</span>
                ) : (
                  <>
                    <div className="upload-track">
                      <div
                        className={`upload-fill ${item.status}`}
                        style={{ width: `${Math.max(item.progress, 4)}%` }}
                      />
                    </div>
                    <span className="upload-item-msg">
                      {item.status === "uploading"
                        ? `Uploading… ${item.progress}%`
                        : item.status === "processing"
                          ? "Indexing & generating summary…"
                          : "Ready ✓"}
                    </span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
