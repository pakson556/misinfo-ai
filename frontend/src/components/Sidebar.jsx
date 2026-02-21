import React from "react";
import { Search, Activity, Shield, LayoutDashboard } from "lucide-react";

export default function Sidebar({ activeTab, setActiveTab }) {
  const menuItems = [
    { id: "analyze", icon: Search, label: "Detection Lab" },
    { id: "dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { id: "monitor", icon: Activity, label: "Global Monitor" },
  ];

  return (
    <div className="w-64 h-screen flex flex-col bg-white border-r border-gray-200 sticky top-0">
      {/* Logo */}
      <div className="p-6 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <Shield className="w-6 h-6 text-blue-600" />
          <span className="font-bold text-xl text-gray-900">MisInfo AI</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
              activeTab === item.id
                ? "bg-blue-50 text-blue-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            }`}
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </button>
        ))}
      </nav>

      {/* Status */}
      <div className="p-4 border-t border-gray-100">
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Active Engine</p>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            <span className="text-sm text-gray-700">twitter15/16 multimodal</span>
          </div>
        </div>
      </div>
    </div>
  );
}
