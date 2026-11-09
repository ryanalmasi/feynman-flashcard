import { Navigate, Route, Routes } from "react-router";
import RequireAuth from "./components/RequireAuth";
import AccountPage from "./pages/AccountPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import RegisterPage from "./pages/RegisterPage";
import ReviewPage from "./pages/ReviewPage";
import SetDetailPage from "./pages/SetDetailPage";
import SetsPage from "./pages/SetsPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/status" element={<StatusPage />} />
      <Route path="/" element={<Navigate to="/sets" replace />} />
      <Route element={<RequireAuth />}>
        <Route path="/sets" element={<SetsPage />} />
        <Route path="/sets/:setId" element={<SetDetailPage />} />
        <Route path="/sets/:setId/review" element={<ReviewPage />} />
        <Route path="/account" element={<AccountPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
