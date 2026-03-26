import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ChapterBrowserPage from './pages/ChapterBrowserPage';
import ChapterDetailPage from './pages/ChapterDetailPage';
import MyBooksPage from './pages/MyBooksPage';
import BookEditorPage from './pages/BookEditorPage';
import BuildStatusPage from './pages/BuildStatusPage';
import LibraryPage from './pages/LibraryPage';
import AboutPage from './pages/AboutPage';

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

      {/* Protected routes */}
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

      {/* Public: About */}
      <Route
        path="/about"
        element={
          <Layout>
            <AboutPage />
          </Layout>
        }
      />

      {/* Default: browse chapters */}
      <Route path="/" element={<Navigate to="/chapters" replace />} />
    </Routes>
  );
}
