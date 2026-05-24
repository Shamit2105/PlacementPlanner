import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Building2, 
  BookOpen, 
  Target, 
  TrendingUp,
  Star,
  Calendar
} from 'lucide-react';

const Sidebar: React.FC = () => {
  const location = useLocation();

  const sidebarItems = [
    { path: '/', icon: <LayoutDashboard size={20} />, label: 'Dashboard' },
    { path: '/companies', icon: <Building2 size={20} />, label: 'Companies' },
    { path: '/experiences', icon: <BookOpen size={20} />, label: 'Experiences' },
    { path: '/trending', icon: <TrendingUp size={20} />, label: 'Trending' },
    { path: '/bookmarks', icon: <Star size={20} />, label: 'Bookmarks' },
    { path: '/schedule', icon: <Calendar size={20} />, label: 'Schedule' },
  ];

  return (
    <aside className="hidden lg:flex lg:flex-col w-64 bg-white border-r border-ocean-100 min-h-screen">
      <div className="flex-1 flex flex-col pt-5 pb-4 overflow-y-auto">
        <div className="px-4 mb-6">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Main Menu
          </h2>
        </div>
        <nav className="flex-1 px-2 space-y-1">
          {sidebarItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
                location.pathname === item.path
                  ? 'bg-gradient-to-r from-primary-50 to-ocean-50 text-primary-700 border border-primary-200'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-ocean-700'
              }`}
            >
              <span className={`mr-3 ${
                location.pathname === item.path ? 'text-primary-600' : 'text-gray-400 group-hover:text-ocean-500'
              }`}>
                {item.icon}
              </span>
              {item.label}
              {location.pathname === item.path && (
                <span className="ml-auto w-1.5 h-1.5 bg-primary-500 rounded-full"></span>
              )}
            </Link>
          ))}
        </nav>
      </div>
      
      <div className="p-4 border-t border-ocean-100">
        <div className="bg-gradient-to-br from-primary-50 to-ocean-50 rounded-lg p-4 border border-primary-200">
          <h3 className="text-sm font-semibold text-primary-800 mb-1">Pro Tip</h3>
          <p className="text-xs text-gray-600">
            Practice with company-specific questions to increase your chances!
          </p>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;