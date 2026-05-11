import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ThemeToggle from './ThemeToggle';

export default function Navbar() {
  const { isAuthenticated, isStaff, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Close the mobile menu whenever the route changes.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  // Close on Escape and on click outside the menu.
  useEffect(() => {
    if (!menuOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false);
    }
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [menuOpen]);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-medium ${isActive ? 'text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-50'}`;

  return (
    <nav
      aria-label="Main navigation"
      className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 sm:px-6 py-3"
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Link
          to="/"
          className="flex items-center gap-2 font-bold text-blue-700 dark:text-blue-400 text-lg tracking-tight"
        >
          <img src="/favicon.png" alt="" className="w-6 h-6" />
          OpenChapters
        </Link>

        {/* Desktop / tablet inline nav */}
        <div className="hidden md:flex items-center gap-4 flex-1">
          <NavLink to="/chapters" className={navItemClass}>Browse</NavLink>
          {isAuthenticated && (
            <NavLink to="/books" className={navItemClass}>My Books</NavLink>
          )}
          {isAuthenticated && (
            <NavLink to="/examples" className={navItemClass}>Examples</NavLink>
          )}
          <NavLink to="/community" className={navItemClass}>Community</NavLink>
          <NavLink to="/catalog" className={navItemClass}>Catalog</NavLink>
          <NavLink to="/guide" className={navItemClass}>User Guide</NavLink>
          <NavLink to="/about" className={navItemClass}>About</NavLink>
        </div>

        <div className="hidden md:flex items-center gap-3 ml-auto">
          {isStaff && (
            <Link
              to="/admin-panel"
              className="text-xs bg-gray-800 dark:bg-gray-700 text-white px-2.5 py-1 rounded hover:bg-gray-900 dark:hover:bg-gray-600"
            >
              Admin
            </Link>
          )}
          <NavLink to="/search" className={navItemClass}>Search</NavLink>
          {isAuthenticated ? (
            <>
              <Link to="/profile" className="text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-50">Profile</Link>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-50"
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-50">Sign in</Link>
              <Link
                to="/register"
                className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
              >
                Register
              </Link>
            </>
          )}
          <ThemeToggle />
        </div>

        {/* Mobile menu trigger */}
        <button
          type="button"
          className="md:hidden ml-auto inline-flex items-center justify-center w-10 h-10 rounded-md text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          aria-controls="mobile-nav"
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((v) => !v);
          }}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-6 h-6"
            aria-hidden="true"
          >
            {menuOpen ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Mobile dropdown panel */}
      {menuOpen && (
        <div
          ref={menuRef}
          id="mobile-nav"
          className="md:hidden mt-3 border-t border-gray-200 dark:border-gray-700 pt-3 flex flex-col gap-1"
        >
          <NavLink to="/chapters" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>Browse</NavLink>
          {isAuthenticated && (
            <NavLink to="/books" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>My Books</NavLink>
          )}
          {isAuthenticated && (
            <NavLink to="/examples" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>Examples</NavLink>
          )}
          <NavLink to="/community" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>Community</NavLink>
          <NavLink to="/catalog" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>Catalog</NavLink>
          <NavLink to="/guide" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>User Guide</NavLink>
          <NavLink to="/about" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>About</NavLink>
          <NavLink to="/search" className={({ isActive }) => `block px-2 py-2 rounded ${isActive ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>Search</NavLink>
          <div className="border-t border-gray-200 dark:border-gray-700 mt-2 pt-2 flex flex-col gap-1">
            {isStaff && (
              <Link to="/admin-panel" className="block px-2 py-2 rounded text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">Admin</Link>
            )}
            {isAuthenticated ? (
              <>
                <Link to="/profile" className="block px-2 py-2 rounded text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">Profile</Link>
                <button
                  onClick={handleLogout}
                  className="text-left block px-2 py-2 rounded text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="block px-2 py-2 rounded text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">Sign in</Link>
                <Link to="/register" className="block px-2 py-2 rounded text-white bg-blue-600 hover:bg-blue-700">Register</Link>
              </>
            )}
            <div className="px-2 pt-2">
              <ThemeToggle />
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
