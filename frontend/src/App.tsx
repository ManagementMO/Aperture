import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Demo from "./pages/Demo";
import Overview from "./pages/Overview";
import TokenWaterfall from "./pages/TokenWaterfall";
import SchemaCompaction from "./pages/SchemaCompaction";
import Benchmarks from "./pages/Benchmarks";
import VsRtk from "./pages/VsRtk";
import SpendStudio from "./pages/SpendStudio";

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Demo />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/spend" element={<SpendStudio />} />
          <Route path="/waterfall" element={<TokenWaterfall />} />
          <Route path="/schema" element={<SchemaCompaction />} />
          <Route path="/benchmarks" element={<Benchmarks />} />
          <Route path="/vs-rtk" element={<VsRtk />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
