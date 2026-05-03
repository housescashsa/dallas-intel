import React, { useState, useEffect } from "react";
import {
  Database, Flame, Lightbulb, Home, RefreshCw, Search, Download, Filter, X
} from "lucide-react";

const API_BASE = "http://localhost:8000";

function downloadCSV(filename, rows) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map(r => headers.map(h => {
      const v = r[h] == null ? "" : String(r[h]);
      return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }).join(","))
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

const fmtMoney = (n) => n ? "$" + Math.round(n).toLocaleString() : "—";

export default function App() {
  const [stats, setStats] = useState(null);
  const [leads, setLeads] = useState([]);
  const [leadTypes, setLeadTypes] = useState([]);
  const [cities, setCities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [scoreMin, setScoreMin] = useState(50);
  const [search, setSearch] = useState("");
  const [leadType, setLeadType] = useState("");
  const [city, setCity] = useState("");
  const [yearsMin, setYearsMin] = useState("");
  const [filedFrom, setFiledFrom] = useState("");
  const [filedTo, setFiledTo] = useState("");
  const [limit, setLimit] = useState(500);

  async function fetchAll() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ score_min: scoreMin, limit });
      if (search) params.set("search", search);
      if (leadType) params.set("lead_type", leadType);
      if (city) params.set("city", city);
      if (yearsMin) params.set("years_delinquent_min", yearsMin);
      if (filedFrom) params.set("filed_from", filedFrom);
      if (filedTo) params.set("filed_to", filedTo);

      const [s, l, t, c] = await Promise.all([
        fetch(API_BASE + "/api/stats").then(r => r.json()),
        fetch(API_BASE + "/api/leads?" + params).then(r => r.json()),
        fetch(API_BASE + "/api/lead-types").then(r => r.json()),
        fetch(API_BASE + "/api/cities").then(r => r.json()),
      ]);
      setStats(s);
      setLeads(l.leads);
      setLeadTypes(t.types);
      setCities(c.cities);
    } catch (e) {
      setError(e.message + " — make sure uvicorn is running on port 8000");
    }
    setLoading(false);
  }

  useEffect(() => { fetchAll(); }, [scoreMin, leadType, city, yearsMin, filedFrom, filedTo, limit]);
  useEffect(() => {
    const id = setInterval(fetchAll, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const clearFilters = () => {
    setSearch(""); setLeadType(""); setCity(""); setYearsMin("");
    setFiledFrom(""); setFiledTo(""); setScoreMin(50); setLimit(500);
  };

  const exportSkipTrace = () => {
    const rows = leads.map(l => ({
      first_name: "", last_name: "", full_name: l.owner_name,
      property_address: l.property_address, property_city: l.city,
      property_state: "TX", property_zip: l.zip,
      mailing_address: l.mailing_address, apn: l.dcad_account,
      lead_score: l.score, lead_type: l.lead_type,
      years_delinquent: l.years_delinquent, amount_owed: l.amount,
      market_value: l.market_value,
    }));
    const today = new Date().toISOString().slice(0,10);
    downloadCSV("dallas-skiptrace-" + today + ".csv", rows);
  };

  const exportGHL = () => {
    const rows = leads.map(l => ({
      "Contact Name": l.owner_name, "First Name": "", "Last Name": "",
      Email: "", Phone: "",
      "Address 1": l.property_address, City: l.city, State: "TX",
      "Postal Code": l.zip,
      Source: "Dallas Property Intel",
      Tags: "DallasIntel|" + l.lead_type + "|Score-" + l.score + (l.flags ? "|" + l.flags.join("|") : ""),
      "Mailing Address": l.mailing_address,
      "Lead Score": l.score, "Lead Type": l.lead_type,
      "DCAD Account": l.dcad_account, "Years Delinquent": l.years_delinquent,
      "Amount Owed": l.amount, "Market Value": l.market_value,
    }));
    const today = new Date().toISOString().slice(0,10);
    downloadCSV("dallas-ghl-" + today + ".csv", rows);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <header className="bg-white rounded-xl shadow p-6 mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-gray-900">DALLAS PROPERTY INTEL</h1>
          <p className="text-base text-gray-600">Live data from your local database — auto-refreshes every 5 min</p>
        </div>
        <button onClick={fetchAll} disabled={loading}
          className="flex items-center gap-2 px-5 py-3 bg-blue-600 text-white text-base font-bold rounded-lg hover:bg-blue-700 disabled:opacity-50">
          <RefreshCw size={18} className={loading ? "animate-spin" : ""}/>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </header>

      {error && (
        <div className="bg-red-100 border-2 border-red-400 text-red-800 p-4 rounded-lg mb-6 text-base">
          {error}
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          <Stat icon={<Database/>} label="TOTAL LEADS" value={stats.total ? stats.total.toLocaleString() : "0"} color="text-blue-600"/>
          <Stat icon={<Flame/>} label="HOT (≥70)" value={stats.hot ? stats.hot.toLocaleString() : "0"} color="text-red-600"/>
          <Stat icon={<Lightbulb/>} label="WARM (50-69)" value={stats.warm ? stats.warm.toLocaleString() : "0"} color="text-amber-600"/>
          <Stat icon={<Home/>} label="ACTIVE (30-49)" value={stats.active ? stats.active.toLocaleString() : "0"} color="text-emerald-600"/>
          <Stat icon={<RefreshCw/>} label="LAST UPDATED" value={stats.last_updated ? new Date(stats.last_updated).toLocaleString() : "never"} color="text-purple-600" small/>
        </div>
      )}

      {/* FILTER PANEL */}
      <div className="bg-white rounded-xl shadow p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter size={18} className="text-gray-500"/>
          <h3 className="font-bold text-gray-700 uppercase text-sm tracking-wide">Filters</h3>
          <button onClick={clearFilters} className="ml-auto text-sm text-blue-600 hover:underline flex items-center gap-1">
            <X size={14}/> Clear all
          </button>
        </div>

        <div className="grid grid-cols-4 gap-3 mb-3">
          <FilterField label="Search owner / address">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16}/>
              <input type="text" value={search} onChange={e=>setSearch(e.target.value)}
                onKeyDown={e=>e.key==="Enter"&&fetchAll()}
                placeholder="press Enter"
                className="w-full pl-9 pr-3 py-2.5 text-base border-2 border-gray-200 rounded-lg"/>
            </div>
          </FilterField>

          <FilterField label="Score tier">
            <select value={scoreMin} onChange={e=>setScoreMin(Number(e.target.value))}
              className="w-full px-3 py-2.5 text-base border-2 border-gray-200 rounded-lg bg-white">
              <option value={70}>Hot (70+)</option>
              <option value={50}>Warm+ (50+)</option>
              <option value={30}>Active+ (30+)</option>
              <option value={0}>Everything</option>
            </select>
          </FilterField>

          <FilterField label="Lead type">
            <select value={leadType} onChange={e=>setLeadType(e.target.value)}
              className="w-full px-3 py-2.5 text-base border-2 border-gray-200 rounded-lg bg-white">
              <option value="">All types</option>
              {leadTypes.map(t => <option key={t.lead_type} value={t.lead_type}>{t.lead_type} ({t.n.toLocaleString()})</option>)}
            </select>
          </FilterField>

          <FilterField label="Years delinquent (min)">
            <select value={yearsMin} onChange={e=>setYearsMin(e.target.value)}
              className="w-full px-3 py-2.5 text-base border-2 border-gray-200 rounded-lg bg-white">
              <option value="">Any</option>
              <option value="1">1+ years</option>
              <option value="2">2+ years</option>
              <option value="3">3+ years</option>
              <option value="5">5+ years</option>
              <option value="10">10+ years</option>
            </select>
          </FilterField>
        </div>

        <div className="grid grid-cols-4 gap-3">
          <FilterField label="City">
            <select value={city} onChange={e=>setCity(e.target.value)}
              className="w-full px-3 py-2.5 text-base border-2 border-gray-200 rounded-lg bg-white">
              <option value="">All cities</option>
              {cities.map(c => <option key={c.city} value={c.city}>{c.city} ({c.n.toLocaleString()})</option>)}
            </select>
          </FilterField>

          <FilterField label="Filed from (foreclosures/probates)">
            <input type="date" value={filedFrom} onChange={e=>setFiledFrom(e.target.value)}
              className="w-full px-3 py-2.5 text-base border-2 border-gray-200 rounded-lg"/>
          </FilterField>

          <FilterField label="Filed to">
            <input type="date" value={filedTo} onChange={e=>setFiledTo(e.target.value)}
              className="w-full px-3 py-2.5 text-base border-2 border-gray-200 rounded-lg"/>
          </FilterField>

          <FilterField label="Result limit">
            <select value={limit} onChange={e=>setLimit(Number(e.target.value))}
              className="w-full px-3 py-2.5 text-base border-2 border-gray-200 rounded-lg bg-white">
              <option value={100}>100</option>
              <option value={500}>500</option>
              <option value={1000}>1,000</option>
              <option value={5000}>5,000</option>
              <option value={10000}>10,000 (max)</option>
            </select>
          </FilterField>
        </div>

        <div className="flex gap-3 mt-4 pt-4 border-t border-gray-200">
          <button onClick={exportSkipTrace}
            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-base font-bold rounded-lg hover:bg-emerald-700">
            <Download size={18}/> Export Skip Trace CSV ({leads.length})
          </button>
          <button onClick={exportGHL}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white text-base font-bold rounded-lg hover:bg-blue-700">
            <Download size={18}/> Export GHL CSV ({leads.length})
          </button>
          <div className="ml-auto text-base text-gray-600 self-center">
            Showing <span className="font-bold">{leads.length}</span> of {stats?.total?.toLocaleString() || "—"}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-base">
            <thead className="bg-gray-50">
              <tr className="text-left">
                <th className="px-3 py-3 font-bold uppercase text-sm">Score</th>
                <th className="px-3 py-3 font-bold uppercase text-sm">Type</th>
                <th className="px-3 py-3 font-bold uppercase text-sm">Yrs</th>
                <th className="px-3 py-3 font-bold uppercase text-sm">Owner</th>
                <th className="px-3 py-3 font-bold uppercase text-sm">Property</th>
                <th className="px-3 py-3 font-bold uppercase text-sm">Mailing</th>
                <th className="px-3 py-3 font-bold uppercase text-sm text-right">Owed</th>
                <th className="px-3 py-3 font-bold uppercase text-sm text-right">Value</th>
                <th className="px-3 py-3 font-bold uppercase text-sm">Flags</th>
              </tr>
            </thead>
            <tbody>
              {leads.map(l => {
                const scoreCls = l.score >= 70 ? "bg-red-500 text-white" :
                                 l.score >= 50 ? "bg-amber-500 text-white" :
                                 l.score >= 30 ? "bg-blue-500 text-white" : "bg-gray-400 text-white";
                return (
                  <tr key={l.id} className="border-t hover:bg-blue-50/40">
                    <td className="px-3 py-3">
                      <span className={"inline-flex w-12 h-9 items-center justify-center rounded font-black " + scoreCls}>{l.score}</span>
                    </td>
                    <td className="px-3 py-3 font-bold text-gray-700">{l.lead_type}</td>
                    <td className="px-3 py-3 text-center font-semibold text-gray-700">{l.years_delinquent || "—"}</td>
                    <td className="px-3 py-3 font-bold">{l.owner_name}</td>
                    <td className="px-3 py-3">
                      <div>{l.property_address}</div>
                      <div className="text-sm text-gray-500">{l.city} {l.zip}</div>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-700 max-w-[180px]">{l.mailing_address}</td>
                    <td className="px-3 py-3 text-right font-semibold">{fmtMoney(l.amount)}</td>
                    <td className="px-3 py-3 text-right">{fmtMoney(l.market_value)}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(l.flags || []).slice(0,3).map((f,i)=>(
                          <span key={i} className="text-xs px-2 py-0.5 rounded bg-gray-100 border">{f}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {leads.length === 0 && !loading && (
          <div className="px-5 py-16 text-center text-gray-500 text-base">
            No leads match your filters. Try lowering the score tier or clearing filters.
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ icon, label, value, color, small }) {
  return (
    <div className="bg-white rounded-xl shadow p-5 flex items-center gap-4">
      <div className={color + " opacity-80"}>{React.cloneElement(icon, { size: 30 })}</div>
      <div className="flex-1 min-w-0">
        <div className={(small ? "text-base" : "text-3xl") + " font-black " + color + " truncate"}>{value || "—"}</div>
        <div className="text-sm font-bold text-gray-500 uppercase mt-0.5">{label}</div>
      </div>
    </div>
  );
}

function FilterField({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wide mb-1">{label}</label>
      {children}
    </div>
  );
}
