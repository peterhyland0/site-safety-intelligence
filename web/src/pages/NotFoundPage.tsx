import { Link } from "react-router";
import { useTitle } from "../lib/useTitle";

export function NotFoundPage() {
  useTitle("Not found");
  return (
    <div className="py-16 text-center">
      <h1 className="text-xl font-semibold text-ink">Page not found</h1>
      <p className="mt-1 text-ink-2">That link doesn't match anything here.</p>
      <Link to="/" className="btn btn-primary mt-4">
        Go to projects
      </Link>
    </div>
  );
}
