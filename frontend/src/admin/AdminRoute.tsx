import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function AdminRoute() {
  const { isAuthenticated, isStaff } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!isStaff) return <Navigate to="/" replace />;
  return <Outlet />;
}
