import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Building2, Search } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { companiesApi } from '../services/api';
import { Company } from '../types';

const Companies: React.FC = () => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const response = await companiesApi.list({ page: 1 });
        setCompanies(response.results);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return companies;
    return companies.filter(
      (item) => item.name.toLowerCase().includes(normalized) || item.slug.toLowerCase().includes(normalized)
    );
  }, [companies, query]);

  if (loading) return <LoadingSpinner label="Loading companies" />;

  return (
    <div className="space-y-6">
      <header className="surface p-6 sm:p-8">
        <h1 className="text-3xl text-slate-900 sm:text-4xl">Company Directory</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Explore companies connected to your question bank. Open any profile to view all filtered interview questions by company slug.
        </p>
        <div className="mt-5 max-w-md">
          <label className="relative block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-xl border border-amber-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none ring-orange-200 focus:ring"
              placeholder="Search by company or slug"
            />
          </label>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((company, index) => (
          <Link
            to={`/companies/${company.id}`}
            key={company.id}
            className="surface stagger-enter p-5 hover:border-amber-300"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className="flex items-start justify-between">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 to-sky-500 text-white">
                <Building2 size={18} />
              </span>
              <span className="rounded-full bg-sky-100 px-2 py-1 text-[11px] font-semibold tracking-[0.12em] text-sky-800">
                {company.slug}
              </span>
            </div>
            <h2 className="mt-4 text-xl text-slate-900">{company.name}</h2>
            <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">Open company board</p>
          </Link>
        ))}
      </section>

      {filtered.length === 0 && (
        <div className="surface p-8 text-center text-slate-600">No companies match your current search.</div>
      )}
    </div>
  );
};

export default Companies;
