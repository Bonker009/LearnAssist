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

export interface AutoStopOptions {
  /**
   * Receives how close the recording is to stopping on silence, 0..1, so the UI can
   * show it coming. A ref for the same reason as the level.
   */
  silenceRef?: React.RefObject<number>;
  /** Silence after speech that ends the recording. Khmer speakers may want longer. */
  silenceMs?: number;
  /** Give up if nothing is said within this long, rather than transcribe silence. */
  noSpeechMs?: number;
}

/** How long the room is sampled before listening for speech, to learn its noise. */
const CALIBRATION_MS = 300;
/** Sound above the threshold for this long counts as speech, not a click or bump. */
const SPEECH_CONFIRM_MS = 120;

/**
 * Record a short voice message in the browser.
 *
 * Recognition is not done here: the Web Speech API's Khmer support is Chrome-only
 * and sends audio to Google. The clip is sent to our own Whisper instead, which
 * works in every browser and keeps the audio on the server.
 *
 * The recording stops by itself once the student has spoken and then gone quiet.
 * Silence is judged against the room's own noise, measured in the first moments,
 * so a noisy classroom doesn't keep it open forever and a quiet one doesn't cut in
 * early. `stop()` still finishes it at any time, and MAX_RECORDING_SECONDS caps it.
 */
export function useVoiceRecorder(
  onRecorded: (clip: Blob) => void,
  /**
   * Receives the live 0..1 input level. A ref, not state: the meter updates every
   * animation frame, and state would re-render every consumer 60 times a second.
   */
  levelRef?: React.RefObject<number>,
  { silenceRef, silenceMs = 1500, noSpeechMs = 8000 }: AutoStopOptions = {},
) {
  const [state, setState] = React.useState<State>("idle");
  const [elapsed, setElapsed] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const ownLevel = React.useRef(0);
  const level = levelRef ?? ownLevel;
  const ownSilence = React.useRef(0);
  const silence = silenceRef ?? ownSilence;

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

    // Voice activity: RMS energy, smoothed, compared with the room's noise floor.
    const began = performance.now();
    let previous = began;
    let energy = 0;
    let floorSum = 0;
    let floorCount = 0;
    let threshold = Infinity;
    let loudFor = 0;
    let quietFor = 0;
    let speaking = false;

    const meter = () => {
      const now = performance.now();
      const dt = now - previous;
      previous = now;

      analyser.getByteTimeDomainData(samples);
      let peak = 0;
      let sumSquares = 0;
      for (const sample of samples) {
        const centred = sample - 128;
        peak = Math.max(peak, Math.abs(centred));
        sumSquares += (centred / 128) ** 2;
      }
      level.current = Math.min(peak / 64, 1);
      energy += (Math.sqrt(sumSquares / samples.length) - energy) * 0.3;

      if (now - began < CALIBRATION_MS) {
        floorSum += energy;
        floorCount += 1;
      } else {
        if (threshold === Infinity) {
          const floor = floorCount ? floorSum / floorCount : 0;
          // Well clear of the room's noise, with a minimum for a near-silent room,
          // and capped so a student who starts talking straight away (and so is
          // counted as "noise") is still heard as speech.
          threshold = Math.min(0.04, Math.max(floor * 3, floor + 0.012, 0.015));
        }
        if (energy > threshold) {
          loudFor += dt;
          quietFor = 0;
          if (loudFor >= SPEECH_CONFIRM_MS) speaking = true;
        } else if (energy < threshold * 0.8) {
          // Below a slightly lower bar to stop, so a voice hovering at the
          // threshold doesn't flicker between speech and silence.
          loudFor = 0;
          if (speaking) quietFor += dt;
        }
        silence.current = speaking ? Math.min(quietFor / silenceMs, 1) : 0;

        if (speaking && quietFor >= silenceMs) {
          media.stop();
          return;
        }
        if (!speaking && now - began >= noSpeechMs) {
          cancelled.current = true;
          setError("Didn't hear anything. Tap the mic and try again.");
          media.stop();
          return;
        }
      }
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
      silence.current = 0;
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
  }, [supported, level, silence, silenceMs, noSpeechMs]);

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
    silenceRef: silence,
    error,
    supported,
    start,
    stop,
    cancel,
    clearError: () => setError(null),
  };
}
