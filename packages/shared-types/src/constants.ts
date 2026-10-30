import type { components } from "./api";

type Category = components["schemas"]["SpotSummary"]["category"];
type Tier = components["schemas"]["SpotSummary"]["display_tier"];

// Mirrors NIGERIAN_STATES in apps/api/app/schemas/spot.py. A test in apps/web fails if they differ.
export const NIGERIAN_STATES = [
  "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
  "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT", "Gombe", "Imo", "Jigawa",
  "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun",
  "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
] as const;

export const CATEGORIES = [
  "nature", "food", "historical", "hangout", "beach", "park", "other",
] as const satisfies readonly Category[];

export const TIERS = ["green", "yellow", "red", "unverified"] as const satisfies readonly Tier[];

// Compile-time exhaustiveness: if the API adds a category or tier, these stop compiling.
type MissingCategory = Exclude<Category, (typeof CATEGORIES)[number]>;
type MissingTier = Exclude<Tier, (typeof TIERS)[number]>;
export const exhaustive: [MissingCategory, MissingTier] extends [never, never] ? true : never = true;
