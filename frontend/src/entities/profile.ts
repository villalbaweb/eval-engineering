import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/api";
import type { Capability, Catalog, ProfileView, VariantView } from "@/shared/types";

/** The active agent profile, from the catalog (which follows the X-Eval-Profile header). */
export function useActiveProfile(): { profile?: ProfileView; catalog?: Catalog } {
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  return { profile: catalog.data?.profile, catalog: catalog.data };
}

/** A variant by name or alias; default: the profile's default variant. */
export function findVariant(p: ProfileView | undefined, ref?: string | null): VariantView | undefined {
  if (!p) return undefined;
  const want = ref || p.default_variant || p.variants[0]?.name;
  return p.variants.find((v) => v.name === want) ?? p.variants.find((v) => v.aliases.includes(want ?? ""));
}

/** Can this variant do X? Servers without profiles (no profile info) support everything, as before. */
export function can(p: ProfileView | undefined, ref: string | null | undefined, cap: Capability): boolean {
  if (!p) return true;
  const v = findVariant(p, ref);
  return v ? v.capabilities.includes(cap) : false;
}

export const CAPABILITY_HELP: Record<Capability, string> = {
  chat: "talk to it in the Playground / multi-turn runs",
  rerun: "send tasks to it (live experiments)",
  fault_injection: "inject tool failures",
  record_replay: "record / replay tool outputs",
  model_override: "swap its model per run",
  traffic_sim: "simulate user traffic against it",
};
