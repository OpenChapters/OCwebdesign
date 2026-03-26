import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Navbar() {
  const { isAuthenticated, isStaff, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
      <Link to="/" className="font-bold text-blue-700 text-lg tracking-tight">
        OpenChapters
      </Link>

      <div className="flex items-center gap-4 flex-1">
        <NavLink
          to="/chapters"
          className={({ isActive }) =>
            `text-sm font-medium ${isActive ? 'text-blue-700' : 'text-gray-600 hover:text-gray-900'}`
          }
        >
          Browse
        </NavLink>
        {isAuthenticated && (
          <>
            <NavLink
              to="/books"
              className={({ isActive }) =>
                `text-sm font-medium ${isActive ? 'text-blue-700' : 'text-gray-600 hover:text-gray-900'}`
              }
            >
              My Books
            </NavLink>
            <NavLink
              to="/library"
              className={({ isActive }) =>
                `text-sm font-medium ${isActive ? 'text-blue-700' : 'text-gray-600 hover:text-gray-900'}`
              }
            >
              Library
            </NavLink>
          </>
        )}
        <NavLink
          to="/about"
          className={({ isActive }) =>
            `text-sm font-medium ${isActive ? 'text-blue-700' : 'text-gray-600 hover:text-gray-900'}`
          }
        >
          About
        </NavLink>
      </div>

      <div className="flex items-center gap-3">
        {isStaff && (
          <Link
            to="/admin-panel"
            className="text-xs bg-gray-800 text-white px-2.5 py-1 rounded hover:bg-gray-900"
          >
            Admin
          </Link>
        )}
        {isAuthenticated ? (
          <>
            <Link to="/profile" className="text-sm text-gray-600 hover:text-gray-900">
              Profile
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Sign out
            </button>
          </>
        ) : (
          <>
            <Link to="/login" className="text-sm text-gray-600 hover:text-gray-900">
              Sign in
            </Link>
            <Link
              to="/register"
              className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
            >
              Register
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
