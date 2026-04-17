import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import ProfilePage from './pages/ProfilePage';
import ChapterBrowserPage from './pages/ChapterBrowserPage';
import ChapterDetailPage from './pages/ChapterDetailPage';
import ChapterReadPage from './pages/ChapterReadPage';
import MyBooksPage from './pages/MyBooksPage';
import BookEditorPage from './pages/BookEditorPage';
import BuildStatusPage from './pages/BuildStatusPage';
import LibraryPage from './pages/LibraryPage';
import AboutPage from './pages/AboutPage';
import UserGuidePage from './pages/UserGuidePage';

// Admin
import AdminRoute from './admin/AdminRoute';
import AdminLayout from './admin/AdminLayout';
import DashboardPage from './admin/pages/DashboardPage';
import UsersPage from './admin/pages/UsersPage';
import UserDetailPage from './admin/pages/UserDetailPage';
import ChaptersAdminPage from './admin/pages/ChaptersPage';
import ChapterAdminDetailPage from './admin/pages/ChapterDetailPage';
import DisciplinesAdminPage from './admin/pages/DisciplinesPage';
import BuildsAdminPage from './admin/pages/BuildsPage';
import BuildAdminDetailPage from './admin/pages/BuildDetailPage';
import SystemPage from './admin/pages/SystemPage';
import SettingsPage from './admin/pages/SettingsPage';
import AuditLogPage from './admin/pages/AuditLogPage';
import AnalyticsPage from './admin/pages/AnalyticsPage';
import PlaceholderPage from './admin/pages/PlaceholderPage';

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      <main className="flex-1">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />

      {/* Public routes with navbar */}
      <Route
        path="/chapters"
        element={
          <Layout>
            <ChapterBrowserPage />
          </Layout>
        }
      />
      <Route
        path="/chapters/:id"
        element={
          <Layout>
            <ChapterDetailPage />
          </Layout>
        }
      />
      <Route
        path="/chapters/:id/read"
        element={<ChapterReadPage />}
      />

      {/* Protected routes */}
      <Route element={<ProtectedRoute />}>
        <Route
          path="/profile"
          element={
            <Layout>
              <ProfilePage />
            </Layout>
          }
        />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route
          path="/books"
          element={
            <Layout>
              <MyBooksPage />
            </Layout>
          }
        />
        <Route path="/books/:id" element={<BookEditorPage />} />
        <Route
          path="/books/:id/status"
          element={
            <Layout>
              <BuildStatusPage />
            </Layout>
          }
        />
        <Route
          path="/library"
          element={
            <Layout>
              <LibraryPage />
            </Layout>
          }
        />
      </Route>

      {/* Admin panel (staff only) */}
      <Route element={<AdminRoute />}>
        <Route path="/admin-panel" element={<AdminLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="users/:id" element={<UserDetailPage />} />
          <Route path="disciplines" element={<DisciplinesAdminPage />} />
          <Route path="chapters" element={<ChaptersAdminPage />} />
          <Route path="chapters/:id" element={<ChapterAdminDetailPage />} />
          <Route path="builds" element={<BuildsAdminPage />} />
          <Route path="builds/:id" element={<BuildAdminDetailPage />} />
          <Route path="system" element={<SystemPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="audit" element={<AuditLogPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
        </Route>
      </Route>

      {/* Public: About and User Guide */}
      <Route
        path="/about"
        element={
          <Layout>
            <AboutPage />
          </Layout>
        }
      />
      <Route
        path="/guide"
        element={
          <Layout>
            <UserGuidePage />
          </Layout>
        }
      />

      {/* Default: browse chapters */}
      <Route path="/" element={<Navigate to="/chapters" replace />} />
    </Routes>
  );
}
