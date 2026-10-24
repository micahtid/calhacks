import donkeyKongCountry from "../covers/donkey-kong-country-snes.png";
import goldenEye from "../covers/goldeneye-007-n64.jpg";
import kirbysDreamLand from "../covers/kirbys-dream-land-gb.png";
import marioKart64 from "../covers/mario-kart-64-n64.jpg";
import pokemonRed from "../covers/pokemon-red-gb.png";
import sonic2 from "../covers/sonic-2-genesis.jpg";
import starFox from "../covers/star-fox-snes.jpg";
import superMarioWorld from "../covers/super-mario-world-snes.png";
import tetris from "../covers/tetris-gb.jpg";
import zeldaLinksAwakening from "../covers/zelda-links-awakening-gb.png";

// These are the facts every store agrees on. Each store adds its own price, condition, and copy.
export type Game = {
  id: string;
  name: string;
  platform: string;
  console: string;
  publisher: string;
  releaseYear: number;
  genre: string;
  image: string;
};

export const GAMES: Game[] = [
  { id: "pokemon-red-gb", name: "Pokémon Red Version", platform: "Game Boy", console: "Nintendo Game Boy", publisher: "Nintendo", releaseYear: 1998, genre: "Role Playing", image: pokemonRed.src },
  { id: "zelda-links-awakening-gb", name: "The Legend of Zelda: Link's Awakening", platform: "Game Boy", console: "Nintendo Game Boy", publisher: "Nintendo", releaseYear: 1993, genre: "Action & Adventure", image: zeldaLinksAwakening.src },
  { id: "tetris-gb", name: "Tetris", platform: "Game Boy", console: "Nintendo Game Boy", publisher: "Nintendo", releaseYear: 1989, genre: "Puzzle", image: tetris.src },
  { id: "super-mario-world-snes", name: "Super Mario World", platform: "SNES", console: "Nintendo SNES", publisher: "Nintendo", releaseYear: 1991, genre: "Platformer", image: superMarioWorld.src },
  { id: "donkey-kong-country-snes", name: "Donkey Kong Country", platform: "SNES", console: "Nintendo SNES", publisher: "Nintendo", releaseYear: 1994, genre: "Platformer", image: donkeyKongCountry.src },
  { id: "mario-kart-64-n64", name: "Mario Kart 64", platform: "Nintendo 64", console: "Nintendo 64", publisher: "Nintendo", releaseYear: 1997, genre: "Racing", image: marioKart64.src },
  { id: "goldeneye-007-n64", name: "GoldenEye 007", platform: "Nintendo 64", console: "Nintendo 64", publisher: "Nintendo", releaseYear: 1997, genre: "Shooter", image: goldenEye.src },
  { id: "sonic-2-genesis", name: "Sonic the Hedgehog 2", platform: "Sega Genesis", console: "Sega Genesis", publisher: "SEGA", releaseYear: 1992, genre: "Platformer", image: sonic2.src },
  { id: "kirbys-dream-land-gb", name: "Kirby's Dream Land", platform: "Game Boy", console: "Nintendo Game Boy", publisher: "Nintendo", releaseYear: 1992, genre: "Platformer", image: kirbysDreamLand.src },
  { id: "star-fox-snes", name: "Star Fox", platform: "SNES", console: "Nintendo SNES", publisher: "Nintendo", releaseYear: 1993, genre: "Shooter", image: starFox.src },
];

export function game(id: string): Game {
  const found = GAMES.find((entry) => entry.id === id);
  if (!found) throw new Error(`Unknown game: ${id}`);
  return found;
}

// A store listing starts from the shared game facts and adds its own fields on top.
// Each store binds its own item type once, so its listings are checked against that type.
export function listingFor<T extends Game>() {
  return (fields: Omit<T, Exclude<keyof Game, "id">>) => ({ ...game(fields.id), ...fields }) as T;
}
