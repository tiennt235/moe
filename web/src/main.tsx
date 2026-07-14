import React from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import Activity from "./pages/Activity";
import ExpertDetail from "./pages/ExpertDetail";
import Playground from "./pages/Playground";
import Settings from "./pages/Settings";
import Team from "./pages/Team";
import "./styles.css";

// Hash routing so the SPA works when served as static files from any base path.
const router = createHashRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Team /> },
      { path: "experts/:name", element: <ExpertDetail /> },
      { path: "activity", element: <Activity /> },
      { path: "playground", element: <Playground /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
