import React, { useState } from "react";
import Sidebar from "./components/Sidebar.jsx";

import DetectionLab from "./pages/DetectionLab.jsx";
import GlobalMonitor from "./pages/GlobalMonitor.jsx";
import Dashboard from "./pages/Dashboard/Dashboard.jsx"; 

export default function App() {
  const [activeTab, setActiveTab] = useState("analyze");

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1">
        {activeTab === "dashboard" && <Dashboard />}   
        {activeTab === "analyze" && <DetectionLab />}
        {activeTab === "monitor" && <GlobalMonitor />}
      </main>
    </div>
  );
}
