import { useEffect } from "react";

export function useTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · Site Safety Intelligence` : "Site Safety Intelligence";
  }, [title]);
}
