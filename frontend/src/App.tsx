import { Navigate, Route, Routes } from "react-router-dom";
import { CandidateProvider } from "./state/CandidateContext";
import { BrowsePage } from "./pages/BrowsePage";
import { MyActivityPage } from "./pages/MyActivityPage";

export default function App() {
  return (
    <CandidateProvider>
      <Routes>
        <Route path="/" element={<BrowsePage />} />
        <Route path="/activity" element={<MyActivityPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </CandidateProvider>
  );
}
