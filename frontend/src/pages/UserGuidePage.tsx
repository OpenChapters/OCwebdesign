import { useEffect, useState } from 'react';
import Markdown from 'react-markdown';
import rehypeSlug from 'rehype-slug';

export default function UserGuidePage() {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/user-guide/')
      .then((r) => r.text())
      .then((text) => { setContent(text); setLoading(false); })
      .catch(() => { setContent('# User Guide\n\nFailed to load content.'); setLoading(false); });
  }, []);

  if (loading) return <div className="text-center text-gray-500 py-16">Loading…</div>;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="prose prose-gray max-w-none">
        <Markdown rehypePlugins={[rehypeSlug]}>{content}</Markdown>
      </div>
    </div>
  );
}
