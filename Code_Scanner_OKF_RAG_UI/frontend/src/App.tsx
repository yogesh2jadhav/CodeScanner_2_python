import { Navigate, Route, Routes } from "react-router-dom";
import { EntityPanelProvider } from "./components/EntityPanelContext";
import { Layout } from "./components/Layout";
import { AskPage } from "./pages/AskPage";
import { ExplorerPage } from "./pages/ExplorerPage";
import { FlowPage } from "./pages/FlowPage";
import { GraphPage } from "./pages/GraphPage";
import { SearchPage } from "./pages/SearchPage";

export default function App() {
  return (
    <EntityPanelProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/ask" replace />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/explorer" element={<ExplorerPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/flow" element={<FlowPage />} />
          <Route path="*" element={<Navigate to="/ask" replace />} />
        </Routes>
      </Layout>
    </EntityPanelProvider>
  );
}
