import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import Today from "@/pages/Today";
import Stores from "@/pages/Stores";
import Findings from "@/pages/Findings";
import Runs from "@/pages/Runs";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Today />} />
            <Route path="stores" element={<Stores />} />
            <Route path="findings" element={<Findings />} />
            <Route path="runs" element={<Runs />} />
            <Route path="*" element={<Today />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
