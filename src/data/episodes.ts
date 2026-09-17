export interface Voiceover {
  name: string;
  src: string;
  audioSrc?: string;
  label: string;
}

export interface Episode {
  id: string;
  season: number;
  episode: number;
  title: string;
  poster: string;
  voiceovers: Voiceover[];
}

const BASE = "/s3";

const episodeTitles: Record<number, string> = {
  1: "Tragedy",
  2: "Incubation",
  3: "Dove",
  4: "Supper",
  5: "Scars",
  6: "Cloudburst",
  7: "Captivity",
  8: "Circular",
  9: "Birdcage",
  10: "Aogiri",
  11: "High Spirits",
  12: "Ghoul",
};

export const episodes: Episode[] = Array.from({ length: 12 }, (_, i) => ({
  id: `s1e${i + 1}`,
  season: 1,
  episode: i + 1,
  title: episodeTitles[i + 1] ?? `Episode ${i + 1}`,
  poster: `${BASE}/season1/poster${String(i + 1).padStart(2, "0")}.jpg`,
  voiceovers: [
    {
      name: "SATRip",
      src: `${BASE}/season1/ep${String(i + 1).padStart(2, "0")}.mp4`,
      label: "SATRip",
    },
  ],
}));
