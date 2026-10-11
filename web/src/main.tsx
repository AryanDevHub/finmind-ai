import "@fontsource-variable/plus-jakarta-sans";
import "@fontsource-variable/jetbrains-mono";
import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ApiError } from "./lib/api";
import { AuthProvider } from "./lib/auth";
import { ToastProvider } from "./components/ui/Toast";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      // Never retry auth/validation failures; retry transient ones once.
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
