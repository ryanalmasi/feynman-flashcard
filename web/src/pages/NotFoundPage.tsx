import { Link } from "react-router";

export default function NotFoundPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-6">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/sets" className="text-primary underline">
        Go to your study sets
      </Link>
    </main>
  );
}
