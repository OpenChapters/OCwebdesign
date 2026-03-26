import { useEffect, useState } from 'react';
import Markdown from 'react-markdown';

export default function AboutPage() {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/about/')
      .then((r) => r.text())
      .then((text) => { setContent(text); setLoading(false); })
      .catch(() => { setContent('# About\n\nFailed to load content.'); setLoading(false); });
  }, []);

  if (loading) return <div className="text-center text-gray-500 py-16">Loading…</div>;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="prose prose-gray max-w-none">
        <Markdown>{content}</Markdown>
      </div>
    </div>
  );
}
