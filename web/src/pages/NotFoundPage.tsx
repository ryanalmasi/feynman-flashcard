import { Link } from "react-router";

export default function NotFoundPage() {
  return (
    <main>
      <h1>Page not found</h1>
      <Link to="/">Back to status</Link>
    </main>
  );
}
