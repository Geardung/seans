import { useEffect, useRef } from "react";
import Plyr from "plyr";
import "plyr/dist/plyr.css";

interface PlayerProps {
  src: string;
  audioSrc?: string;
}

export function Player({ src }: PlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<Plyr | null>(null);

  useEffect(() => {
    if (!videoRef.current) return;

    if (playerRef.current) {
      playerRef.current.destroy();
    }

    const video = videoRef.current;
    video.src = src;
    video.load();

    playerRef.current = new Plyr(video, {
      controls: [
        "play-large",
        "rewind",
        "play",
        "fast-forward",
        "progress",
        "current-time",
        "duration",
        "mute",
        "volume",
        "settings",
        "fullscreen",
      ],
      settings: ["speed", "quality"],
      speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] },
    });

    return () => {
      playerRef.current?.destroy();
      playerRef.current = null;
    };
  }, [src]);

  return (
    <div className="player-wrapper">
      <video ref={videoRef} playsInline crossOrigin="anonymous" />
    </div>
  );
}
