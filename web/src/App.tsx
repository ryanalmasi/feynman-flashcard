import { Route, Routes } from "react-router";
import NotFoundPage from "./pages/NotFoundPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<StatusPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
