import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import TokenWaterfall from "./pages/TokenWaterfall";
import Compression from "./pages/Compression";
import SchemaCompaction from "./pages/SchemaCompaction";
import CacheStats from "./pages/CacheStats";
import Benchmarks from "./pages/Benchmarks";
import TaskAware from "./pages/TaskAware";
import Placeholder from "./pages/Placeholder";
import PromptCache from "./pages/PromptCache";
import FieldSelect from "./pages/FieldSelect";

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/waterfall" element={<TokenWaterfall />} />
          <Route path="/compression" element={<Compression />} />
          <Route path="/schema" element={<SchemaCompaction />} />
          <Route path="/cache" element={<CacheStats />} />
          <Route path="/benchmarks" element={<Benchmarks />} />
          <Route path="/task-aware" element={<TaskAware />} />
          <Route path="/placeholder" element={<Placeholder />} />
          <Route path="/prompt-cache" element={<PromptCache />} />
          <Route path="/field-select" element={<FieldSelect />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
