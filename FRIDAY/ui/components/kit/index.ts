/* ================================================================
   FRIDAY UI kit (TASK-WEB-008).

   Design-technique components for the FRIDAY site, extracted
   from the in-situ implementations (checkpoint 1 inventory) or
   built new from the board acceptance text:

   - ScrollPlaybook — the scroll motion layer (reveal, progress,
     parallax, reduced-motion hook), moved from stage/motion.tsx.
   - ShowcaseRows — Netflix-style billboard + browsable rows
     over caller-supplied data, generalised from ShowcaseSheet.
   - ScrollVideo — NEW scroll-driven video (scrub, no autoplay).
   - MapInterface — NEW OSIRIS-style map surface (Nominatim +
     OpenStreetMap embed, key-less).
   - GlassStartPage — the LumiList start-page pattern, already a
     component; re-exported here unchanged. It takes no props.

   CSS dependency: the kit uses the global classes in
   `app/globals.css` (`reveal`, `sheet-progress`, `parallax`,
   `showcase-*`, `pill` / `tone-*`, `sheet-note`). The kit adds
   no stylesheet of its own and no new dependency.

   Live surfaces are untouched: the stage keeps importing from
   `stage/motion.tsx` (now a re-export of ScrollPlaybook) and
   ShowcaseSheet keeps its own fleet wiring.
   ================================================================ */

export {
  Parallax,
  Reveal,
  ScrollProgress,
  usePrefersReducedMotion,
} from "./ScrollPlaybook";
export {
  ShowcaseRows,
  toneForStatus,
  useFeaturedPool,
  type ShowcaseItem,
  type ShowcaseRow,
  type ShowcaseRowsProps,
  type ShowcaseTone,
} from "./ShowcaseRows";
export { ScrollVideo, type ScrollVideoProps } from "./ScrollVideo";
export { MapInterface, type MapInterfaceProps, type MapPlace } from "./MapInterface";
export { GlassStartPage } from "@/components/GlassStartPage";
