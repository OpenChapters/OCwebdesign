import { useState, useEffect, useRef, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

// Load the Turnstile script once
let turnstileLoaded = false;
function loadTurnstileScript(): Promise<void> {
  if (turnstileLoaded) return Promise.resolve();
  return new Promise((resolve) => {
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.onload = () => { turnstileLoaded = true; resolve(); };
    document.head.appendChild(script);
  });
}

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState('');
  const [siteKey, setSiteKey] = useState('');
  const widgetRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  // Fetch site key and load Turnstile widget
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get('/api/auth/turnstile/');
        if (cancelled || !data.site_key) return;
        setSiteKey(data.site_key);
        await loadTurnstileScript();
        if (cancelled || !widgetRef.current) return;
        // Render the widget
        const w = window as any;
        if (w.turnstile && widgetRef.current) {
          widgetIdRef.current = w.turnstile.render(widgetRef.current, {
            sitekey: data.site_key,
            callback: (token: string) => setTurnstileToken(token),
            'expired-callback': () => setTurnstileToken(''),
          });
        }
      } catch {
        // Turnstile not available; registration will still work with test keys
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (!turnstileToken) {
      setError('Please complete the CAPTCHA verification.');
      return;
    }
    setLoading(true);
    try {
      await register(email, password, turnstileToken, fullName);
      navigate('/login');
    } catch (err: any) {
      const data = err?.response?.data;
      if (data?.email) setError(data.email.join(' '));
      else if (data?.password) setError(data.password.join(' '));
      else if (data?.turnstile_token) setError(data.turnstile_token.join(' '));
      else setError('Registration failed.');
      // Reset the widget so the user can try again
      const w = window as any;
      if (w.turnstile && widgetIdRef.current) {
        w.turnstile.reset(widgetIdRef.current);
        setTurnstileToken('');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Create account</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password <span className="text-gray-400 font-normal">(min. 8 characters)</span>
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          {/* Turnstile widget */}
          <div ref={widgetRef} className="flex justify-center" />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="text-sm text-gray-500 mt-4 text-center">
          Already have an account?{' '}
          <Link to="/login" className="text-blue-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
