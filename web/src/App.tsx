import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import ChatPage from "./pages/ChatPage";
import KnowledgePage from "./pages/KnowledgePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<ChatPage />} />
        <Route path="c/:sessionId" element={<ChatPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
