import type { Episode, Voiceover } from "../data/episodes";

interface ControlsProps {
  episodes: Episode[];
  currentEpisode: Episode;
  currentVoiceover: Voiceover;
  onEpisodeChange: (ep: Episode) => void;
  onVoiceoverChange: (v: Voiceover) => void;
}

export function Controls({
  episodes,
  currentEpisode,
  currentVoiceover,
  onEpisodeChange,
  onVoiceoverChange,
}: ControlsProps) {
  const seasons = [...new Set(episodes.map((e) => e.season))];

  return (
    <div className="controls">
      <div className="controls-row">
        <div className="control-group">
          <label>Season</label>
          <select value={currentEpisode.season} disabled>
            {seasons.map((s) => (
              <option key={s} value={s}>
                Season {s}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>Episode</label>
          <select
            value={currentEpisode.id}
            onChange={(e) => {
              const ep = episodes.find((ep) => ep.id === e.target.value);
              if (ep) onEpisodeChange(ep);
            }}
          >
            {episodes.map((ep) => (
              <option key={ep.id} value={ep.id}>
                {ep.episode}. {ep.title}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>Voiceover</label>
          <select
            value={currentVoiceover.name}
            onChange={(e) => {
              const v = currentEpisode.voiceovers.find(
                (v) => v.name === e.target.value
              );
              if (v) onVoiceoverChange(v);
            }}
          >
            {currentEpisode.voiceovers.map((v) => (
              <option key={v.name} value={v.name}>
                {v.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="episode-nav">
        <span className="episode-info">
          Episode {currentEpisode.episode} of {episodes.length}
        </span>
      </div>
    </div>
  );
}
