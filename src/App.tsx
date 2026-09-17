import { useState } from "react";
import { episodes } from "./data/episodes";
import { Player } from "./components/Player";
import { Controls } from "./components/Controls";
import type { Episode, Voiceover } from "./data/episodes";
import "./App.css";

export default function App() {
  const [currentEpisode, setCurrentEpisode] = useState<Episode>(episodes[0]);
  const [currentVoiceover, setCurrentVoiceover] = useState<Voiceover>(
    episodes[0].voiceovers[0]
  );

  const handleEpisodeChange = (ep: Episode) => {
    setCurrentEpisode(ep);
    setCurrentVoiceover(ep.voiceovers[0]);
  };

  const handleVoiceoverChange = (v: Voiceover) => {
    setCurrentVoiceover(v);
  };

  return (
    <div className="app">
      <header className="header">
        <h1>
          <span className="accent">Tokyo</span> Ghoul
        </h1>
      </header>

      <main className="main">
        <Player src={currentVoiceover.src} audioSrc={currentVoiceover.audioSrc} />
        <Controls
          episodes={episodes}
          currentEpisode={currentEpisode}
          currentVoiceover={currentVoiceover}
          onEpisodeChange={handleEpisodeChange}
          onVoiceoverChange={handleVoiceoverChange}
        />
      </main>

      <footer className="footer">
        <span>Tokyo Ghoul Season 1</span>
      </footer>
    </div>
  );
}
