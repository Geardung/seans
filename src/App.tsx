import { useState, useEffect } from "react";
import { episodes } from "./data/episodes";
import { Player } from "./components/Player";
import type { Episode, Voiceover } from "./data/episodes";
import "./App.css";

export default function App() {
  const savedEpId = localStorage.getItem("player-episode");
  const savedEp = savedEpId ? episodes.find((e) => e.id === savedEpId) : null;

  const [currentEpisode, setCurrentEpisode] = useState<Episode>(savedEp ?? episodes[0]);
  const [currentVoiceover, setCurrentVoiceover] = useState<Voiceover>(
    (savedEp ?? episodes[0]).voiceovers[0]
  );

  const handleEpisodeChange = (ep: Episode) => {
    setCurrentEpisode(ep);
    setCurrentVoiceover(ep.voiceovers[0]);
    localStorage.setItem("player-episode", ep.id);
  };

  // Persist initial episode on first visit
  useEffect(() => {
    if (!savedEpId) {
      localStorage.setItem("player-episode", currentEpisode.id);
    }
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1>
          <span className="accent">Tokyo</span> Ghoul
        </h1>
      </header>

      <main className="main">
        <Player
          src={currentVoiceover.src}
          poster={currentEpisode.poster}
          episodes={episodes}
          currentEpisode={currentEpisode}
          onPrev={() => {
            const prev = episodes.find(
              (e) => e.episode === currentEpisode.episode - 1
            );
            if (prev) handleEpisodeChange(prev);
          }}
          onNext={() => {
            const next = episodes.find(
              (e) => e.episode === currentEpisode.episode + 1
            );
            if (next) handleEpisodeChange(next);
          }}
          onEpisodeChange={handleEpisodeChange}
        />
      </main>

      <footer className="footer">
        <span>Tokyo Ghoul Season 1</span>
      </footer>
    </div>
  );
}
