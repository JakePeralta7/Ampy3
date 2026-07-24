import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AppLayout } from "./components/Layout/AppLayout";
import { AuthProvider } from "./contexts/AuthContext";
import { ChatSessionProvider } from "./contexts/ChatSessionContext";
import "./globals.css";

const root = ReactDOM.createRoot(document.getElementById("root") as HTMLElement);
root.render(
  <BrowserRouter>
    <AuthProvider>
      <ChatSessionProvider>
        <AppLayout />
      </ChatSessionProvider>
    </AuthProvider>
  </BrowserRouter>,
);
