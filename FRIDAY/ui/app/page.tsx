import { Stage } from "@/components/stage/Stage";

/* TASK-WEB-002 — the entire app is one stage. There is no router
   of screens and no shell of views: the room renders, and every
   other surface is a layer summoned over it. */
export default function Home() {
  return <Stage />;
}
