import { NavLink, Outlet, Link } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/admin-panel', label: 'Dashboard', end: true },
  { to: '/admin-panel/users', label: 'Users' },
  { to: '/admin-panel/disciplines', label: 'Disciplines' },
  { to: '/admin-panel/chapters', label: 'Chapters' },
  { to: '/admin-panel/examples', label: 'Examples' },
  { to: '/admin-panel/builds', label: 'Builds' },
  { to: '/admin-panel/system', label: 'System' },
  { to: '/admin-panel/settings', label: 'Settings' },
  { to: '/admin-panel/audit', label: 'Audit Log' },
  { to: '/admin-panel/analytics', label: 'Analytics' },
];

function SidebarLink({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `block px-4 py-2 text-sm rounded-lg transition-colors ${
          isActive
            ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 font-medium'
            : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-50'
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function AdminLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <aside className="w-56 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col shrink-0">
        <div className="px-4 py-4 border-b border-gray-200 dark:border-gray-700">
          <Link to="/" className="text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">
            ← Back to site
          </Link>
          <h2 className="text-lg font-bold text-gray-900 dark:text-gray-50 mt-1">Admin Panel</h2>
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <SidebarLink key={item.to} {...item} />
          ))}
        </nav>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
