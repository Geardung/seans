import { useEffect, useRef } from "react";
import Plyr from "plyr";
import "plyr/dist/plyr.css";
import type { Episode } from "../data/episodes";

interface PlayerProps {
  src: string;
  poster: string;
  episodes: Episode[];
  currentEpisode: Episode;
  onPrev: () => void;
  onNext: () => void;
  onEpisodeChange: (ep: Episode) => void;
}

export function Player({
  src,
  poster,
  episodes,
  currentEpisode,
  onPrev,
  onNext,
  onEpisodeChange,
}: PlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<Plyr | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const posterRef = useRef<HTMLDivElement | null>(null);
  const onPrevRef = useRef(onPrev);
  const onNextRef = useRef(onNext);
  const onEpisodeChangeRef = useRef(onEpisodeChange);

  onPrevRef.current = onPrev;
  onNextRef.current = onNext;
  onEpisodeChangeRef.current = onEpisodeChange;

  // Create Plyr once
  useEffect(() => {
    if (!containerRef.current) return;

    const video = document.createElement("video");
    video.setAttribute("playsinline", "");
    video.setAttribute("preload", "none");

    const source = document.createElement("source");
    source.src = src;
    source.type = "video/mp4";
    video.appendChild(source);

    containerRef.current.innerHTML = "";
    containerRef.current.appendChild(video);
    videoRef.current = video;

    const savedVolume = parseFloat(localStorage.getItem("player-volume") || "0.3");

    const player = new Plyr(video, {
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
      settings: ["speed"],
      speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] },
      volume: savedVolume,
      muted: false,
    });

    playerRef.current = player;

    // Save volume on change
    player.on("volumechange", () => {
      localStorage.setItem("player-volume", String(player.volume));
    });

    // Save playback position every second
    const saveInterval = setInterval(() => {
      const epId = localStorage.getItem("player-episode");
      if (epId && !video.paused && video.currentTime > 0) {
        localStorage.setItem(`player-time-${epId}`, String(Math.floor(video.currentTime)));
      }
    }, 1000);

    // Create poster overlay INSIDE .plyr__video-wrapper (between video and controls)
    const videoWrapper = containerRef.current.querySelector(".plyr__video-wrapper");
    if (videoWrapper) {
      const posterDiv = document.createElement("div");
      posterDiv.className = "poster-overlay";
      posterDiv.style.backgroundImage = `url(${poster})`;
      posterRef.current = posterDiv;

      posterDiv.addEventListener("click", () => video.play());
      video.addEventListener("play", () => {
        posterDiv.style.opacity = "0";
        posterDiv.style.pointerEvents = "none";
      });

      videoWrapper.appendChild(posterDiv);
    }

    // Inject prev/next buttons + episode selector into Plyr controls
    const injectControls = () => {
      const controls = containerRef.current?.querySelector(".plyr__controls");
      if (!controls || controls.querySelector(".plyr-ep-btn")) return;

      const wrapper = document.createElement("div");
      wrapper.className = "plyr-ep-controls";
      wrapper.style.display = "flex";
      wrapper.style.alignItems = "center";
      wrapper.style.gap = "4px";

      const prevBtn = document.createElement("button");
      prevBtn.className = "plyr__control plyr-ep-btn";
      prevBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>`;
      prevBtn.title = "Previous episode";
      prevBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        onPrevRef.current();
      });

      const sel = document.createElement("select");
      sel.className = "plyr-ep-select";
      for (const ep of episodes) {
        const opt = document.createElement("option");
        opt.value = ep.id;
        opt.textContent = `${ep.episode}. ${ep.title}`;
        opt.selected = ep.id === currentEpisode.id;
        sel.appendChild(opt);
      }
      sel.addEventListener("change", () => {
        const ep = episodes.find((ep) => ep.id === sel.value);
        if (ep) onEpisodeChangeRef.current(ep);
      });

      const nextBtn = document.createElement("button");
      nextBtn.className = "plyr__control plyr-ep-btn";
      nextBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 6 15 12 9 18"/></svg>`;
      nextBtn.title = "Next episode";
      nextBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        onNextRef.current();
      });

      wrapper.appendChild(prevBtn);
      wrapper.appendChild(sel);
      wrapper.appendChild(nextBtn);

      const fsBtn = controls.querySelector('[data-plyr="fullscreen"]');
      if (fsBtn) {
        controls.insertBefore(wrapper, fsBtn);
      } else {
        controls.appendChild(wrapper);
      }
    };

    player.on("ready", injectControls);
    setTimeout(injectControls, 100);

    return () => {
      clearInterval(saveInterval);
      player.destroy();
      playerRef.current = null;
      videoRef.current = null;
    };
  }, []); // Mount once

  // Update source + poster when episode changes
  useEffect(() => {
    const video = videoRef.current;
    const posterDiv = posterRef.current;
    if (!video) return;

    // Update poster overlay
    if (posterDiv) {
      posterDiv.style.backgroundImage = `url(${poster})`;
      posterDiv.style.opacity = "1";
      posterDiv.style.pointerEvents = "auto";
    }

    const source = video.querySelector("source");
    if (source) source.src = src;
    video.load();

    // Restore saved position for this episode
    const epId = localStorage.getItem("player-episode");
    if (epId) {
      const savedTime = parseFloat(localStorage.getItem(`player-time-${epId}`) || "0");
      if (savedTime > 0) {
        const onLoaded = () => {
          video.currentTime = savedTime;
          video.removeEventListener("loadedmetadata", onLoaded);
        };
        video.addEventListener("loadedmetadata", onLoaded);
      }
    }
  }, [src, poster]);

  // Keep episode selector in sync
  useEffect(() => {
    const sel = containerRef.current?.querySelector(".plyr-ep-select") as HTMLSelectElement | null;
    if (sel) sel.value = currentEpisode.id;

    const prevBtn = containerRef.current?.querySelector(".plyr-ep-btn") as HTMLButtonElement | null;
    if (prevBtn) prevBtn.disabled = currentEpisode.episode <= 1;

    const btns = containerRef.current?.querySelectorAll(".plyr-ep-btn");
    if (btns && btns[1]) (btns[1] as HTMLButtonElement).disabled = currentEpisode.episode >= episodes.length;
  }, [currentEpisode, episodes]);

  return <div className="player-wrapper" ref={containerRef} />;
}
