import React, { useState, useEffect } from "react";
import {
  Database, Flame, Lightbulb, Home, RefreshCw, Search, Download
} from "lucide-react";

const API_BASE = "http://localhost:8000";

function downloadCSV(filename, rows) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map(r => headers.map(h => {
      const v = r[h] == null ? "" : String(r[h]);
      return /[",\n]/.test(v) ? `"` + v.replace(/"/g, '""') + `"` : v;
    }).join(","))
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [stats, setStats] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scoreMin, setScoreMin] = useState(50);
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);

  async function fetchAll() {
    setLoading(true);
    setError(null);
    try {
      const statsRes = await fetch(API_BASE + "/api/stats");
      const s = await statsRes.json();
      const url = API_BASE + "/api/leads?score_min=" + scoreMin + "&limit=500" + (search ? "&search=" + encodeURIComponent(search) : "");
      const leadsRes = await fetch(url);
      const l = await leadsRes.json();
      setStats(s);
      setLeads(l.leads);
    } catch (e) {
      setError(e.message + " — make sure uvicorn is running on port 8000");
    }
    setLoading(false);
  }

  useEffect(() => { fetchAll(); }, [scoreMin]);
  useEffect(() => {
    const id = setInterval(fetchAll, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [scoreMin, search]);

  const exportSkipTrace = () => {
    const rows = leads.map(l => ({
      first_name: "", last_name: "", full_name: l.owner_name,
      property_address: l.property_address, property_city: l.city,
      property_state: "TX", property_zip: l.zip,
      mailing_address: l.mailing_address, apn: l.dcad_account,
      lead_score: l.score, lead_type: l.lead_type,
    }));
    const today = new Date().toISOString().slice(0,10);
    downloadCSV("dallas-skiptrace-" + today + ".csv", rows);
  };

  const fmtMoney = (n) => n ? "$" + Math.round(n).toLocaleString() : "—";

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <header className="bg-white rounded-xl shadow p-6 mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-gray-900">DALLAS PROPERTY INTEL</h1>
          <p className="text-base text-gray-600">Live data from your local database</p>
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

      <div className="bg-white rounded-xl shadow p-5 mb-6 flex gap-3 flex-wrap items-center">
        <div className="relative flex-1 min-w-[280px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18}/>
          <input type="text" value={search} onChange={e=>setSearch(e.target.value)}
            onKeyDown={e=>e.key==="Enter"&&fetchAll()}
            placeholder="Search owner or address (press Enter)"
            className="w-full pl-10 pr-3 py-3 text-base border-2 border-gray-200 rounded-lg"/>
        </div>
        <select value={scoreMin} onChange={e=>setScoreMin(Number(e.target.value))}
          className="px-4 py-3 text-base border-2 border-gray-200 rounded-lg bg-white">
          <option value={70}>Hot only (70+)</option>
          <option value={50}>Warm+ (50+)</option>
          <option value={30}>Active+ (30+)</option>
          <option value={0}>Everything</option>
        </select>
        <button onClick={exportSkipTrace}
          className="flex items-center gap-2 px-5 py-3 bg-emerald-600 text-white text-base font-bold rounded-lg hover:bg-emerald-700">
          <Download size={18}/> Export Skip Trace CSV
        </button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="px-5 py-4 border-b text-base text-gray-700">
          Showing <span className="font-bold">{leads.length}</span> leads
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-base">
            <thead className="bg-gray-50">
              <tr className="text-left">
                <th className="px-3 py-3 font-bold uppercase text-sm">Score</th>
                <th className="px-3 py-3 font-bold uppercase text-sm">Type</th>
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
