"use client";

import * as React from "react";

/** Matches `dictation_max_seconds` in the AI service; stop before it would refuse. */
export const MAX_RECORDING_SECONDS = 115;

type State = "idle" | "requesting" | "recording";

/** Opus in WebM where supported (Chrome, Firefox); Safari only records MP4/AAC. */
function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find(
    (type) => MediaRecorder.isTypeSupported(type),
  );
}

/**
 * Record a short voice message in the browser.
 *
 * Recognition is not done here: the Web Speech API's Khmer support is Chrome-only
 * and sends audio to Google. The clip is sent to our own Whisper instead, which
 * works in every browser and keeps the audio on the server.
 */
export function useVoiceRecorder(
  onRecorded: (clip: Blob) => void,
  /**
   * Receives the live 0..1 input level. A ref, not state: the meter updates every
   * animation frame, and state would re-render every consumer 60 times a second.
   */
  levelRef?: React.RefObject<number>,
) {
  const [state, setState] = React.useState<State>("idle");
  const [elapsed, setElapsed] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const ownLevel = React.useRef(0);
  const level = levelRef ?? ownLevel;

  const recorder = React.useRef<MediaRecorder | null>(null);
  const stream = React.useRef<MediaStream | null>(null);
  const cancelled = React.useRef(false);
  const cleanupRef = React.useRef<() => void>(() => {});
  const onRecordedRef = React.useRef(onRecorded);
  React.useEffect(() => {
    onRecordedRef.current = onRecorded;
  }, [onRecorded]);

  const supported =
    typeof window !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia) &&
    typeof MediaRecorder !== "undefined";

  const stop = React.useCallback(() => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const cancel = React.useCallback(() => {
    cancelled.current = true;
    stop();
  }, [stop]);

  const start = React.useCallback(async () => {
    if (!supported) {
      setError("Voice input isn't supported in this browser.");
      return;
    }
    setError(null);
    setState("requesting");
    cancelled.current = false;

    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      setState("idle");
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone access was blocked. Allow it in your browser's site settings."
          : "Couldn't start the microphone.",
      );
      return;
    }

    const mimeType = pickMimeType();
    const media = new MediaRecorder(stream.current, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    media.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };

    // Input level meter, so the student can see the mic is actually hearing them.
    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    audioContext.createMediaStreamSource(stream.current).connect(analyser);
    const samples = new Uint8Array(analyser.frequencyBinCount);
    let frame = 0;
    const meter = () => {
      analyser.getByteTimeDomainData(samples);
      let peak = 0;
      for (const sample of samples) peak = Math.max(peak, Math.abs(sample - 128));
      level.current = Math.min(peak / 64, 1);
      frame = requestAnimationFrame(meter);
    };
    frame = requestAnimationFrame(meter);

    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      const seconds = Math.floor((Date.now() - startedAt) / 1000);
      setElapsed(seconds);
      if (seconds >= MAX_RECORDING_SECONDS) media.stop();
    }, 250);

    const cleanup = () => {
      window.clearInterval(timer);
      cancelAnimationFrame(frame);
      void audioContext.close();
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
      level.current = 0;
      setElapsed(0);
    };
    cleanupRef.current = cleanup;

    media.onstop = () => {
      cleanup();
      setState("idle");
      const clip = new Blob(chunks, { type: media.mimeType || mimeType || "audio/webm" });
      if (!cancelled.current && clip.size > 0) onRecordedRef.current(clip);
    };

    recorder.current = media;
    media.start(250);
    setState("recording");
  }, [supported, level]);

  // Release the microphone if the component unmounts mid-recording.
  React.useEffect(
    () => () => {
      cancelled.current = true;
      if (recorder.current?.state === "recording") recorder.current.stop();
      cleanupRef.current();
    },
    [],
  );

  return {
    state,
    elapsed,
    levelRef: level,
    error,
    supported,
    start,
    stop,
    cancel,
    clearError: () => setError(null),
  };
}
