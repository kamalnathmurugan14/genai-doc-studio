import { NavLink, Route, Routes } from "react-router-dom";
import { useTheme } from "./hooks/useTheme";
import { HistoryPage } from "./pages/HistoryPage";
import { PromptsPage } from "./pages/PromptsPage";
import { StudioPage } from "./pages/StudioPage";

export default function App() {
  const [theme, toggle] = useTheme();
  return (
    <div className="layout">
      <nav className="sidebar" aria-label="Main">
        <h1>✨ GenAI Studio</h1>
        <NavLink to="/" end>
          Studio
        </NavLink>
        <NavLink to="/prompts">Prompts</NavLink>
        <NavLink to="/history">History</NavLink>
        <span className="spacer" />
        <button type="button" onClick={toggle} aria-label="Toggle theme">
          {theme === "dark" ? "☀ Light" : "🌙 Dark"}
        </button>
      </nav>
      <main className="main wide">
        <Routes>
          <Route path="/" element={<StudioPage />} />
          <Route path="/prompts" element={<PromptsPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>
    </div>
  );
}
